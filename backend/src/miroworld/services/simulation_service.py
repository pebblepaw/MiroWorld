from __future__ import annotations

import json
import logging
import random
import re
import requests
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from miroworld.config import Settings
from miroworld.models.phase_a import PersonaFilterRequest
from miroworld.models.phase_b import SimulationRunRequest
from miroworld.services.llm_client import GeminiChatClient
from miroworld.services.persona_sampler import PersonaSampler
from miroworld.services.storage import SimulationStore


BACKEND_ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)


@dataclass
class SimulationService:
    settings: Settings

    def __post_init__(self) -> None:
        self.store = SimulationStore(self.settings.simulation_db_path)
        self.sampler = PersonaSampler(
            self.settings.nemotron_dataset,
            self.settings.nemotron_split,
            cache_dir=self.settings.nemotron_cache_dir,
            download_workers=self.settings.nemotron_download_workers,
        )
        self.llm = GeminiChatClient(self.settings)

    def run(self, req: SimulationRunRequest) -> dict[str, Any]:
        sample_req = PersonaFilterRequest(
            min_age=req.min_age,
            max_age=req.max_age,
            planning_areas=req.planning_areas,
            income_brackets=req.income_brackets,
            limit=req.agent_count,
            mode="local",
        )
        personas = self.sampler.sample(sample_req)
        if not personas:
            raise ValueError("No personas matched provided filters.")

        if self.settings.enable_real_oasis:
            result = self._run_oasis(req, personas)
            agents = result["agents"]
            interactions = result["interactions"]
            stage3a_approval_rate = float(result["stage3a_approval_rate"])
            stage3b_approval_rate = float(result["stage3b_approval_rate"])
            net_opinion_shift = float(result["net_opinion_shift"])
            runtime = "oasis"
        else:
            agents = self._build_agents(personas)
            interactions: list[dict[str, Any]] = []

            for round_no in range(1, req.rounds + 1):
                round_delta = self._run_round(req.policy_summary, agents, round_no, interactions)
                for agent in agents:
                    agent["opinion_post"] = max(1.0, min(10.0, agent["opinion_post"] + round_delta * 0.05))

            pre = [a["opinion_pre"] for a in agents]
            post = [a["opinion_post"] for a in agents]
            stage3a_approval_rate = _approval_rate(pre)
            stage3b_approval_rate = _approval_rate(post)
            net_opinion_shift = (sum(post) / len(post)) - (sum(pre) / len(pre))
            runtime = "heuristic"

        self.store.upsert_simulation(req.simulation_id, req.policy_summary, req.rounds, len(agents), runtime=runtime)
        self.store.replace_agents(req.simulation_id, agents)
        self.store.replace_interactions(req.simulation_id, interactions)

        return {
            "simulation_id": req.simulation_id,
            "platform": self.settings.simulation_platform,
            "agent_count": len(agents),
            "rounds": req.rounds,
            "stage3a_approval_rate": stage3a_approval_rate,
            "stage3b_approval_rate": stage3b_approval_rate,
            "net_opinion_shift": net_opinion_shift,
            "sqlite_path": self.settings.simulation_db_path,
            "runtime": runtime,
        }

    def run_with_personas(
        self,
        *,
        simulation_id: str,
        policy_summary: str,
        rounds: int,
        personas: list[dict[str, Any]],
        events_path: Path | None = None,
        force_live: bool = False,
        controversy_boost: float = 0.0,
        on_progress: Callable[[Path, int], None] | None = None,
        elapsed_offset_seconds: int = 0,
        tail_checkpoint_estimate_seconds: int = 0,
        seed_discussion_threads: list[str] | None = None,
    ) -> dict[str, Any]:
        resolved_seed_threads = [
            str(item).strip()
            for item in (seed_discussion_threads or [])
            if str(item).strip()
        ]
        token_usage: dict[str, Any] | None = None
        if force_live or self.settings.enable_real_oasis:
            result = self._run_oasis_with_inputs(
                simulation_id=simulation_id,
                policy_summary=policy_summary,
                rounds=rounds,
                personas=personas,
                events_path=events_path,
                controversy_boost=controversy_boost,
                on_progress=on_progress,
                elapsed_offset_seconds=elapsed_offset_seconds,
                tail_checkpoint_estimate_seconds=tail_checkpoint_estimate_seconds,
                seed_discussion_threads=resolved_seed_threads,
            )
            agents = result["agents"]
            interactions = result["interactions"]
            runtime = "oasis"
            stage3a_approval_rate = float(result["stage3a_approval_rate"])
            stage3b_approval_rate = float(result["stage3b_approval_rate"])
            net_opinion_shift = float(result["net_opinion_shift"])
            elapsed_seconds = int(result.get("elapsed_seconds", 0) or 0)
            counters = dict(result.get("counters") or {})
            token_usage = result.get("token_usage") if isinstance(result.get("token_usage"), dict) else None
        else:
            agents = self._build_agents(personas)
            interactions = []
            if resolved_seed_threads and agents:
                for index, question in enumerate(resolved_seed_threads):
                    actor = agents[index % len(agents)]
                    interactions.append(
                        {
                            "round_no": 0,
                            "actor_agent_id": actor["agent_id"],
                            "target_agent_id": None,
                            "action_type": "create_post",
                            "content": f"Analysis question seed {index + 1}: {question}",
                            "delta": 0.0,
                        }
                    )
            for round_no in range(1, rounds + 1):
                round_delta = self._run_round(policy_summary, agents, round_no, interactions)
                for agent in agents:
                    agent["opinion_post"] = max(1.0, min(10.0, agent["opinion_post"] + round_delta * 0.05))
            pre = [a["opinion_pre"] for a in agents]
            post = [a["opinion_post"] for a in agents]
            stage3a_approval_rate = _approval_rate(pre)
            stage3b_approval_rate = _approval_rate(post)
            net_opinion_shift = (sum(post) / len(post)) - (sum(pre) / len(pre))
            runtime = "heuristic"
            elapsed_seconds = 0
            counters = {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0}

        self.store.upsert_simulation(simulation_id, policy_summary, rounds, len(agents), runtime=runtime)
        self.store.replace_agents(simulation_id, agents)
        self.store.replace_interactions(simulation_id, interactions)
        payload = {
            "simulation_id": simulation_id,
            "platform": self.settings.simulation_platform,
            "agent_count": len(agents),
            "rounds": rounds,
            "stage3a_approval_rate": stage3a_approval_rate,
            "stage3b_approval_rate": stage3b_approval_rate,
            "net_opinion_shift": net_opinion_shift,
            "sqlite_path": self.settings.simulation_db_path,
            "runtime": runtime,
            "elapsed_seconds": elapsed_seconds,
            "counters": counters,
        }
        if token_usage is not None:
            payload["token_usage"] = token_usage
        return payload

    def build_context_bundles(
        self,
        *,
        simulation_id: str,
        policy_summary: str,
        knowledge_artifact: dict[str, Any],
        sampled_personas: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        node_lookup = {str(node.get("id")): node for node in knowledge_artifact.get("entity_nodes", [])}
        canonical_lookup = {
            str(node.get("canonical_key")): str(node.get("id"))
            for node in knowledge_artifact.get("entity_nodes", [])
            if node.get("canonical_key")
        }
        adjacency: dict[str, set[str]] = {}
        for edge in knowledge_artifact.get("relationship_edges", []):
            source = str(edge.get("source"))
            target = str(edge.get("target"))
            if source and target:
                adjacency.setdefault(source, set()).add(target)
                adjacency.setdefault(target, set()).add(source)

        bundles: dict[str, dict[str, Any]] = {}
        knowledge_summary = " ".join(str(knowledge_artifact.get("summary", "")).split()).strip()
        knowledge_digest = knowledge_summary
        if len(knowledge_digest) > 320:
            knowledge_digest = f"{knowledge_digest[:320].rstrip()}..."
        for row in sampled_personas:
            agent_id = str(row.get("agent_id"))
            persona = dict(row.get("persona") or {})
            reason = dict(row.get("selection_reason") or {})
            matched_context_nodes: list[str] = []
            graph_node_ids: list[str] = []

            for facet_key in reason.get("matched_facets", []) or []:
                facet_key = str(facet_key).strip()
                if not facet_key:
                    continue
                matched_context_nodes.append(facet_key)
                node_id = canonical_lookup.get(facet_key)
                if node_id:
                    graph_node_ids.append(node_id)

            lowered_entities = {str(value).strip().lower() for value in (reason.get("matched_document_entities") or []) if str(value).strip()}
            for node in knowledge_artifact.get("entity_nodes", []):
                label = str(node.get("label", "")).strip()
                if label and label.lower() in lowered_entities:
                    graph_node_ids.append(str(node.get("id")))

            expanded_ids = list(dict.fromkeys(graph_node_ids))
            for node_id in list(expanded_ids):
                for adjacent in sorted(adjacency.get(node_id, set())):
                    if adjacent not in expanded_ids:
                        expanded_ids.append(adjacent)

            source_ids: list[str] = []
            file_paths: list[str] = []
            context_labels: list[str] = []
            for node_id in expanded_ids:
                node = node_lookup.get(node_id, {})
                label = str(node.get("label", "")).strip()
                if label:
                    context_labels.append(label)
                for source_id in node.get("source_ids", []) or []:
                    text = str(source_id).strip()
                    if text and text not in source_ids:
                        source_ids.append(text)
                for file_path in node.get("file_paths", []) or []:
                    text = str(file_path).strip()
                    if text and text not in file_paths:
                        file_paths.append(text)

            salient_labels = ", ".join(context_labels[:4]) or "general policy context"
            persona_highlights = {
                "planning_area": persona.get("planning_area"),
                "occupation": persona.get("occupation"),
                "age": persona.get("age"),
                "income_bracket": persona.get("income_bracket"),
                "household_type": persona.get("household_type"),
            }
            compact_dossier = str(persona.get("mckainsey_context") or "").strip()
            if not compact_dossier:
                compact_dossier = str(reason.get("semantic_summary") or "").strip()
            if len(compact_dossier) > 180:
                compact_dossier = f"{compact_dossier[:180].rstrip()}..."
            matched_facet_text = ", ".join(matched_context_nodes[:4]) or "none"
            brief = (
                f"Persona highlights: {json.dumps(persona_highlights, ensure_ascii=False)}. "
                f"Matched facets: {matched_facet_text}. "
                f"Relevant knowledge nodes: {salient_labels}. "
                f"Policy relevance note: {compact_dossier or 'not provided'}."
            ).strip()
            bundles[agent_id] = {
                "agent_id": agent_id,
                "persona": persona,
                "brief": brief,
                "knowledge_digest": knowledge_digest,
                "matched_context_nodes": matched_context_nodes,
                "graph_node_ids": expanded_ids,
                "provenance": {
                    "source_ids": sorted(source_ids),
                    "file_paths": sorted(file_paths),
                },
            }

        return bundles

    def run_opinion_checkpoint(
        self,
        *,
        simulation_id: str,
        checkpoint_kind: str,
        policy_summary: str,
        agent_context_bundles: dict[str, dict[str, Any]],
        checkpoint_questions: list[dict[str, Any]] | None = None,
        on_token_usage: Callable[[int, int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        if not agent_context_bundles:
            return []
        resolved_questions = [item for item in (checkpoint_questions or []) if isinstance(item, dict)]
        batch_size = self._resolve_checkpoint_batch_size(total_agents=len(agent_context_bundles))
        max_attempts = 3
        records: list[dict[str, Any]] = []
        agent_ids = list(agent_context_bundles.keys())
        for start in range(0, len(agent_ids), batch_size):
            chunk_ids = agent_ids[start : start + batch_size]
            pending_ids = list(chunk_ids)
            chunk_records_by_agent: dict[str, dict[str, Any]] = {}

            for _attempt in range(max_attempts):
                if not pending_ids:
                    break
                bundle_chunk = [agent_context_bundles[agent_id] for agent_id in pending_ids]
                prompt = self._build_checkpoint_prompt(
                    simulation_id=simulation_id,
                    checkpoint_kind=checkpoint_kind,
                    policy_summary=policy_summary,
                    bundle_chunk=bundle_chunk,
                    checkpoint_questions=resolved_questions,
                )
                response_format = {"type": "json_object"} if self.settings.llm_provider == "ollama" else None
                try:
                    raw = self.llm.complete_required(
                        prompt,
                        system_prompt=(
                            "You classify the opinions of simulated Singapore residents about a policy. "
                            "Return valid JSON only."
                        ),
                        response_format=response_format,
                    )
                    if on_token_usage is not None:
                        on_token_usage(
                            _estimate_tokens(prompt),
                            _estimate_tokens(raw),
                            0,
                        )
                    parsed = _parse_json_payload(raw)
                    if isinstance(parsed, dict):
                        parsed = parsed.get("records")
                    if not isinstance(parsed, list):
                        raise RuntimeError("The configured model must return a JSON array for opinion checkpoints.")

                    chunk_records = self._normalize_checkpoint_records(
                        simulation_id=simulation_id,
                        checkpoint_kind=checkpoint_kind,
                        parsed_records=parsed,
                        bundle_chunk=bundle_chunk,
                        checkpoint_questions=resolved_questions,
                        allow_missing=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    if _attempt + 1 >= max_attempts:
                        raise RuntimeError(
                            "Opinion checkpoint failed after retries. "
                            f"provider={self.settings.llm_provider} model={self.settings.llm_model} "
                            f"checkpoint={checkpoint_kind} pending_agents={len(pending_ids)}: {exc}"
                        ) from exc
                    continue

                for record in chunk_records:
                    chunk_records_by_agent[record["agent_id"]] = record

                pending_ids = [agent_id for agent_id in pending_ids if agent_id not in chunk_records_by_agent]

            if pending_ids:
                raise RuntimeError(f"Opinion checkpoint response omitted agents: {', '.join(pending_ids[:5])}")

            records.extend(
                chunk_records_by_agent[agent_id]
                for agent_id in chunk_ids
                if agent_id in chunk_records_by_agent
            )

        return records

    def _resolve_checkpoint_batch_size(self, *, total_agents: int) -> int:
        provider = str(self.settings.llm_provider or "").strip().lower()
        if provider == "ollama":
            configured = max(1, int(self.settings.ollama_checkpoint_batch_size))
            if total_agents <= 20:
                return max(configured, 4)
            return configured
        return max(1, int(self.settings.default_checkpoint_batch_size))

    def _run_oasis(self, req: SimulationRunRequest, personas: list[dict[str, Any]]) -> dict[str, Any]:
        return self._run_oasis_with_inputs(
            simulation_id=req.simulation_id,
            policy_summary=req.policy_summary,
            rounds=req.rounds,
            personas=personas,
            events_path=None,
            controversy_boost=0.0,
        )

    def _run_oasis_with_inputs(
        self,
        *,
        simulation_id: str,
        policy_summary: str,
        rounds: int,
        personas: list[dict[str, Any]],
        events_path: Path | None,
        controversy_boost: float = 0.0,
        on_progress: Callable[[Path, int], None] | None = None,
        elapsed_offset_seconds: int = 0,
        tail_checkpoint_estimate_seconds: int = 0,
        seed_discussion_threads: list[str] | None = None,
    ) -> dict[str, Any]:
        provider_key = self.settings.resolved_gemini_key
        if not provider_key:
            raise RuntimeError("A provider API key is required for real OASIS runtime.")

        oasis_db_root = Path(self.settings.oasis_db_dir)
        if not oasis_db_root.is_absolute():
            oasis_db_root = BACKEND_ROOT / oasis_db_root
        oasis_db = oasis_db_root / f"{simulation_id}.db"

        run_log_dir = Path(self.settings.oasis_run_log_dir)
        if not run_log_dir.is_absolute():
            run_log_dir = BACKEND_ROOT / run_log_dir
        run_log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_log_path = run_log_dir / f"{simulation_id}-{ts}.log"
        timeout_seconds = self._resolve_oasis_timeout_seconds(rounds=rounds, persona_count=len(personas))
        oasis_semaphore = self._resolve_oasis_semaphore()
        sidecar_host = str(self.settings.oasis_sidecar_host or "").strip()

        payload = {
            "simulation_id": simulation_id,
            "policy_summary": policy_summary,
            "rounds": rounds,
            "personas": personas,
            "controversy_boost": max(0.0, min(1.0, float(controversy_boost))),
            "model_name": self.settings.gemini_model,
            "api_key": provider_key,
            "base_url": self.settings.gemini_openai_base_url,
            "oasis_db_path": str(oasis_db),
            "events_path": str(events_path) if events_path else None,
            "elapsed_offset_seconds": elapsed_offset_seconds,
            "tail_checkpoint_estimate_seconds": tail_checkpoint_estimate_seconds,
            "oasis_semaphore": oasis_semaphore,
            "seed_discussion_threads": [item for item in (seed_discussion_threads or []) if str(item).strip()],
        }

        if sidecar_host:
            return self._run_oasis_via_sidecar(
                payload,
                simulation_id=simulation_id,
                timeout_seconds=timeout_seconds,
                events_path=events_path,
                on_progress=on_progress,
                run_log_path=run_log_path,
            )

        runner = Path(self.settings.oasis_runner_script)
        if not runner.is_absolute():
            runner = BACKEND_ROOT / runner
        if not runner.exists():
            raise RuntimeError(f"OASIS runner script not found: {runner}")

        python_bin = self._resolve_oasis_python_bin()

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "oasis_input.json"
            output_path = Path(temp_dir) / "oasis_output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            cmd = [
                str(python_bin),
                str(runner),
                str(input_path),
                str(output_path),
            ]
            with run_log_path.open("w", encoding="utf-8") as log_file:
                log_file.write(f"command={cmd}\n")
                log_file.write(f"simulation_id={simulation_id}\n")
                log_file.write(f"provider={self.settings.llm_provider} model={self.settings.llm_model}\n")
                log_file.write(f"timeout_seconds={timeout_seconds}\n")
                log_file.write(f"oasis_semaphore={oasis_semaphore}\n")
                log_file.write(f"started_at={datetime.now(UTC).isoformat()}\n")
                log_file.flush()

                proc = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                start = time.time()
                heartbeat_every = 10
                while True:
                    rc = proc.poll()
                    elapsed = int(time.time() - start)
                    if rc is not None:
                        log_file.write(
                            f"process_exit_code={rc} finished_at={datetime.now(UTC).isoformat()} elapsed_seconds={elapsed}\n"
                        )
                        log_file.flush()
                        if rc != 0:
                            tail = _tail_file(run_log_path, lines=40)
                            raise RuntimeError(
                                "Real OASIS simulation failed. "
                                f"run_log={run_log_path} tail={tail}"
                            )
                        break

                    if elapsed > timeout_seconds:
                        proc.kill()
                        tail = _tail_file(run_log_path, lines=40)
                        raise RuntimeError(
                            "Real OASIS simulation timed out. "
                            f"provider={self.settings.llm_provider} model={self.settings.llm_model} "
                            f"timeout_seconds={timeout_seconds} "
                            f"run_log={run_log_path} tail={tail}"
                        )

                    if elapsed % heartbeat_every == 0:
                        log_file.write(f"heartbeat elapsed_seconds={elapsed}\n")
                        log_file.flush()
                    if on_progress is not None and events_path is not None:
                        on_progress(events_path, elapsed)
                    time.sleep(1)

            if not output_path.exists():
                raise RuntimeError("OASIS runner completed but no output payload was produced.")

            return json.loads(output_path.read_text(encoding="utf-8"))

    def _run_oasis_via_sidecar(
        self,
        payload: dict[str, Any],
        *,
        simulation_id: str,
        timeout_seconds: int,
        events_path: Path | None,
        on_progress: Callable[[Path, int], None] | None,
        run_log_path: Path,
    ) -> dict[str, Any]:
        base_url = self._oasis_sidecar_base_url()
        heartbeat_every = 10

        with run_log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"sidecar_base_url={base_url}\n")
            log_file.write(f"simulation_id={simulation_id}\n")
            log_file.write(f"provider={self.settings.llm_provider} model={self.settings.llm_model}\n")
            log_file.write(f"timeout_seconds={timeout_seconds}\n")
            log_file.write(f"started_at={datetime.now(UTC).isoformat()}\n")
            log_file.flush()

            try:
                create_response = requests.post(
                    f"{base_url}/jobs",
                    json=payload,
                    timeout=10,
                )
            except requests.RequestException as exc:
                raise RuntimeError(
                    "Real OASIS sidecar is unreachable. "
                    f"base_url={base_url} error={exc}"
                ) from exc

            if create_response.status_code >= 400:
                raise RuntimeError(
                    "Real OASIS sidecar rejected the simulation request. "
                    f"base_url={base_url} status={create_response.status_code} body={create_response.text[:1000]}"
                )

            try:
                job_payload = create_response.json()
            except ValueError as exc:
                raise RuntimeError(
                    "Real OASIS sidecar returned a non-JSON job response. "
                    f"base_url={base_url} body={create_response.text[:1000]}"
                ) from exc

            job_id = str(job_payload.get("job_id") or "").strip()
            if not job_id:
                raise RuntimeError(
                    "Real OASIS sidecar did not return a job id. "
                    f"base_url={base_url} payload={job_payload}"
                )

            log_file.write(f"job_id={job_id}\n")
            log_file.flush()

            start = time.time()
            while True:
                elapsed = int(time.time() - start)

                if elapsed > timeout_seconds:
                    try:
                        requests.delete(f"{base_url}/jobs/{job_id}", timeout=5)
                    except requests.RequestException as exc:
                        log_file.write(f"cancel_failed={exc}\n")
                        log_file.flush()
                    tail = _tail_file(run_log_path, lines=40)
                    raise RuntimeError(
                        "Real OASIS simulation timed out. "
                        f"provider={self.settings.llm_provider} model={self.settings.llm_model} "
                        f"timeout_seconds={timeout_seconds} run_log={run_log_path} tail={tail}"
                    )

                if elapsed % heartbeat_every == 0:
                    log_file.write(f"heartbeat elapsed_seconds={elapsed}\n")
                    log_file.flush()
                if on_progress is not None and events_path is not None:
                    on_progress(events_path, elapsed)

                try:
                    status_response = requests.get(
                        f"{base_url}/jobs/{job_id}",
                        timeout=5,
                    )
                except requests.RequestException as exc:
                    raise RuntimeError(
                        "Real OASIS sidecar status check failed. "
                        f"base_url={base_url} job_id={job_id} error={exc}"
                    ) from exc

                if status_response.status_code >= 400:
                    raise RuntimeError(
                        "Real OASIS sidecar returned an error status while polling. "
                        f"base_url={base_url} job_id={job_id} status={status_response.status_code} body={status_response.text[:1000]}"
                    )

                try:
                    status_payload = status_response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        "Real OASIS sidecar returned non-JSON job status. "
                        f"base_url={base_url} job_id={job_id} body={status_response.text[:1000]}"
                    ) from exc

                status = str(status_payload.get("status") or "").strip().lower()
                if status == "completed":
                    result = status_payload.get("result")
                    if not isinstance(result, dict):
                        raise RuntimeError(
                            "Real OASIS sidecar completed without a result payload. "
                            f"base_url={base_url} job_id={job_id} payload={status_payload}"
                        )
                    log_file.write(
                        f"completed_at={datetime.now(UTC).isoformat()} elapsed_seconds={elapsed}\n"
                    )
                    log_file.flush()
                    return result

                if status == "failed":
                    error = str(status_payload.get("error") or "unknown error").strip()
                    log_file.write(f"failed_error={error}\n")
                    log_file.flush()
                    raise RuntimeError(
                        "Real OASIS simulation failed via sidecar. "
                        f"job_id={job_id} error={error} run_log={run_log_path}"
                    )

                time.sleep(1)

    def _oasis_sidecar_base_url(self) -> str:
        host = str(self.settings.oasis_sidecar_host or "").strip()
        if not host:
            raise RuntimeError("OASIS sidecar host is not configured.")
        port = int(self.settings.oasis_sidecar_port)
        return f"http://{host}:{port}"

    def _resolve_oasis_python_bin(self) -> Path:
        configured = Path(self.settings.oasis_python_bin)
        if not configured.is_absolute():
            configured = BACKEND_ROOT / configured

        fallback = BACKEND_ROOT / ".venv311" / "bin" / "python"
        candidates: list[Path] = []
        for candidate in (configured, fallback):
            if candidate in candidates:
                continue
            candidates.append(candidate)

        failures: list[tuple[Path, str]] = []
        for candidate in candidates:
            reason = self._validate_oasis_python_bin(candidate)
            if reason is None:
                if candidate != configured and failures:
                    logger.warning(
                        "Configured OASIS runtime %s is invalid; using fallback %s (%s)",
                        configured,
                        candidate,
                        failures[0][1],
                    )
                return candidate
            failures.append((candidate, reason))

        details = "; ".join(f"{path}: {reason}" for path, reason in failures)
        raise RuntimeError(
            "OASIS Python runtime is unavailable. "
            "Install backend/.venv311 or point OASIS_PYTHON_BIN to a valid Python 3.11 environment with camel-oasis installed."
            + (f" Details: {details}" if details else "")
        )

    def _validate_oasis_python_bin(self, python_bin: Path) -> str | None:
        if not python_bin.exists():
            return "runtime not found"

        check_script = BACKEND_ROOT / "scripts" / "check_oasis_runtime.py"
        if not check_script.exists():
            return f"runtime check script not found: {check_script}"

        try:
            result = subprocess.run(
                [str(python_bin), str(check_script)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return str(exc)

        if result.returncode == 0:
            return None

        output = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        output = re.sub(r"\s+", " ", output)
        return output[:240]

    def _resolve_oasis_timeout_seconds(self, *, rounds: int, persona_count: int) -> int:
        configured_timeout = max(120, int(self.settings.oasis_timeout_seconds))
        provider = str(self.settings.llm_provider or "").strip().lower()
        if provider == "ollama":
            per_agent_round_seconds = max(4, int(self.settings.oasis_ollama_timeout_per_agent_round_seconds))
            base_buffer = 300
        else:
            per_agent_round_seconds = max(1, int(self.settings.oasis_default_timeout_per_agent_round_seconds))
            base_buffer = 120
        estimated_timeout = base_buffer + (max(1, persona_count) * max(1, rounds) * per_agent_round_seconds)
        if provider == "ollama":
            estimated_timeout += 120 * max(1, rounds)
        return max(configured_timeout, estimated_timeout)

    def _resolve_oasis_semaphore(self) -> int:
        provider = str(self.settings.llm_provider or "").strip().lower()
        if provider == "ollama":
            return max(1, int(self.settings.oasis_ollama_semaphore))
        return max(1, int(self.settings.oasis_default_semaphore))

    def _build_checkpoint_prompt(
        self,
        *,
        simulation_id: str,
        checkpoint_kind: str,
        policy_summary: str,
        bundle_chunk: list[dict[str, Any]],
        checkpoint_questions: list[dict[str, Any]] | None = None,
    ) -> str:
        knowledge_digest = ""
        if bundle_chunk:
            knowledge_digest = str(bundle_chunk[0].get("knowledge_digest") or "").strip()
        payload = [
            {
                "agent_id": bundle["agent_id"],
                "brief": bundle["brief"],
                "matched_context_nodes": list(bundle.get("matched_context_nodes", []))[:8],
            }
            for bundle in bundle_chunk
        ]
        questions = [item for item in (checkpoint_questions or []) if isinstance(item, dict)]
        question_block = ""
        if questions:
            question_lines: list[str] = []
            for question in questions:
                metric_name = str(question.get("metric_name", "")).strip()
                metric_type = str(question.get("type", "")).strip() or "scale"
                question_text = str(question.get("question", "")).strip()
                if not metric_name or not question_text:
                    continue
                question_lines.append(
                    f'- metric_name="{metric_name}" type="{metric_type}" question="{question_text}"'
                )
            if question_lines:
                question_block = (
                    "\nCheckpoint questions (populate metric_answers for each metric_name):\n"
                    + "\n".join(question_lines)
                    + "\n"
                )
        context_line = f"Shared document context: {knowledge_digest}\n" if knowledge_digest else ""
        return (
            f"Simulation: {simulation_id}\n"
            f"Checkpoint kind: {checkpoint_kind}\n"
            f"Policy summary: {policy_summary}\n"
            f"{context_line}\n"
            f"{question_block}"
            "For each agent, assess their stance on the policy and return JSON only using this schema:\n"
            "{\"records\":[{\"agent_id\": str, \"stance_score\": number, \"stance_class\": \"approve|neutral|dissent\", "
            "\"confidence\": number, \"primary_driver\": str, \"confirmed_name\": str, "
            "\"metric_answers\": {metric_name: number|string}, \"matched_context_nodes\": [str]}]}\n\n"
            f"Agents:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _normalize_checkpoint_records(
        self,
        *,
        simulation_id: str,
        checkpoint_kind: str,
        parsed_records: list[dict[str, Any]],
        bundle_chunk: list[dict[str, Any]],
        checkpoint_questions: list[dict[str, Any]] | None = None,
        allow_missing: bool = False,
    ) -> list[dict[str, Any]]:
        bundle_lookup = {bundle["agent_id"]: bundle for bundle in bundle_chunk}
        questions = [item for item in (checkpoint_questions or []) if isinstance(item, dict)]
        normalized: list[dict[str, Any]] = []
        for item in parsed_records:
            if not isinstance(item, dict):
                continue
            agent_id = str(item.get("agent_id", "")).strip()
            if not agent_id or agent_id not in bundle_lookup:
                continue
            score = float(item.get("stance_score", 0) or 0)
            confidence = float(item.get("confidence", 0) or 0)
            stance_class = str(item.get("stance_class", "")).strip().lower() or _stance_class_from_score(score)
            matched_nodes = [
                str(value).strip()
                for value in (item.get("matched_context_nodes") or bundle_lookup[agent_id].get("matched_context_nodes") or [])
                if str(value).strip()
            ]
            metric_answers = _normalize_metric_answers(item.get("metric_answers"), questions)
            normalized.append(
                {
                    "simulation_id": simulation_id,
                    "checkpoint_kind": checkpoint_kind,
                    "agent_id": agent_id,
                    "stance_score": round(max(0.0, min(1.0, score)), 4),
                    "stance_class": stance_class,
                    "confidence": round(max(0.0, min(1.0, confidence)), 4),
                    "primary_driver": str(item.get("primary_driver", "")).strip() or "unspecified",
                    "confirmed_name": str(item.get("confirmed_name", "")).strip() or None,
                    "metric_answers": metric_answers,
                    "matched_context_nodes": matched_nodes,
                }
            )

        missing = self._missing_checkpoint_agent_ids(bundle_chunk=bundle_chunk, records=normalized)
        if missing and not allow_missing:
            raise RuntimeError(f"Opinion checkpoint response omitted agents: {', '.join(missing[:5])}")
        return normalized

    def _missing_checkpoint_agent_ids(
        self,
        *,
        bundle_chunk: list[dict[str, Any]],
        records: list[dict[str, Any]],
    ) -> list[str]:
        present = {record.get("agent_id") for record in records}
        return [bundle["agent_id"] for bundle in bundle_chunk if bundle["agent_id"] not in present]

    def snapshot(self, simulation_id: str) -> dict[str, Any]:
        simulation = self.store.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation not found: {simulation_id}")

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        stage3a = [a["opinion_pre"] for a in agents]
        stage3b = [a["opinion_post"] for a in agents]

        post_interactions = [i for i in interactions if i["action_type"] == "create_post"]
        top_posts = sorted(post_interactions, key=lambda x: abs(x.get("delta", 0)), reverse=True)[:10]

        return {
            "simulation_id": simulation_id,
            "stats": {
                "agent_count": len(agents),
                "rounds": simulation["rounds"],
                "interactions": len(interactions),
                "approval_pre": _approval_rate(stage3a),
                "approval_post": _approval_rate(stage3b),
                "runtime": simulation.get("runtime", "heuristic"),
            },
            "stage3a_scores": stage3a,
            "stage3b_scores": stage3b,
            "top_posts": top_posts,
        }

    def _build_agents(self, personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        agents: list[dict[str, Any]] = []
        for idx, persona in enumerate(personas):
            base = _persona_seed_opinion(persona)
            agents.append(
                {
                    "agent_id": f"agent-{idx+1:04d}",
                    "persona": persona,
                    "opinion_pre": base,
                    "opinion_post": base,
                }
            )
        return agents

    def _run_round(
        self,
        policy_summary: str,
        agents: list[dict[str, Any]],
        round_no: int,
        interactions: list[dict[str, Any]],
    ) -> float:
        deltas: list[float] = []
        avg = sum(a["opinion_post"] for a in agents) / len(agents)

        for agent in agents:
            jitter = random.uniform(-0.45, 0.45)
            social_pull = (avg - agent["opinion_post"]) * 0.18
            delta = jitter + social_pull
            agent["opinion_post"] = max(1.0, min(10.0, agent["opinion_post"] + delta))
            deltas.append(delta)

            sentiment = "support" if agent["opinion_post"] >= 7 else "oppose" if agent["opinion_post"] <= 4 else "neutral"
            content = f"Round {round_no} {sentiment} stance on policy: {policy_summary[:120]}"

            interactions.append(
                {
                    "round_no": round_no,
                    "actor_agent_id": agent["agent_id"],
                    "target_agent_id": None,
                    "action_type": "create_post",
                    "content": content,
                    "delta": delta,
                }
            )

            target = random.choice(agents)["agent_id"]
            if target != agent["agent_id"]:
                interactions.append(
                    {
                        "round_no": round_no,
                        "actor_agent_id": agent["agent_id"],
                        "target_agent_id": target,
                        "action_type": "comment",
                        "content": f"Responding to {target} in round {round_no}",
                        "delta": delta * 0.4,
                    }
                )

        return sum(deltas) / len(deltas)


def _tail_file(path: Path, lines: int = 40) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
    except Exception:  # noqa: BLE001
        return "<unable to read run log>"


def _estimate_tokens(text: str) -> int:
    normalized = str(text or "").strip()
    if not normalized:
        return 0
    return max(1, int(len(normalized) / 4))


def _normalize_metric_answers(raw_answers: Any, checkpoint_questions: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(raw_answers, dict):
        return {}
    expected = {
        str(question.get("metric_name", "")).strip()
        for question in checkpoint_questions
        if str(question.get("metric_name", "")).strip()
    }
    normalized: dict[str, Any] = {}
    for key, value in raw_answers.items():
        metric_name = str(key or "").strip()
        if not metric_name:
            continue
        if expected and metric_name not in expected:
            continue
        if isinstance(value, bool):
            normalized[metric_name] = "yes" if value else "no"
            continue
        if isinstance(value, (int, float)):
            normalized[metric_name] = float(value)
            continue
        text = str(value or "").strip()
        if text:
            normalized[metric_name] = text
    return normalized


def _persona_seed_opinion(persona: dict[str, Any]) -> float:
    # Demographic-prior heuristic for Stage 3a baseline before social influence.
    base = 5.5
    age = persona.get("age")
    if isinstance(age, (int, float)):
        if age >= 60:
            base -= 0.8
        elif age <= 30:
            base += 0.4

    income = str(persona.get("income_bracket", "")).lower()
    if "$1,000" in income or "$2,000" in income or "$3,000" in income:
        base -= 0.5
    if "$10,000" in income or "$12,000" in income:
        base += 0.6

    return max(1.0, min(10.0, base + random.uniform(-1.0, 1.0)))


def _approval_rate(scores: list[float]) -> float:
    if not scores:
        return 0.0
    approved = [s for s in scores if s >= 7.0]
    return round(len(approved) / len(scores), 4)


def _parse_json_payload(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    if not cleaned.startswith("{") and not cleaned.startswith("["):
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
        if match:
            cleaned = match.group(1)
    return json.loads(cleaned)


def _stance_class_from_score(score: float) -> str:
    if score >= 0.67:
        return "approve"
    if score <= 0.33:
        return "dissent"
    return "neutral"
