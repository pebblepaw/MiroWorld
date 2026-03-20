from __future__ import annotations

import json
import random
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from mckainsey.config import Settings
from mckainsey.models.phase_a import PersonaFilterRequest
from mckainsey.models.phase_b import SimulationRunRequest
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.storage import SimulationStore


BACKEND_ROOT = Path(__file__).resolve().parents[3]


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
        on_progress: Callable[[Path, int], None] | None = None,
        elapsed_offset_seconds: int = 0,
        tail_checkpoint_estimate_seconds: int = 0,
    ) -> dict[str, Any]:
        if force_live or self.settings.enable_real_oasis:
            result = self._run_oasis_with_inputs(
                simulation_id=simulation_id,
                policy_summary=policy_summary,
                rounds=rounds,
                personas=personas,
                events_path=events_path,
                on_progress=on_progress,
                elapsed_offset_seconds=elapsed_offset_seconds,
                tail_checkpoint_estimate_seconds=tail_checkpoint_estimate_seconds,
            )
            agents = result["agents"]
            interactions = result["interactions"]
            runtime = "oasis"
            stage3a_approval_rate = float(result["stage3a_approval_rate"])
            stage3b_approval_rate = float(result["stage3b_approval_rate"])
            net_opinion_shift = float(result["net_opinion_shift"])
            elapsed_seconds = int(result.get("elapsed_seconds", 0) or 0)
            counters = dict(result.get("counters") or {})
        else:
            agents = self._build_agents(personas)
            interactions = []
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
        return {
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
        knowledge_summary = str(knowledge_artifact.get("summary", "")).strip()
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
            brief = (
                f"Simulation {simulation_id} policy summary: {policy_summary.strip()} "
                f"Document context: {knowledge_summary} "
                f"Relevant nodes: {salient_labels}. "
                f"Persona profile: {json.dumps(persona, ensure_ascii=False)}."
            ).strip()
            bundles[agent_id] = {
                "agent_id": agent_id,
                "persona": persona,
                "brief": brief,
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
    ) -> list[dict[str, Any]]:
        if not agent_context_bundles:
            return []
        batch_size = 25
        records: list[dict[str, Any]] = []
        agent_ids = list(agent_context_bundles.keys())
        for start in range(0, len(agent_ids), batch_size):
            chunk_ids = agent_ids[start : start + batch_size]
            bundle_chunk = [agent_context_bundles[agent_id] for agent_id in chunk_ids]
            prompt = self._build_checkpoint_prompt(
                simulation_id=simulation_id,
                checkpoint_kind=checkpoint_kind,
                policy_summary=policy_summary,
                bundle_chunk=bundle_chunk,
            )
            raw = self.llm.complete_required(
                prompt,
                system_prompt=(
                    "You classify the opinions of simulated Singapore residents about a policy. "
                    "Return valid JSON only."
                ),
            )
            parsed = _parse_json_payload(raw)
            if not isinstance(parsed, list):
                raise RuntimeError("Gemini must return a JSON array for opinion checkpoints.")
            chunk_records = self._normalize_checkpoint_records(
                simulation_id=simulation_id,
                checkpoint_kind=checkpoint_kind,
                parsed_records=parsed,
                bundle_chunk=bundle_chunk,
            )
            records.extend(chunk_records)

        return records

    def _run_oasis(self, req: SimulationRunRequest, personas: list[dict[str, Any]]) -> dict[str, Any]:
        return self._run_oasis_with_inputs(
            simulation_id=req.simulation_id,
            policy_summary=req.policy_summary,
            rounds=req.rounds,
            personas=personas,
            events_path=None,
        )

    def _run_oasis_with_inputs(
        self,
        *,
        simulation_id: str,
        policy_summary: str,
        rounds: int,
        personas: list[dict[str, Any]],
        events_path: Path | None,
        on_progress: Callable[[Path, int], None] | None = None,
        elapsed_offset_seconds: int = 0,
        tail_checkpoint_estimate_seconds: int = 0,
    ) -> dict[str, Any]:
        runner = Path(self.settings.oasis_runner_script)
        if not runner.is_absolute():
            runner = BACKEND_ROOT / runner
        if not runner.exists():
            raise RuntimeError(f"OASIS runner script not found: {runner}")

        python_bin = Path(self.settings.oasis_python_bin)
        if not python_bin.is_absolute():
            python_bin = BACKEND_ROOT / python_bin
        if not python_bin.exists():
            raise RuntimeError(
                f"OASIS python runtime not found: {python_bin}. "
                "Create backend/.venv311 and install camel-oasis first."
            )

        gemini_key = self.settings.resolved_gemini_key
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY/GEMINI_API is required for real OASIS runtime.")

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

        payload = {
            "simulation_id": simulation_id,
            "policy_summary": policy_summary,
            "rounds": rounds,
            "personas": personas,
            "model_name": self.settings.gemini_model,
            "gemini_api_key": gemini_key,
            "openai_base_url": self.settings.gemini_openai_base_url,
            "oasis_db_path": str(oasis_db),
            "events_path": str(events_path) if events_path else None,
            "elapsed_offset_seconds": elapsed_offset_seconds,
            "tail_checkpoint_estimate_seconds": tail_checkpoint_estimate_seconds,
        }

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

                    if elapsed > self.settings.oasis_timeout_seconds:
                        proc.kill()
                        tail = _tail_file(run_log_path, lines=40)
                        raise RuntimeError(
                            "Real OASIS simulation timed out. "
                            f"timeout_seconds={self.settings.oasis_timeout_seconds} "
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

    def _build_checkpoint_prompt(
        self,
        *,
        simulation_id: str,
        checkpoint_kind: str,
        policy_summary: str,
        bundle_chunk: list[dict[str, Any]],
    ) -> str:
        payload = [
            {
                "agent_id": bundle["agent_id"],
                "brief": bundle["brief"],
                "matched_context_nodes": bundle.get("matched_context_nodes", []),
            }
            for bundle in bundle_chunk
        ]
        return (
            f"Simulation: {simulation_id}\n"
            f"Checkpoint kind: {checkpoint_kind}\n"
            f"Policy summary: {policy_summary}\n\n"
            "For each agent, assess their stance on the policy and return JSON only using this schema:\n"
            "[{\"agent_id\": str, \"stance_score\": number, \"stance_class\": \"approve|neutral|dissent\", "
            "\"confidence\": number, \"primary_driver\": str, \"matched_context_nodes\": [str]}]\n\n"
            f"Agents:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    def _normalize_checkpoint_records(
        self,
        *,
        simulation_id: str,
        checkpoint_kind: str,
        parsed_records: list[dict[str, Any]],
        bundle_chunk: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        bundle_lookup = {bundle["agent_id"]: bundle for bundle in bundle_chunk}
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
            normalized.append(
                {
                    "simulation_id": simulation_id,
                    "checkpoint_kind": checkpoint_kind,
                    "agent_id": agent_id,
                    "stance_score": round(max(0.0, min(1.0, score)), 4),
                    "stance_class": stance_class,
                    "confidence": round(max(0.0, min(1.0, confidence)), 4),
                    "primary_driver": str(item.get("primary_driver", "")).strip() or "unspecified",
                    "matched_context_nodes": matched_nodes,
                }
            )

        missing = [bundle["agent_id"] for bundle in bundle_chunk if bundle["agent_id"] not in {record["agent_id"] for record in normalized}]
        if missing:
            raise RuntimeError(f"Opinion checkpoint response omitted agents: {', '.join(missing[:5])}")
        return normalized

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
