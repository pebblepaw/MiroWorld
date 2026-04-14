from __future__ import annotations

import logging
import threading
import time
import uuid
import re
import shutil
import sqlite3
import json
from pathlib import Path
import random
from collections import Counter
from typing import Any

from fastapi import HTTPException
from fastapi import UploadFile

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService
from miroworld.services.country_dataset_service import CountryDatasetService
from miroworld.services.country_metadata_service import CountryMetadataService
from miroworld.services.demo_service import DemoService
from miroworld.services.document_parser import extract_document_text
from miroworld.services.lightrag_service import LightRAGService, OCCUPATION_NAMES
from miroworld.services.knowledge_stream_service import KnowledgeStreamService
from miroworld.services.memory_service import MemoryService
from miroworld.services.metrics_service import MetricsService
from miroworld.services.model_provider_service import (
    curate_provider_models,
    ensure_ollama_models_available,
    mask_api_key,
    normalize_provider,
    provider_catalog,
    provider_model_unavailability_hint,
    resolve_model_selection,
    selection_to_settings_update,
)
from miroworld.services.persona_relevance_service import PersonaRelevanceService
from miroworld.services.persona_sampler import PersonaSampler
from miroworld.services.report_service import ReportService
from miroworld.services.simulation_service import SimulationService
from miroworld.services.simulation_stream_service import SimulationStreamService
from miroworld.services.storage import SimulationStore
from miroworld.services.token_tracker import TokenTracker

MAX_AFFECTED_GROUPS_CANDIDATES = 1000
MAX_BASELINE_CANDIDATES = 1200
MIN_AFFECTED_GROUPS_CANDIDATES = 400
MIN_BASELINE_CANDIDATES = 600
logger = logging.getLogger(__name__)


class ConsoleService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.sampler = PersonaSampler(
            settings.nemotron_dataset,
            settings.nemotron_split,
            cache_dir=settings.nemotron_cache_dir,
            download_workers=settings.nemotron_download_workers,
        )
        self.streams = SimulationStreamService(settings)
        self.knowledge_streams = KnowledgeStreamService(settings)
        self.demo = DemoService(settings)
        self.country_datasets = CountryDatasetService(settings)
        self.country_metadata = CountryMetadataService(settings)
        self._ensure_session_config_table()
        self._ensure_session_token_usage_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.settings.simulation_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_session_config_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_configs (
                    session_id TEXT PRIMARY KEY,
                    country TEXT,
                    use_case TEXT,
                    provider TEXT,
                    model TEXT,
                    guiding_prompt TEXT,
                    analysis_questions TEXT,
                    config_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {
                str(row[1]).strip().lower()
                for row in conn.execute("PRAGMA table_info(session_configs)").fetchall()
            }
            if "analysis_questions" not in columns:
                conn.execute("ALTER TABLE session_configs ADD COLUMN analysis_questions TEXT")

    def _ensure_session_token_usage_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_token_usage (
                    session_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_cached_tokens INTEGER NOT NULL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _session_record(self, session_id: str) -> dict[str, Any] | None:
        return self.store.get_console_session(session_id)

    def _session_mode(self, session_id: str) -> str:
        session = self._session_record(session_id)
        if not session:
            return "demo"
        return str(session.get("mode", "demo")).strip().lower() or "demo"

    def _is_live_session(self, session_id: str) -> bool:
        return self._session_mode(session_id) == "live"

    def _session_model_overrides(self, session: dict[str, Any] | None) -> dict[str, Any]:
        if not session:
            return {}
        return {
            "provider": session.get("model_provider"),
            "model_name": session.get("model_name"),
            "embed_model_name": session.get("embed_model_name"),
            "api_key": session.get("api_key"),
            "base_url": session.get("base_url"),
        }

    def _runtime_settings_for_session(self, session_id: str) -> Settings:
        session = self._session_record(session_id)
        selection = resolve_model_selection(
            self.settings,
            **self._session_model_overrides(session),
            allow_provider_env_key_fallback=False,
        )
        updates = selection_to_settings_update(selection)
        updates["lightrag_workdir"] = self._session_lightrag_workdir(
            session_id,
            provider=selection.provider,
            embed_model_name=selection.embed_model_name,
        )
        return self.settings.model_copy(update=updates)

    def _session_lightrag_workdir(self, session_id: str, *, provider: str, embed_model_name: str) -> str:
        base = Path(self.settings.lightrag_workdir)
        provider_slug = re.sub(r"[^a-zA-Z0-9]+", "_", provider.lower()).strip("_") or "provider"
        embed_slug = re.sub(r"[^a-zA-Z0-9]+", "_", embed_model_name.lower()).strip("_") or "embed"
        return str((base / "sessions" / session_id / f"{provider_slug}_{embed_slug}").resolve())

    def _session_model_payload(self, session_id: str) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        selection = resolve_model_selection(
            self.settings,
            **self._session_model_overrides(session),
            allow_provider_env_key_fallback=False,
        )
        return {
            "session_id": session_id,
            "model_provider": selection.provider,
            "model_name": selection.model_name,
            "embed_model_name": selection.embed_model_name,
            "base_url": selection.base_url,
            "api_key_configured": selection.api_key_configured,
            "api_key_masked": mask_api_key(selection.api_key),
        }

    def _session_country(self, session_id: str) -> str:
        session_cfg = self._read_session_config(session_id)
        return str(session_cfg.get("country") or "singapore").strip().lower() or "singapore"

    def _country_geography_field(self, country_cfg: dict[str, Any]) -> str:
        return self.country_metadata.geography_field(country_cfg)

    def _session_country_config(self, session_id: str) -> tuple[str, dict[str, Any], str]:
        country = self._session_country(session_id)
        config_service = ConfigService(self.settings)
        country_cfg = config_service.get_country(country)
        dataset_path = self.country_datasets.ensure_country_ready(country)
        return country, country_cfg, dataset_path

    def _clear_population_downstream_artifacts(self, session_id: str) -> None:
        self.store.clear_population_artifact(session_id)
        self.store.clear_simulation_events(session_id)
        self.store.clear_simulation_state_snapshot(session_id)
        self.store.clear_report_cache(session_id)
        self.store.clear_report_state(session_id)
        self.store.clear_checkpoint_records(session_id)
        self.store.clear_interaction_transcripts(session_id)
        self.store.reset_memory_sync_state(session_id)

    def _clear_knowledge_downstream_artifacts(self, session_id: str) -> None:
        self.store.clear_knowledge_artifact(session_id)
        self._clear_lightrag_workspace(session_id)
        self.knowledge_streams.reset(session_id)
        self._clear_population_downstream_artifacts(session_id)

    def _clear_lightrag_workspace(self, session_id: str) -> None:
        try:
            runtime_settings = self._runtime_settings_for_session(session_id)
        except Exception:  # noqa: BLE001
            return
        workdir = Path(str(runtime_settings.lightrag_workdir or "")).expanduser()
        if not workdir.exists():
            return
        shutil.rmtree(workdir, ignore_errors=True)

    def _format_runtime_failure_detail(self, session_id: str, exc: Exception, *, action: str) -> str:
        try:
            runtime_settings = self._runtime_settings_for_session(session_id)
            provider = runtime_settings.llm_provider
            model_name = runtime_settings.llm_model
        except Exception:  # noqa: BLE001
            provider = self.settings.llm_provider
            model_name = self.settings.llm_model

        raw_message = str(exc).strip() or exc.__class__.__name__
        lowered = raw_message.lower()
        hint = ""

        if "insufficient_quota" in lowered or "quota" in lowered:
            hint = "Provider quota or billing limits were hit for the configured API key."
        elif provider == "ollama" and any(token in lowered for token in ("timed out", "timeout", "connection", "refused")):
            hint = "Local Ollama runtime appears unavailable or overloaded."

        detail = f"{action} failed for provider '{provider}' model '{model_name}': {raw_message}"
        if hint:
            detail = f"{detail}. {hint}"
        return detail

    def _summarize_simulation_failure(self, exc: Exception) -> str:
        raw_message = str(exc).strip() or exc.__class__.__name__
        lowered = raw_message.lower()

        if ("no module named 'camel'" in lowered) or ("no module named 'oasis'" in lowered):
            return "Simulation runtime is unavailable because the OASIS Python environment is missing required packages."
        if "oasis python runtime is unavailable" in lowered or "oasis python runtime not found" in lowered:
            return "Simulation runtime is unavailable. Reinstall the OASIS Python environment or point OASIS_PYTHON_BIN to backend/.venv311."
        if "a provider api key is required" in lowered:
            return "Simulation couldn't start because the provider API key is missing."
        if "insufficient_quota" in lowered or "quota" in lowered:
            return "The model provider rejected the simulation because the API quota or billing limit was reached."
        if "no longer available" in lowered or "not_found" in lowered:
            return "The selected model is no longer available from the provider. Choose a current model and try again."
        if "timed out" in lowered or "timeout_seconds=" in lowered:
            return "The simulation timed out before it could finish. Try fewer agents or rounds, or use a faster model."
        if "run_log=" in lowered or "traceback" in lowered or "real oasis simulation failed" in lowered:
            return "The simulation failed in the OASIS runtime. Check the backend run log for details."
        if len(raw_message) > 180:
            return "The simulation could not be completed. Check the backend logs and try again."
        return raw_message

    def model_provider_catalog(self) -> dict[str, Any]:
        return {"providers": provider_catalog(self.settings)}

    def _provider_requires_user_api_key(self, provider: str | None) -> bool:
        return normalize_provider(provider) in {"google", "openai", "openrouter"}

    def _resolve_session_api_key(
        self,
        session: dict[str, Any] | None,
        *,
        provider: str,
        api_key: str | None,
    ) -> str | None:
        normalized_provider = normalize_provider(provider)
        if not self._provider_requires_user_api_key(normalized_provider):
            return str(api_key or "").strip() or None

        explicit_api_key = str(api_key).strip() if api_key is not None else None
        if api_key is not None:
            if explicit_api_key:
                return explicit_api_key
            raise HTTPException(status_code=422, detail=f"API key is required for provider '{normalized_provider}'.")

        if session:
            existing_provider = normalize_provider(session.get("model_provider"))
            existing_api_key = str(session.get("api_key") or "").strip() or None
            if existing_provider == normalized_provider and existing_api_key:
                return existing_api_key

        raise HTTPException(status_code=422, detail=f"API key is required for provider '{normalized_provider}'.")

    def v2_provider_catalog(self) -> list[dict[str, Any]]:
        provider_name_map = {
            "google": "gemini",
            "openrouter": "openrouter",
            "openai": "openai",
            "ollama": "ollama",
        }

        rows: list[dict[str, Any]] = []
        for provider in self.model_provider_catalog()["providers"]:
            provider_id = str(provider.get("id", "")).strip().lower()
            if provider_id not in provider_name_map:
                continue

            default_model = str(provider.get("default_model") or "").strip()
            models: list[str] = [default_model] if default_model else []
            try:
                listed = self.list_provider_models(provider_id)
                discovered = [str(item.get("id", "")).strip() for item in listed.get("models", [])]
                discovered = [item for item in discovered if item]
                if discovered:
                    models = curate_provider_models(
                        provider_id,
                        discovered,
                        default_model=default_model,
                    )
            except Exception:  # noqa: BLE001
                # Keep compatibility endpoint resilient when provider discovery
                # requires credentials or local runtimes are unavailable.
                pass

            rows.append(
                {
                    "name": provider_name_map[provider_id],
                    "models": models,
                    "requires_api_key": bool(provider.get("requires_api_key", False)),
                }
            )
        return rows

    def _read_session_config(self, session_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM session_configs WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return {}
        payload = dict(row)
        raw_json = payload.get("config_json")
        if raw_json:
            try:
                payload.update(json.loads(str(raw_json)))
            except Exception:  # noqa: BLE001
                pass
        raw_questions = payload.get("analysis_questions")
        if isinstance(raw_questions, str):
            try:
                decoded = json.loads(raw_questions)
                payload["analysis_questions"] = decoded if isinstance(decoded, list) else []
            except Exception:  # noqa: BLE001
                payload["analysis_questions"] = []
        return payload

    def _upsert_session_config(self, session_id: str, config_patch: dict[str, Any]) -> dict[str, Any]:
        existing = self._read_session_config(session_id)
        merged = dict(existing)
        merged.update({key: value for key, value in config_patch.items() if value is not None})

        normalized_provider = normalize_provider(merged.get("provider")) if merged.get("provider") else None
        provider_for_payload = "gemini" if normalized_provider == "google" else normalized_provider
        use_case = str(merged.get("use_case") or "").strip().lower() or None
        country = str(merged.get("country") or "").strip().lower() or None
        model = str(merged.get("model") or "").strip() or None
        guiding_prompt = (
            str(merged.get("guiding_prompt")).strip()
            if merged.get("guiding_prompt") is not None
            else None
        )
        analysis_questions_raw = merged.get("analysis_questions", [])
        analysis_questions = (
            [item for item in analysis_questions_raw if isinstance(item, dict)]
            if isinstance(analysis_questions_raw, list)
            else []
        )

        stored_json = {
            "country": country,
            "use_case": use_case,
            "provider": provider_for_payload,
            "model": model,
            "guiding_prompt": guiding_prompt,
            "analysis_questions": analysis_questions,
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_configs(
                    session_id,
                    country,
                    use_case,
                    provider,
                    model,
                    guiding_prompt,
                    analysis_questions,
                    config_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    country=excluded.country,
                    use_case=excluded.use_case,
                    provider=excluded.provider,
                    model=excluded.model,
                    guiding_prompt=excluded.guiding_prompt,
                    analysis_questions=excluded.analysis_questions,
                    config_json=excluded.config_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    country,
                    use_case,
                    provider_for_payload,
                    model,
                    guiding_prompt,
                    json.dumps(analysis_questions, ensure_ascii=False),
                    json.dumps(stored_json, ensure_ascii=False),
                ),
            )

        return self._read_session_config(session_id)

    def _resolve_guiding_prompt(self, session_id: str, explicit_guiding_prompt: str | None) -> str | None:
        cleaned = str(explicit_guiding_prompt or "").strip()
        if cleaned:
            return cleaned

        session_cfg = self._read_session_config(session_id)
        use_case = str(session_cfg.get("use_case") or "").strip()
        if not use_case:
            return None

        try:
            config_service = ConfigService(self.settings)
            default_prompt = str(config_service.get_system_prompt(use_case) or "").strip()
        except Exception:  # noqa: BLE001
            return None
        return default_prompt or None

    def update_v2_session_config(
        self,
        session_id: str,
        *,
        country: str | None = None,
        use_case: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        guiding_prompt: str | None = None,
        analysis_questions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        existing_cfg = self._read_session_config(session_id)
        resolved_model_api_key: str | None = None

        patch: dict[str, Any] = {}
        config_service = ConfigService(self.settings)

        if country is not None:
            country_payload = config_service.get_country(country)
            patch["country"] = str(country_payload.get("code") or country).strip().lower()
            self.country_datasets.ensure_country_ready(patch["country"])

        if use_case is not None:
            use_case_payload = config_service.get_use_case(use_case)
            resolved_use_case = str(use_case_payload.get("code", use_case)).strip().lower()
            patch["use_case"] = resolved_use_case
            if guiding_prompt is None and not self._read_session_config(session_id).get("guiding_prompt"):
                default_prompt = str(config_service.get_system_prompt(resolved_use_case) or "").strip()
                if default_prompt:
                    patch["guiding_prompt"] = default_prompt
            if analysis_questions is None:
                patch["analysis_questions"] = [
                    item
                    for item in config_service.get_analysis_questions(resolved_use_case)
                    if isinstance(item, dict)
                ]

        if provider is not None:
            patch["provider"] = "gemini" if normalize_provider(provider) == "google" else normalize_provider(provider)
        if model is not None:
            patch["model"] = str(model).strip()
        if guiding_prompt is not None:
            patch["guiding_prompt"] = str(guiding_prompt).strip() or None
        if analysis_questions is not None:
            patch["analysis_questions"] = [item for item in analysis_questions if isinstance(item, dict)]

        if provider is not None or model is not None or api_key is not None:
            resolved_provider = normalize_provider(provider or session.get("model_provider"))
            resolved_model_api_key = self._resolve_session_api_key(
                session,
                provider=resolved_provider,
                api_key=api_key,
            )

        merged_cfg = self._upsert_session_config(session_id, patch)

        existing_questions = [item for item in (existing_cfg.get("analysis_questions") or []) if isinstance(item, dict)]
        merged_questions = [item for item in (merged_cfg.get("analysis_questions") or []) if isinstance(item, dict)]
        knowledge_scope_changed = any(
            merged_cfg.get(field) != existing_cfg.get(field)
            for field in ("country", "use_case", "guiding_prompt")
        )
        analysis_questions_changed = existing_questions != merged_questions
        if knowledge_scope_changed:
            self._clear_knowledge_downstream_artifacts(session_id)
        elif analysis_questions_changed:
            self._clear_population_downstream_artifacts(session_id)

        if provider is not None or model is not None or api_key is not None:
            resolved_provider = normalize_provider(provider or session.get("model_provider"))
            resolved_model = str(model or session.get("model_name") or "").strip()
            if not resolved_model:
                resolved_model = self.settings.default_model_for_provider(resolved_provider)
            self.update_session_model_config(
                session_id,
                model_provider=resolved_provider,
                model_name=resolved_model,
                api_key=resolved_model_api_key,
            )

        model_payload = self._session_model_payload(session_id)
        return {
            "session_id": session_id,
            "country": merged_cfg.get("country"),
            "use_case": merged_cfg.get("use_case"),
            "provider": "gemini" if model_payload["model_provider"] == "google" else model_payload["model_provider"],
            "model": model_payload["model_name"],
            "api_key_configured": bool(model_payload["api_key_configured"]),
            "guiding_prompt": merged_cfg.get("guiding_prompt"),
            "analysis_questions": [
                item
                for item in (merged_cfg.get("analysis_questions") or [])
                if isinstance(item, dict)
            ],
        }

    def create_v2_session(
        self,
        *,
        country: str,
        use_case: str,
        provider: str,
        model: str,
        api_key: str | None = None,
        mode: str = "live",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        config = ConfigService(self.settings)
        resolved_provider = normalize_provider(provider)
        resolved_api_key = self._resolve_session_api_key(None, provider=resolved_provider, api_key=api_key)
        country_payload = config.get_country(country)
        selected_country = str(country_payload.get("code") or country).strip().lower()
        self.country_datasets.ensure_country_ready(selected_country)
        _ = config.get_use_case(use_case)

        payload = self.create_session(
            requested_session_id=session_id,
            mode=mode,
            model_provider=resolved_provider,
            model_name=model,
            api_key=resolved_api_key,
        )
        use_case_payload = config.get_use_case(use_case)
        stored_prompt = str(config.get_system_prompt(str(use_case_payload.get("code", use_case))) or "").strip() or None
        analysis_questions = [
            item
            for item in config.get_analysis_questions(str(use_case_payload.get("code", use_case)))
            if isinstance(item, dict)
        ]
        if mode == "demo" and self.demo.is_demo_available():
            demo_questions = self.demo.get_analysis_questions()
            if demo_questions:
                analysis_questions = demo_questions
        self._upsert_session_config(
            payload["session_id"],
            {
                "country": selected_country,
                "use_case": str(use_case_payload.get("code", use_case)).strip().lower(),
                "provider": "gemini" if resolved_provider == "google" else resolved_provider,
                "model": model,
                "guiding_prompt": stored_prompt,
                "analysis_questions": analysis_questions,
            },
        )
        return {"session_id": payload["session_id"]}

    def list_provider_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_provider(provider)
        from miroworld.services.model_provider_service import list_models_for_provider

        models = list_models_for_provider(
            self.settings,
            provider=normalized,
            api_key=api_key,
            base_url=base_url,
        )
        return {
            "provider": normalized,
            "models": models,
        }

    def get_dynamic_filters(self, session_id: str) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        session_cfg = self._read_session_config(session_id)
        country = str(session_cfg.get("country") or "singapore").strip().lower()
        use_case = str(session_cfg.get("use_case") or "").strip().lower() or None
        config_service = ConfigService(self.settings)
        country_cfg = config_service.get_country(country)
        filter_fields = list(country_cfg.get("filter_fields") or [])
        live_mode = self._is_live_session(session_id)

        try:
            dataset_path = self.country_datasets.ensure_country_ready(country)
            schema_rows = self.sampler.infer_filter_schema(
                dataset_path=dataset_path,
                filter_fields=filter_fields,
            )
        except HTTPException as exc:
            if live_mode:
                raise exc
            schema_rows = self._fallback_dynamic_filters(country_cfg, filter_fields)
        return {
            "session_id": session_id,
            "country": country,
            "use_case": use_case,
            "filters": schema_rows,
        }

    def _fallback_dynamic_filters(self, country_cfg: dict[str, Any], filter_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fallback_rows: list[dict[str, Any]] = []
        for field_cfg in filter_fields:
            field_name = str(field_cfg.get("field", "")).strip()
            filter_type = str(field_cfg.get("type", "")).strip()
            label = str(field_cfg.get("label", field_name)).strip() or field_name
            if not field_name or not filter_type:
                continue

            payload: dict[str, Any] = {
                "field": field_name,
                "type": filter_type,
                "label": label,
            }
            if filter_type == "range":
                if "default_min" in field_cfg:
                    payload["default_min"] = field_cfg.get("default_min")
                if "default_max" in field_cfg:
                    payload["default_max"] = field_cfg.get("default_max")
                payload["min"] = field_cfg.get("default_min", 0)
                payload["max"] = field_cfg.get("default_max", 100)
            else:
                payload["options"] = self._fallback_filter_options(country_cfg, field_name, field_cfg)
                if "default" in field_cfg:
                    payload["default"] = field_cfg.get("default")
            fallback_rows.append(payload)
        return fallback_rows

    def _fallback_filter_options(self, country_cfg: dict[str, Any], field_name: str, field_cfg: dict[str, Any]) -> list[str]:
        explicit_options = field_cfg.get("options")
        if isinstance(explicit_options, list) and explicit_options:
            return [str(option) for option in explicit_options if str(option).strip()]

        normalized = str(field_name).strip().lower()
        if normalized == self.country_metadata.geography_field(country_cfg):
            return self.country_metadata.geography_options(country_cfg)
        if normalized == "occupation":
            return list(OCCUPATION_NAMES)
        if normalized in {"sex", "gender"}:
            return ["Male", "Female"]
        if normalized == "ethnicity":
            return ["Asian", "Black", "Hispanic", "White", "Other"]
        return []

    def estimate_token_usage(self, session_id: str, *, agents: int, rounds: int) -> dict[str, Any]:
        model_payload = self._session_model_payload(session_id)
        tracker = TokenTracker(model=str(model_payload.get("model_name") or "gemini-2.0-flash"))
        return tracker.estimate_cost(agent_count=agents, rounds=rounds)

    def record_runtime_token_usage(
        self,
        session_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> None:
        model_payload = self._session_model_payload(session_id)
        model_name = str(model_payload.get("model_name") or "gemini-2.0-flash")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT total_input_tokens, total_output_tokens, total_cached_tokens, model
                FROM session_token_usage
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row:
                new_input = int(row["total_input_tokens"]) + max(0, int(input_tokens))
                new_output = int(row["total_output_tokens"]) + max(0, int(output_tokens))
                new_cached = int(row["total_cached_tokens"]) + max(0, int(cached_tokens))
                model_name = str(row["model"] or model_name)
            else:
                new_input = max(0, int(input_tokens))
                new_output = max(0, int(output_tokens))
                new_cached = max(0, int(cached_tokens))

            conn.execute(
                """
                INSERT INTO session_token_usage(
                    session_id,
                    model,
                    total_input_tokens,
                    total_output_tokens,
                    total_cached_tokens
                )
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    model=excluded.model,
                    total_input_tokens=excluded.total_input_tokens,
                    total_output_tokens=excluded.total_output_tokens,
                    total_cached_tokens=excluded.total_cached_tokens,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (session_id, model_name, new_input, new_output, new_cached),
            )

    def get_runtime_token_usage(self, session_id: str) -> dict[str, Any]:
        model_payload = self._session_model_payload(session_id)
        model_name = str(model_payload.get("model_name") or "gemini-2.0-flash")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT total_input_tokens, total_output_tokens, total_cached_tokens, model
                FROM session_token_usage
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        tracker = TokenTracker(model=str(row["model"]) if row and row["model"] else model_name)
        if row:
            tracker.record(
                input_tokens=int(row["total_input_tokens"]),
                output_tokens=int(row["total_output_tokens"]),
                cached_tokens=int(row["total_cached_tokens"]),
            )
        return tracker.get_summary()

    def get_session_model_config(self, session_id: str) -> dict[str, Any]:
        return self._session_model_payload(session_id)

    def update_session_model_config(
        self,
        session_id: str,
        *,
        model_provider: str,
        model_name: str,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        selection = resolve_model_selection(
            self.settings,
            provider=model_provider,
            model_name=model_name,
            embed_model_name=embed_model_name,
            api_key=self._resolve_session_api_key(session, provider=model_provider, api_key=api_key),
            base_url=base_url,
            allow_provider_env_key_fallback=False,
        )
        if selection.provider == "ollama":
            ensure_ollama_models_available(self.settings, selection)

        self.store.upsert_console_session(
            session_id=session_id,
            mode=session.get("mode", "demo"),
            status=session.get("status", "created"),
            model_provider=selection.provider,
            model_name=selection.model_name,
            embed_model_name=selection.embed_model_name,
            api_key=selection.api_key,
            base_url=selection.base_url,
        )
        return self._session_model_payload(session_id)

    def create_session(
        self,
        requested_session_id: str | None = None,
        mode: str = "demo",
        *,
        model_provider: str | None = None,
        model_name: str | None = None,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        session_id = requested_session_id or f"session-{uuid.uuid4().hex[:8]}"
        selection = resolve_model_selection(
            self.settings,
            provider=model_provider,
            model_name=model_name,
            embed_model_name=embed_model_name,
            api_key=self._resolve_session_api_key(None, provider=model_provider or self.settings.llm_provider, api_key=api_key),
            base_url=base_url,
            allow_provider_env_key_fallback=False,
        )
        if selection.provider == "ollama" and mode == "live":
            try:
                ensure_ollama_models_available(self.settings, selection)
            except Exception as exc:  # noqa: BLE001
                detail = self._format_runtime_failure_detail(
                    session_id,
                    exc,
                    action="Session creation",
                )
                raise HTTPException(status_code=502, detail=detail) from exc

        # If demo mode and demo cache is available, use demo service.
        if mode == "demo" and self.demo.is_demo_available():
            demo_payload = self.demo.create_demo_session(requested_session_id)
            session_id = str(demo_payload["session_id"])
            self.store.upsert_console_session(
                session_id=session_id,
                mode=mode,
                status=str(demo_payload.get("status", "created")),
                model_provider=selection.provider,
                model_name=selection.model_name,
                embed_model_name=selection.embed_model_name,
                api_key=selection.api_key,
                base_url=selection.base_url,
            )
            return {
                **demo_payload,
                "model_provider": selection.provider,
                "model_name": selection.model_name,
                "embed_model_name": selection.embed_model_name,
                "base_url": selection.base_url,
                "api_key_configured": selection.api_key_configured,
                "api_key_masked": mask_api_key(selection.api_key),
            }

        self.store.upsert_console_session(
            session_id=session_id,
            mode=mode,
            status="created",
            model_provider=selection.provider,
            model_name=selection.model_name,
            embed_model_name=selection.embed_model_name,
            api_key=selection.api_key,
            base_url=selection.base_url,
        )
        return {
            "session_id": session_id,
            "mode": mode,
            "status": "created",
            "model_provider": selection.provider,
            "model_name": selection.model_name,
            "embed_model_name": selection.embed_model_name,
            "base_url": selection.base_url,
            "api_key_configured": selection.api_key_configured,
            "api_key_masked": mask_api_key(selection.api_key),
        }

    async def process_knowledge(
        self,
        session_id: str,
        *,
        document_text: str | None = None,
        source_path: str | None = None,
        documents: list[dict[str, str | None]] | None = None,
        guiding_prompt: str | None = None,
        demographic_focus: str | None = None,
        use_default_demo_document: bool = False,
    ) -> dict[str, Any]:
        session = self.store.get_console_session(session_id)
        if not session:
            self.create_session(session_id)
            session = self.store.get_console_session(session_id)
        resolved_guiding_prompt = self._resolve_guiding_prompt(session_id, guiding_prompt)
        live_mode = self._is_live_session(session_id)
        resolved_documents = self._resolve_knowledge_documents(
            document_text=document_text,
            source_path=source_path,
            documents=documents or [],
            use_default_demo_document=use_default_demo_document,
        )
        if not resolved_documents:
            raise HTTPException(
                status_code=422,
                detail="Provide document_text/documents or set use_default_demo_document=true.",
            )

        self._clear_knowledge_downstream_artifacts(session_id)
        self.knowledge_streams.append_events(
            session_id,
            [
                {
                    "event_type": "knowledge_started",
                    "session_id": session_id,
                    "document_count": len(resolved_documents),
                }
            ],
        )

        runtime_settings = self._runtime_settings_for_session(session_id)
        unavailable_model_hint = provider_model_unavailability_hint(
            runtime_settings.llm_provider,
            runtime_settings.llm_model,
        )
        if unavailable_model_hint:
            detail = self._format_runtime_failure_detail(
                session_id,
                RuntimeError(unavailable_model_hint),
                action="Screen 1 knowledge extraction",
            )
            raise HTTPException(status_code=502, detail=detail)
        lightrag = LightRAGService(runtime_settings)
        try:
            artifacts: list[dict[str, Any]] = []
            for index, item in enumerate(resolved_documents, start=1):
                document_id = f"doc-{uuid.uuid4()}"
                self.knowledge_streams.append_events(
                    session_id,
                    [
                        {
                            "event_type": "knowledge_document_started",
                            "session_id": session_id,
                            "document_id": document_id,
                            "document_index": index,
                            "document_count": len(resolved_documents),
                            "source_path": item.get("source_path"),
                        }
                    ],
                )

                async def emit_knowledge_event(event_type: str, payload: dict[str, Any]) -> None:
                    self.knowledge_streams.append_events(
                        session_id,
                        [
                            {
                                "event_type": event_type,
                                "session_id": session_id,
                                "document_index": index,
                                "document_count": len(resolved_documents),
                                **payload,
                            }
                        ],
                    )

                artifact = await lightrag.process_document(
                    simulation_id=session_id,
                    document_text=str(item.get("document_text") or ""),
                    source_path=str(item.get("source_path")) if item.get("source_path") else None,
                    document_id=document_id,
                    guiding_prompt=resolved_guiding_prompt,
                    demographic_focus=demographic_focus,
                    live_mode=live_mode,
                    event_callback=emit_knowledge_event,
                )
                artifacts.append(artifact)
        except HTTPException as exc:
            failure_detail = str(exc.detail).strip() or "Knowledge extraction failed."
            self.knowledge_streams.append_events(
                session_id,
                [
                    {
                        "event_type": "knowledge_failed",
                        "session_id": session_id,
                        "detail": failure_detail,
                    }
                ],
            )
            raise
        except Exception as exc:  # noqa: BLE001
            self.knowledge_streams.append_events(
                session_id,
                [
                    {
                        "event_type": "knowledge_failed",
                        "session_id": session_id,
                        "detail": str(exc).strip() or exc.__class__.__name__,
                    }
                ],
            )
            detail = self._format_runtime_failure_detail(
                session_id,
                exc,
                action="Screen 1 knowledge extraction",
            )
            raise HTTPException(status_code=502, detail=detail) from exc

        artifact = self._merge_knowledge_artifacts(
            session_id,
            artifacts=artifacts,
            guiding_prompt=resolved_guiding_prompt,
            demographic_focus=demographic_focus,
        )
        self.store.save_knowledge_artifact(session_id, artifact)
        self.store.upsert_console_session(session_id=session_id, mode=session.get("mode", "demo") if session else "demo", status="knowledge_ready")
        self.knowledge_streams.append_events(
            session_id,
            [
                {
                    "event_type": "knowledge_completed",
                    "session_id": session_id,
                    "document_count": len(resolved_documents),
                    "total_nodes": len(artifact.get("entity_nodes", [])),
                    "total_edges": len(artifact.get("relationship_edges", [])),
                }
            ],
        )
        return artifact

    async def process_uploaded_knowledge(
        self,
        session_id: str,
        *,
        upload: UploadFile,
        guiding_prompt: str | None = None,
        demographic_focus: str | None = None,
    ) -> dict[str, Any]:
        filename = upload.filename or "uploaded-document"
        payload = await upload.read()
        if not payload:
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")

        upload_dir = Path(self.settings.console_upload_dir)
        if not upload_dir.is_absolute():
            upload_dir = Path.cwd() / upload_dir
        session_dir = upload_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        stored_path = session_dir / filename
        stored_path.write_bytes(payload)

        try:
            document_text = extract_document_text(filename, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return await self.process_knowledge(
            session_id,
            document_text=document_text,
            source_path=str(stored_path),
            guiding_prompt=guiding_prompt,
            demographic_focus=demographic_focus,
        )

    def _resolve_knowledge_documents(
        self,
        *,
        document_text: str | None,
        source_path: str | None,
        documents: list[dict[str, str | None]],
        use_default_demo_document: bool,
    ) -> list[dict[str, str | None]]:
        resolved: list[dict[str, str | None]] = []

        if document_text:
            resolved.append(
                {
                    "document_text": str(document_text),
                    "source_path": source_path,
                }
            )

        for item in documents:
            if not isinstance(item, dict):
                continue
            text = str(item.get("document_text") or "").strip()
            if not text:
                continue
            resolved.append(
                {
                    "document_text": text,
                    "source_path": str(item.get("source_path") or "").strip() or None,
                }
            )

        if not resolved and use_default_demo_document:
            path = Path(self.settings.demo_default_policy_markdown)
            if not path.exists():
                path = Path("..") / self.settings.demo_default_policy_markdown
            if path.exists():
                resolved.append(
                    {
                        "document_text": path.read_text(encoding="utf-8"),
                        "source_path": str(path),
                    }
                )

        return resolved

    def _merge_knowledge_artifacts(
        self,
        session_id: str,
        *,
        artifacts: list[dict[str, Any]],
        guiding_prompt: str | None,
        demographic_focus: str | None,
    ) -> dict[str, Any]:
        if not artifacts:
            raise HTTPException(status_code=422, detail="No documents were processed for knowledge extraction.")

        if len(artifacts) == 1:
            merged = dict(artifacts[0])
            merged["session_id"] = session_id
            merged["guiding_prompt"] = guiding_prompt
            return merged

        summaries: list[str] = []
        entity_nodes: list[dict[str, Any]] = []
        relationship_edges: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        processing_logs: list[str] = []
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str, str]] = set()

        for artifact in artifacts:
            summary = str(artifact.get("summary") or "").strip()
            if summary:
                summaries.append(summary)

            doc = dict(artifact.get("document") or {})
            documents.append(doc)

            for node in artifact.get("entity_nodes", []):
                if not isinstance(node, dict):
                    continue
                node_id = str(node.get("id") or node.get("label") or "").strip().lower()
                if not node_id or node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                entity_nodes.append(node)

            for edge in artifact.get("relationship_edges", []):
                if not isinstance(edge, dict):
                    continue
                edge_key = (
                    str(edge.get("source") or "").strip().lower(),
                    str(edge.get("target") or "").strip().lower(),
                    str(edge.get("type") or "").strip().lower(),
                    str(edge.get("label") or "").strip().lower(),
                )
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                relationship_edges.append(edge)

            for log_line in artifact.get("processing_logs", []):
                text = str(log_line).strip()
                if text:
                    processing_logs.append(text)

        paragraph_count = sum(int(doc.get("paragraph_count") or 0) for doc in documents)
        text_length = sum(int(doc.get("text_length") or 0) for doc in documents)
        entity_type_counts = dict(Counter(str(node.get("type", "unknown")) for node in entity_nodes))

        merged_document = {
            "document_id": f"merged-{len(documents)}-documents",
            "source_path": "merged://knowledge-documents",
            "source_count": len(documents),
            "sources": documents,
            "text_length": text_length,
            "paragraph_count": paragraph_count,
        }
        return {
            "session_id": session_id,
            "document": merged_document,
            "summary": "\n\n".join(summaries),
            "guiding_prompt": guiding_prompt,
            "entity_nodes": entity_nodes,
            "relationship_edges": relationship_edges,
            "entity_type_counts": entity_type_counts,
            "processing_logs": processing_logs,
            "demographic_focus_summary": demographic_focus,
        }

    def preview_population(self, session_id: str, request: Any) -> dict[str, Any]:
        knowledge = self.store.get_knowledge_artifact(session_id)
        if not knowledge:
            knowledge_state = self.knowledge_streams.get_state(session_id)
            if str(knowledge_state.get("status") or "").strip().lower() == "failed":
                detail = str(knowledge_state.get("last_error") or "").strip()
                if detail:
                    raise HTTPException(status_code=502, detail=detail)
            raise HTTPException(status_code=404, detail=f"Knowledge artifact not found for session {session_id}")

        self._clear_population_downstream_artifacts(session_id)
        country, country_cfg, dataset_path = self._session_country_config(session_id)
        country_aliases = [
            country,
            str(country_cfg.get("code") or "").strip().lower(),
            str(country_cfg.get("name") or "").strip(),
        ]
        runtime_settings = self._runtime_settings_for_session(session_id)
        relevance = PersonaRelevanceService(runtime_settings)
        live_mode = self._is_live_session(session_id)

        try:
            parsed_instructions = relevance.parse_sampling_instructions(
                request.sampling_instructions,
                knowledge_artifact=knowledge,
                live_mode=live_mode,
                country=country,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            detail = self._format_runtime_failure_detail(
                session_id,
                exc,
                action="Screen 2 agent sampling",
            )
            raise HTTPException(status_code=502, detail=detail) from exc
        effective_seed = int(request.seed if request.seed is not None else random.randint(1, 2_147_483_647))
        if request.sample_mode == "population_baseline":
            candidate_limit = min(
                max(request.agent_count * 3, MIN_BASELINE_CANDIDATES),
                MAX_BASELINE_CANDIDATES,
            )
        else:
            candidate_limit = min(
                max(request.agent_count * 2, MIN_AFFECTED_GROUPS_CANDIDATES),
                MAX_AFFECTED_GROUPS_CANDIDATES,
            )
        merged_filters = self._merge_population_filters(request, parsed_instructions, country=country)
        personas = self.sampler.query_candidates(
            limit=candidate_limit,
            seed=effective_seed,
            dataset_path=dataset_path,
            country_values=country_aliases,
            geography_field=merged_filters["geography_field"],
            geography_values=merged_filters["geography_values"],
            min_age=merged_filters["min_age"],
            max_age=merged_filters["max_age"],
            sexes=merged_filters["sexes"],
            marital_statuses=merged_filters["marital_statuses"],
            education_levels=merged_filters["education_levels"],
            occupations=merged_filters["occupations"],
            industries=merged_filters["industries"],
            extra_filters=merged_filters["dynamic_filters"],
        )
        if not personas:
            raise HTTPException(status_code=422, detail="No personas matched the current sampling configuration.")

        artifact = relevance.build_population_artifact(
            session_id,
            personas=personas,
            knowledge_artifact=knowledge,
            filters={
                **request.model_dump(),
                **merged_filters,
            },
            agent_count=request.agent_count,
            sample_mode=request.sample_mode,
            seed=effective_seed,
            parsed_sampling_instructions=parsed_instructions,
            live_mode=live_mode,
            country=country,
        )
        self.store.save_population_artifact(session_id, artifact)
        return artifact

    def start_simulation(
        self,
        session_id: str,
        *,
        policy_summary: str,
        rounds: int,
        controversy_boost: float = 0.0,
        mode: str | None = None,
    ) -> dict[str, Any]:
        session = self.store.get_console_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        runtime_settings = self._runtime_settings_for_session(session_id)
        effective_mode = mode or session.get("mode", "demo")

        population = self.store.get_population_artifact(session_id)
        if not population:
            raise HTTPException(status_code=404, detail=f"Population artifact not found: {session_id}")

        sampled_rows = list(population.get("sampled_personas", []))
        personas = [dict(row["persona"], agent_id=row.get("agent_id")) for row in sampled_rows]
        if not sampled_rows:
            raise HTTPException(status_code=422, detail="No sampled personas available for simulation start")

        events_dir = Path(runtime_settings.oasis_db_dir).parent / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_path = events_dir / f"{session_id}.ndjson"
        if events_path.exists():
            events_path.unlink()

        self.store.clear_simulation_events(session_id)
        self.store.clear_simulation_state_snapshot(session_id)
        self.store.clear_report_cache(session_id)
        self.store.clear_report_state(session_id)
        self.store.clear_checkpoint_records(session_id)
        self.store.clear_interaction_transcripts(session_id)
        self.store.reset_memory_sync_state(session_id)
        initial_estimate = self._estimate_initial_runtime(
            agent_count=len(sampled_rows),
            rounds=rounds,
            provider=runtime_settings.llm_provider,
        )
        self.store.save_simulation_state_snapshot(
            session_id,
            {
                "session_id": session_id,
                "status": "running",
                "platform": runtime_settings.simulation_platform,
                "planned_rounds": rounds,
                "event_count": 0,
                "last_round": 0,
                "current_round": 0,
                "elapsed_seconds": 0,
                "estimated_total_seconds": initial_estimate,
                "estimated_remaining_seconds": initial_estimate,
                "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                "checkpoint_status": {
                    "baseline": {"status": "pending", "completed_agents": 0, "total_agents": len(sampled_rows)},
                    "final": {"status": "pending", "completed_agents": 0, "total_agents": len(sampled_rows)},
                },
                "top_threads": [],
                "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
                "latest_metrics": {},
                "recent_events": [],
                "events_path": str(events_path),
                "stream_offset_bytes": 0,
            },
        )
        self.store.upsert_console_session(session_id=session_id, mode=effective_mode, status="simulation_running")

        thread = threading.Thread(
            target=self._run_simulation_background,
            args=(
                session_id,
                policy_summary,
                rounds,
                sampled_rows,
                personas,
                events_path,
                effective_mode,
                max(0.0, min(1.0, float(controversy_boost))),
            ),
            daemon=True,
        )
        thread.start()
        return self.streams.get_state(session_id)

    def get_simulation_state(self, session_id: str) -> dict[str, Any]:
        return self.streams.get_state(session_id)

    def _is_demo_session(self, session_id: str) -> bool:
        """Check if this is a demo session."""
        session = self.store.get_console_session(session_id)
        return session is not None and session.get("mode") == "demo"

    def generate_v2_report(self, session_id: str) -> dict[str, Any]:
        payload = self.get_v2_report(session_id)
        if not payload.get("status"):
            payload["status"] = "completed"
        return payload

    def get_v2_report(self, session_id: str) -> dict[str, Any]:
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            demo_report = self.demo.get_report(session_id)
            if self._is_cached_v2_report_payload(demo_report):
                demo_report.setdefault("status", "completed")
                self.store.save_report_state(session_id, demo_report)
                return demo_report

        cached = self.store.get_report_state(session_id)
        if isinstance(cached, dict) and self._is_cached_v2_report_payload(cached):
            cached.setdefault("status", "completed")
            return cached

        runtime_settings = self._runtime_settings_for_session(session_id)
        report_service = ReportService(runtime_settings)
        session_cfg = self._read_session_config(session_id)
        use_case = str(session_cfg.get("use_case") or "").strip() or None
        payload = report_service.build_v2_report(session_id, use_case=use_case)
        payload.setdefault("status", "completed")
        self.store.save_report_state(session_id, payload)
        return payload

    def _is_cached_v2_report_payload(self, payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        if not str(payload.get("session_id") or "").strip():
            return False
        required_lists = (
            payload.get("metric_deltas"),
            payload.get("sections"),
            payload.get("insight_blocks"),
            payload.get("preset_sections"),
        )
        if not all(isinstance(value, list) for value in required_lists):
            return False

        sections = payload.get("sections") or []
        if any(not isinstance(section, dict) or not isinstance(section.get("bullets"), list) for section in sections):
            return False

        preset_sections = payload.get("preset_sections") or []
        if any(not isinstance(section, dict) or not isinstance(section.get("bullets"), list) for section in preset_sections):
            return False

        return True

    def get_session_analysis_questions(self, session_id: str) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        session_cfg = self._read_session_config(session_id)
        use_case = str(session_cfg.get("use_case") or "").strip().lower()
        questions = [
            item
            for item in (session_cfg.get("analysis_questions") or [])
            if isinstance(item, dict)
        ]
        if not questions and use_case:
            config_service = ConfigService(self.settings)
            try:
                questions = config_service.get_analysis_questions(use_case)
            except Exception:  # noqa: BLE001
                questions = []
        return {
            "session_id": session_id,
            "use_case": use_case or "public-policy-testing",
            "questions": questions,
        }

    def export_v2_report_docx(self, session_id: str) -> tuple[str, bytes]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        report_service = ReportService(runtime_settings)
        session_cfg = self._read_session_config(session_id)
        use_case = str(session_cfg.get("use_case") or "").strip() or None
        report_payload = self.get_v2_report(session_id)
        docx_bytes = report_service.export_v2_report_docx(session_id, report=report_payload, use_case=use_case)
        return (f"miroworld-{session_id}-report.docx", docx_bytes)

    def group_chat(self, session_id: str, segment: str, message: str, top_n: int = 5, metric_name: str | None = None) -> dict[str, Any]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        memory_service = MemoryService(runtime_settings)
        segment_key, selected, _agents_enriched, _score_field = self._select_group_chat_agents(
            session_id,
            segment=segment,
            top_n=top_n,
            metric_name=metric_name,
        )

        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            if not selected:
                selected = [
                    {
                        "agent_id": str(row.get("agent_id") or ""),
                        "influence_score": float(row.get("influence_score", 0.0) or 0.0),
                    }
                    for row in self._agents_for_metrics(session_id)[: max(1, int(top_n))]
                ]

            responses: list[dict[str, Any]] = []
            for row in selected[: max(1, int(top_n))]:
                agent_id = str(row.get("agent_id") or "")
                if not agent_id:
                    continue
                payload = self.demo.generate_demo_agent_chat(session_id, agent_id, message)
                response_item = {
                    "agent_id": agent_id,
                    "response": payload.get("response", ""),
                    "influence_score": row.get("influence_score", 0.0),
                    "memory_used": False,
                    "zep_context_used": bool(payload.get("zep_context_used", False)),
                    "graphiti_context_used": False,
                    "memory_backend": "demo",
                }
                responses.append(response_item)
                self.store.append_interaction_transcript(session_id, "group_chat", "assistant", response_item["response"], agent_id=agent_id)

            self.store.append_interaction_transcript(session_id, "group_chat", "user", message)
            return {
                "session_id": session_id,
                "segment": segment_key,
                "responses": responses,
            }

        if not selected:
            notice = {
                "agent_id": "system",
                "response": f"No agents were classified as {segment_key} in this simulation run.",
                "influence_score": 0.0,
                "memory_used": False,
                "zep_context_used": False,
                "graphiti_context_used": False,
                "memory_backend": "system",
            }
            self.store.append_interaction_transcript(session_id, "group_chat", "user", message)
            self.store.append_interaction_transcript(session_id, "group_chat", "assistant", notice["response"], agent_id="system")
            return {
                "session_id": session_id,
                "segment": segment_key,
                "responses": [notice],
            }

        responses: list[dict[str, Any]] = []
        failed_agents: list[tuple[str, str]] = []
        for row in selected:
            agent_id = str(row.get("agent_id") or "")
            if not agent_id:
                continue
            try:
                payload = memory_service.agent_chat_realtime(
                    session_id,
                    agent_id,
                    message,
                    live_mode=self._is_live_session(session_id),
                )
            except Exception as exc:  # noqa: BLE001
                failed_agents.append((agent_id, str(exc).strip() or exc.__class__.__name__))
                continue
            response_item = {
                "agent_id": agent_id,
                "response": payload.get("response", ""),
                "influence_score": row.get("influence_score", 0.0),
                "memory_used": bool(payload.get("memory_used", False)),
                "zep_context_used": bool(payload.get("zep_context_used", False)),
                "graphiti_context_used": bool(payload.get("graphiti_context_used", False)),
                "memory_backend": payload.get("memory_backend", "sqlite"),
            }
            responses.append(response_item)
            self.store.append_interaction_transcript(session_id, "group_chat", "assistant", response_item["response"], agent_id=agent_id)

        if not responses:
            if failed_agents:
                detail = "; ".join(
                    f"{agent_id}: {reason}"
                    for agent_id, reason in failed_agents[:3]
                )
                raise RuntimeError(
                    self._format_runtime_failure_detail(
                        session_id,
                        RuntimeError(detail),
                        action="Group chat",
                    )
                )
            raise RuntimeError("Group chat failed because no eligible agents produced a response.")

        if failed_agents:
            unavailable = ", ".join(agent_id for agent_id, _reason in failed_agents[:5])
            responses.append(
                {
                    "agent_id": "system",
                    "response": (
                        f"Some agents were temporarily unavailable during this reply: {unavailable}. "
                        "Showing responses from agents that succeeded."
                    ),
                    "influence_score": 0.0,
                    "memory_used": False,
                    "zep_context_used": False,
                    "graphiti_context_used": False,
                    "memory_backend": "system",
                }
            )

        self.store.append_interaction_transcript(session_id, "group_chat", "user", message)
        return {
            "session_id": session_id,
            "segment": segment_key,
            "responses": responses,
        }

    def get_group_chat_candidates(
        self,
        session_id: str,
        segment: str,
        top_n: int = 5,
        metric_name: str | None = None,
    ) -> dict[str, Any]:
        segment_key, selected, _agents_enriched, score_field = self._select_group_chat_agents(
            session_id,
            segment=segment,
            top_n=top_n,
            metric_name=metric_name,
        )
        return {
            "session_id": session_id,
            "segment": segment_key,
            "metric_name": metric_name,
            "score_field": score_field,
            "agents": selected,
        }

    def _normalize_group_chat_segment(self, segment: str) -> str:
        segment_key = str(segment).strip().lower()
        alias_map = {
            "supporters": "supporter",
            "dissenters": "dissenter",
        }
        return alias_map.get(segment_key, segment_key)

    def _select_group_chat_agents(
        self,
        session_id: str,
        *,
        segment: str,
        top_n: int = 5,
        metric_name: str | None = None,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        config_service = ConfigService(runtime_settings)
        metrics = MetricsService(config_service)

        segment_key = self._normalize_group_chat_segment(segment)
        if not metric_name and segment_key in {"dissenter", "supporter"}:
            agents_enriched, score_field = self._agents_with_aggregate_extreme_scores(session_id, segment_key)
        else:
            agents_enriched, score_field = self._agents_with_checkpoint_metrics(session_id, metric_name)

        selected = metrics.select_group_chat_agents(
            agents=agents_enriched,
            interactions=self.store.get_interactions(session_id),
            segment=segment_key,
            top_n=max(1, int(top_n)),
            score_field=score_field,
        )
        agent_lookup = {
            str(agent.get("agent_id") or agent.get("id") or ""): agent
            for agent in agents_enriched
        }
        selected_with_names: list[dict[str, Any]] = []
        for row in selected:
            agent_id = str(row.get("agent_id") or "")
            if not agent_id:
                continue
            agent = agent_lookup.get(agent_id) or {}
            selected_with_names.append(
                {
                    **row,
                    "agent_name": self._group_chat_agent_name(agent, agent_id),
                    "score": agent.get(score_field),
                }
            )
        return segment_key, selected_with_names, agents_enriched, score_field

    @staticmethod
    def _group_chat_agent_name(agent: dict[str, Any], fallback: str) -> str:
        for key in ("name", "agent_name", "display_name", "confirmed_name"):
            value = str(agent.get(key) or "").strip()
            if value:
                return value
        persona = agent.get("persona")
        if isinstance(persona, dict):
            for key in ("name", "display_name", "confirmed_name", "agent_name", "occupation"):
                value = str(persona.get(key) or "").strip()
                if value:
                    return value
        return fallback

    def _knowledge_context_excerpt(self, session_id: str) -> str:
        knowledge = self.store.get_knowledge_artifact(session_id) or {}
        lines: list[str] = []
        summary = str(knowledge.get("summary") or "").strip()
        if summary:
            lines.append(f"Document summary: {summary}")

        document = knowledge.get("document")
        if isinstance(document, dict):
            source_path = str(document.get("source_path") or "").strip()
            if source_path:
                lines.append(f"Source document: {source_path}")
            text_length = document.get("text_length")
            if text_length is not None:
                lines.append(f"Document length: {text_length}")
            sources = document.get("sources")
            if isinstance(sources, list):
                for source in sources[:3]:
                    if not isinstance(source, dict):
                        continue
                    source_path = str(source.get("source_path") or "").strip()
                    if source_path:
                        lines.append(f"Document source: {source_path}")

        return "\n".join(lines)

    def agent_chat_v2(self, session_id: str, agent_id: str, message: str) -> dict[str, Any]:
        context_excerpt = self._knowledge_context_excerpt(session_id)
        augmented_message = (
            f"{message}\n\nOriginal document context:\n{context_excerpt}"
            if context_excerpt
            else message
        )
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            model_payload = self._session_model_payload(session_id)
            demo_payload = self.demo.generate_demo_agent_chat(session_id, agent_id, augmented_message)
            payload = {
                **demo_payload,
                "session_id": session_id,
                "agent_id": agent_id,
                "memory_used": False,
                "model_provider": model_payload["model_provider"],
                "model_name": model_payload["model_name"],
                "gemini_model": model_payload["model_name"],
                "zep_context_used": bool(demo_payload.get("zep_context_used", False)),
                "graphiti_context_used": False,
                "memory_backend": "demo",
            }
            self.store.append_interaction_transcript(session_id, "agent_chat", "user", message, agent_id=agent_id)
            self.store.append_interaction_transcript(session_id, "agent_chat", "assistant", payload["response"], agent_id=agent_id)
            return payload

        runtime_settings = self._runtime_settings_for_session(session_id)
        memory_service = MemoryService(runtime_settings)
        try:
            payload = memory_service.agent_chat_realtime(
                session_id,
                agent_id,
                augmented_message,
                live_mode=self._is_live_session(session_id),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                self._format_runtime_failure_detail(
                    session_id,
                    exc,
                    action="Live 1:1 chat",
                )
            ) from exc

        response_text = str(payload.get("response") or "").strip()
        if not response_text:
            raise RuntimeError("Live 1:1 chat returned an empty response from the selected agent.")

        self.store.append_interaction_transcript(session_id, "agent_chat", "user", message, agent_id=agent_id)
        self.store.append_interaction_transcript(session_id, "agent_chat", "assistant", response_text, agent_id=agent_id)
        payload["response"] = response_text
        return payload

    def get_analytics_polarization(self, session_id: str, metric_name: str | None = None) -> dict[str, Any]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        config_service = ConfigService(runtime_settings)
        metrics = MetricsService(config_service)

        agents_post = self._agents_for_metrics(session_id)
        agents_pre = self._agents_for_metrics(session_id)
        baseline_cps = self._load_checkpoint_records(session_id, "baseline")
        final_cps = self._load_checkpoint_records(session_id, "post")

        if metric_name:
            post_field = f"checkpoint_{metric_name}"
            pre_field = f"checkpoint_pre_{metric_name}"
            self._enrich_agents_metric_score(agents_post, final_cps, metric_name, post_field)
            self._enrich_agents_metric_score(agents_pre, baseline_cps, metric_name, pre_field)
        else:
            post_field = "agg_post_score"
            pre_field = "agg_pre_score"
            self._enrich_agents_aggregate_scores(agents_post, final_cps, post_field)
            self._enrich_agents_aggregate_scores(agents_pre, baseline_cps, pre_field)

        post_metric = metrics.compute_polarization(agents_post, post_field)
        pre_metric = metrics.compute_polarization(agents_pre, pre_field)

        interactions = self.store.get_interactions(session_id)
        # Prefer planned_rounds from the session state so we get the correct
        # number of rounds even though all interaction records have round_no=1.
        state = self.streams.get_state(session_id)
        max_round = int((state or {}).get("planned_rounds", 0) or 0)
        if max_round < 1:
            # Fallback: derive from interaction records (may be inaccurate)
            max_round = max((int(item.get("round_no", 0) or 0) for item in interactions), default=1)
        max_round = max(1, max_round)

        pre_index = float(pre_metric.get("polarization_index", 0.0))
        post_index = float(post_metric.get("polarization_index", 0.0))

        def _severity(idx: float) -> str:
            if idx < 0.2:
                return "low"
            if idx < 0.5:
                return "moderate"
            if idx < 0.8:
                return "high"
            return "critical"

        series: list[dict[str, Any]] = [
            {
                "round": "Start",
                "round_no": 0,
                "polarization_index": pre_index,
                "severity": pre_metric.get("severity", "low"),
                "by_group_means": pre_metric.get("by_group_means", {}),
                "group_sizes": pre_metric.get("group_sizes", {}),
            },
        ]
        # Interpolate per-round data points between baseline and final
        for r in range(1, max_round + 1):
            t = r / max_round  # 0→1
            interp_index = round(pre_index + t * (post_index - pre_index), 4)
            series.append({
                "round": f"R{r}",
                "round_no": r,
                "polarization_index": interp_index,
                "severity": _severity(interp_index),
            })

        return {"session_id": session_id, "metric_name": metric_name, "series": series}

    def get_analytics_opinion_flow(self, session_id: str, metric_name: str | None = None) -> dict[str, Any]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        config_service = ConfigService(runtime_settings)
        metrics = MetricsService(config_service)

        agents = self._agents_for_metrics(session_id)
        baseline_cps = self._load_checkpoint_records(session_id, "baseline")
        final_cps = self._load_checkpoint_records(session_id, "post")

        if not metric_name:
            # Aggregate: average across ALL numeric metric scores from checkpoints
            pre_field = "agg_pre_score"
            post_field = "agg_post_score"
            self._enrich_agents_aggregate_scores(agents, baseline_cps, pre_field)
            self._enrich_agents_aggregate_scores(agents, final_cps, post_field)
        else:
            # Per-metric: parse specific metric from baseline & final checkpoints
            pre_field = f"checkpoint_pre_{metric_name}"
            post_field = f"checkpoint_{metric_name}"
            self._enrich_agents_metric_score(agents, final_cps, metric_name, post_field)
            self._enrich_agents_metric_score(agents, baseline_cps, metric_name, pre_field)

        flow = metrics.compute_opinion_flow(agents, post_field, pre_field=pre_field)
        flow["session_id"] = session_id
        flow["metric_name"] = metric_name
        return flow

    def _enrich_agents_metric_score(
        self,
        agents: list[dict[str, Any]],
        checkpoints: list[dict[str, Any]],
        metric_name: str,
        target_field: str,
    ) -> None:
        """Parse a single metric from checkpoint records and store on agents."""
        lookup: dict[str, float] = {}
        for record in checkpoints:
            aid = str(record.get("agent_id", "")).strip()
            if not aid:
                continue
            answers = record.get("metric_answers") or {}
            if metric_name in answers:
                parsed = self._extract_metric_score(answers[metric_name])
                if parsed is not None:
                    lookup[aid] = parsed
        for agent in agents:
            aid = str(agent.get("agent_id") or agent.get("id") or "")
            if aid in lookup:
                agent[target_field] = lookup[aid]

    def _enrich_agents_aggregate_scores(
        self,
        agents: list[dict[str, Any]],
        checkpoints: list[dict[str, Any]],
        target_field: str,
    ) -> None:
        """Compute average of all parseable metric scores and store on agents."""
        scores_by_agent: dict[str, list[float]] = {}
        for record in checkpoints:
            aid = str(record.get("agent_id", "")).strip()
            if not aid:
                continue
            answers = record.get("metric_answers") or {}
            for value in answers.values():
                parsed = self._extract_metric_score(value)
                if parsed is not None:
                    scores_by_agent.setdefault(aid, []).append(parsed)
        for agent in agents:
            aid = str(agent.get("agent_id") or agent.get("id") or "")
            agent_scores = scores_by_agent.get(aid)
            if agent_scores:
                agent[target_field] = sum(agent_scores) / len(agent_scores)

    def get_analytics_influence(self, session_id: str) -> dict[str, Any]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        config_service = ConfigService(runtime_settings)
        metrics = MetricsService(config_service)
        interactions = self.store.get_interactions(session_id)
        payload = metrics.compute_influence(interactions)
        payload["session_id"] = session_id
        return payload

    def get_analytics_cascades(self, session_id: str) -> dict[str, Any]:
        runtime_settings = self._runtime_settings_for_session(session_id)
        config_service = ConfigService(runtime_settings)
        metrics = MetricsService(config_service)
        interactions = self.store.get_interactions(session_id)
        posts = [
            row
            for row in interactions
            if str(row.get("action_type", "")).lower() in {"create_post", "post_created", "post"}
        ]
        comments = [
            row
            for row in interactions
            if "comment" in str(row.get("action_type", "")).lower() or str(row.get("type", "")).lower() == "comment"
        ]
        payload = metrics.compute_cascades(posts, comments, self._agents_for_metrics(session_id))
        payload["session_id"] = session_id
        return payload

    def get_agent_stances(self, session_id: str, metric_name: str | None = None) -> dict[str, Any]:
        agents, score_field = self._agents_with_checkpoint_metrics(session_id, metric_name)
        stances: list[dict[str, Any]] = []
        for agent in agents:
            aid = str(agent.get("agent_id") or agent.get("id") or "")
            score = agent.get(score_field, 5.0)
            try:
                numeric = float(score)
            except (TypeError, ValueError):
                numeric = 5.0
            persona = agent.get("persona") or {}
            stances.append({
                "agent_id": aid,
                "score": numeric,
                "planning_area": persona.get("planning_area", ""),
                "age_group": persona.get("age_group", ""),
                "archetype": persona.get("archetype", ""),
            })
        return {"session_id": session_id, "metric_name": metric_name, "score_field": score_field, "stances": stances}

    def _agents_for_metrics(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.store.get_agents(session_id)
        normalized: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["id"] = payload.get("id") or payload.get("agent_id")
            normalized.append(payload)
        return normalized

    @staticmethod
    def _extract_metric_score(value: Any) -> float | None:
        """Extract a numeric score from a free-text LLM metric answer.

        Handles patterns like:
        - ``"7/10"`` or ``"7/10. I think..."`` → 7.0
        - ``"7"`` or ``"7.5"`` → 7.0 / 7.5
        - ``"Yes"`` → 10.0  (full approval)
        - ``"No"``  →  1.0  (full disapproval)
        - Open-ended text  → None
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        low = text.lower()
        if low == "yes":
            return 10.0
        if low == "no":
            return 1.0
        # Try leading number: "7/10", "7.5/10", "7 out of 10", or just "7"
        m = re.match(r"(\d+(?:\.\d+)?)", text)
        if m:
            return float(m.group(1))
        return None

    def _load_checkpoint_records(self, session_id: str, checkpoint_kind: str) -> list[dict[str, Any]]:
        """Load checkpoint records, trying the requested kind first, then common fallbacks."""
        records = self.store.list_checkpoint_records(session_id, checkpoint_kind=checkpoint_kind)
        if records:
            return records
        # Try alternate names: "post" ↔ "final"
        alt = "final" if checkpoint_kind == "post" else ("post" if checkpoint_kind == "final" else None)
        if alt:
            records = self.store.list_checkpoint_records(session_id, checkpoint_kind=alt)
            if records:
                return records
        return []

    def _agents_with_checkpoint_metrics(self, session_id: str, metric_name: str | None = None) -> tuple[list[dict[str, Any]], str]:
        """Return (agents, score_field) with per-metric checkpoint data merged in.

        When *metric_name* is ``None`` (or empty), computes an average score
        across ALL parseable metrics from checkpoint data.  Falls back to
        ``opinion_post`` only when no checkpoint data is available.
        """
        agents = self._agents_for_metrics(session_id)

        checkpoints = self._load_checkpoint_records(session_id, "post")
        if not checkpoints:
            checkpoints = self.store.list_checkpoint_records(session_id)

        if not metric_name:
            # Aggregate: average across all parseable metric scores
            if not checkpoints:
                return agents, "opinion_post"
            score_field = "aggregate_avg"
            self._enrich_agents_aggregate_scores(agents, checkpoints, score_field)
            return agents, score_field

        score_field = f"checkpoint_{metric_name}"

        # Build lookup: agent_id → parsed numeric metric value
        metric_by_agent: dict[str, float] = {}
        for record in checkpoints:
            aid = str(record.get("agent_id", "")).strip()
            if not aid:
                continue
            answers = record.get("metric_answers") or {}
            if metric_name in answers:
                parsed = self._extract_metric_score(answers[metric_name])
                if parsed is not None:
                    metric_by_agent[aid] = parsed

        for agent in agents:
            aid = str(agent.get("agent_id") or agent.get("id") or "")
            if aid in metric_by_agent:
                agent[score_field] = metric_by_agent[aid]

        return agents, score_field

    def _agents_with_aggregate_extreme_scores(
        self, session_id: str, segment: str,
    ) -> tuple[list[dict[str, Any]], str]:
        """Enrich agents with min/max checkpoint scores across ALL metrics.

        For *dissenter* segment: uses the **minimum** score across all metrics
        so that any agent who dissents on ANY metric is captured.
        For *supporter* segment: uses the **maximum** score across all metrics
        so that any agent who supports ANY metric is captured.
        Falls back to ``opinion_post`` when no checkpoint data exists.
        """
        agents = self._agents_for_metrics(session_id)
        checkpoints = self._load_checkpoint_records(session_id, "post")
        if not checkpoints:
            checkpoints = self.store.list_checkpoint_records(session_id)
        if not checkpoints:
            return agents, "opinion_post"

        # Gather all numeric scores per agent across all metrics
        scores_by_agent: dict[str, list[float]] = {}
        for record in checkpoints:
            aid = str(record.get("agent_id", "")).strip()
            if not aid:
                continue
            answers = record.get("metric_answers") or {}
            for value in answers.values():
                parsed = self._extract_metric_score(value)
                if parsed is not None:
                    scores_by_agent.setdefault(aid, []).append(parsed)

        if not scores_by_agent:
            return agents, "opinion_post"

        score_field = "aggregate_extreme"
        pick = min if segment == "dissenter" else max
        for agent in agents:
            aid = str(agent.get("agent_id") or agent.get("id") or "")
            agent_scores = scores_by_agent.get(aid)
            if agent_scores:
                agent[score_field] = pick(agent_scores)

        return agents, score_field

    def _run_simulation_background(
        self,
        session_id: str,
        policy_summary: str,
        rounds: int,
        sampled_rows: list[dict[str, Any]],
        personas: list[dict[str, Any]],
        events_path: Path,
        mode: str,
        controversy_boost: float = 0.0,
    ) -> None:
        try:
            runtime_settings = self._runtime_settings_for_session(session_id)
            simulation_service = SimulationService(runtime_settings)
            config_service = ConfigService(runtime_settings)
            use_case = self._session_use_case(session_id)
            session_questions_payload = self.get_session_analysis_questions(session_id)
            checkpoint_questions = [
                item for item in session_questions_payload.get("questions", []) if isinstance(item, dict)
            ]
            if not checkpoint_questions:
                checkpoint_questions = self._checkpoint_questions_for_use_case(config_service, use_case)
            seed_discussion_threads = [
                str(item.get("question", "")).strip()
                for item in checkpoint_questions
                if isinstance(item, dict) and str(item.get("question", "")).strip()
            ]
            personality_modifiers = self._personality_modifiers_for_use_case(config_service, use_case)
            metrics_service = MetricsService(config_service)
            knowledge = self.store.get_knowledge_artifact(session_id) or {}
            country_id, country_cfg, _dataset_path = self._session_country_config(session_id)
            country_display_name = str(country_cfg.get("name") or country_id).strip() or "Singapore"
            context_bundles = simulation_service.build_context_bundles(
                simulation_id=session_id,
                policy_summary=policy_summary,
                knowledge_artifact=knowledge,
                sampled_personas=sampled_rows,
            )

            def _record_tokens(input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> None:
                if input_tokens <= 0 and output_tokens <= 0 and cached_tokens <= 0:
                    return
                self.record_runtime_token_usage(
                    session_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                )

            checkpoint_estimate = self._estimate_checkpoint_runtime(
                agent_count=len(sampled_rows),
                provider=runtime_settings.llm_provider,
            )
            round_estimate = self._estimate_round_runtime(
                agent_count=len(sampled_rows),
                provider=runtime_settings.llm_provider,
            )
            baseline_started_at = time.monotonic()
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_started",
                        "session_id": session_id,
                        "checkpoint_kind": "baseline",
                        "total_agents": len(sampled_rows),
                    }
                ],
            )
            baseline = simulation_service.run_opinion_checkpoint(
                simulation_id=session_id,
                checkpoint_kind="baseline",
                policy_summary=policy_summary,
                agent_context_bundles=context_bundles,
                checkpoint_questions=checkpoint_questions,
                on_token_usage=_record_tokens,
            )
            baseline_elapsed = max(1, int(time.monotonic() - baseline_started_at))
            baseline_metrics = metrics_service.compute_dynamic_metrics(
                self._agents_for_dynamic_metrics(baseline),
                use_case,
                round_no=0,
            )
            baseline_metrics_payload = self._flatten_dynamic_metrics_payload(
                baseline_metrics,
                round_label="Round 0 (100%)",
            )
            self.store.replace_checkpoint_records(session_id, "baseline", baseline)
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_completed",
                        "session_id": session_id,
                        "checkpoint_kind": "baseline",
                        "completed_agents": len(baseline),
                        "total_agents": len(sampled_rows),
                    },
                    {
                        "event_type": "metrics_updated",
                        "session_id": session_id,
                        "round_no": 0,
                        "elapsed_seconds": baseline_elapsed,
                        "estimated_total_seconds": baseline_elapsed + (rounds * round_estimate) + checkpoint_estimate,
                        "estimated_remaining_seconds": (rounds * round_estimate) + checkpoint_estimate,
                        "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                        "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
                        "top_threads": [],
                        "metrics": baseline_metrics_payload,
                        **baseline_metrics_payload,
                    },
                ],
            )
            enriched_personas = self._enrich_personas_for_simulation(
                personas,
                sampled_rows,
                context_bundles,
                personality_modifiers=personality_modifiers,
            )

            def _ingest_progress(path: Path, elapsed: int) -> None:
                del elapsed
                self.streams.ingest_events_incremental(session_id, path)

            simulation_result = simulation_service.run_with_personas(
                simulation_id=session_id,
                policy_summary=policy_summary,
                rounds=rounds,
                personas=enriched_personas,
                events_path=events_path,
                force_live=(mode == "live"),
                controversy_boost=controversy_boost,
                on_progress=_ingest_progress,
                elapsed_offset_seconds=baseline_elapsed,
                tail_checkpoint_estimate_seconds=checkpoint_estimate,
                seed_discussion_threads=seed_discussion_threads,
                country=country_display_name,
            )
            token_usage_payload = simulation_result.get("token_usage")
            if isinstance(token_usage_payload, dict):
                _record_tokens(
                    int(token_usage_payload.get("input_tokens", 0) or 0),
                    int(token_usage_payload.get("output_tokens", 0) or 0),
                    int(token_usage_payload.get("cached_tokens", 0) or 0),
                )
            self.streams.ingest_events_incremental(session_id, events_path)
            final_bundles = self._build_final_checkpoint_bundles(session_id, context_bundles)
            final_started_at = time.monotonic()
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_started",
                        "session_id": session_id,
                        "checkpoint_kind": "final",
                        "total_agents": len(sampled_rows),
                    }
                ],
            )
            final = simulation_service.run_opinion_checkpoint(
                simulation_id=session_id,
                checkpoint_kind="final",
                policy_summary=policy_summary,
                agent_context_bundles=final_bundles,
                checkpoint_questions=checkpoint_questions,
                on_token_usage=_record_tokens,
            )
            final_elapsed = max(1, int(time.monotonic() - final_started_at))
            total_elapsed = int(simulation_result.get("elapsed_seconds", 0) or 0) + final_elapsed
            final_counters = dict(simulation_result.get("counters") or {})
            current_state = self.streams.get_state(session_id)
            final_metrics = metrics_service.compute_dynamic_metrics(
                self._agents_for_dynamic_metrics(final),
                use_case,
                round_no=rounds,
            )
            final_metrics_payload = self._flatten_dynamic_metrics_payload(
                final_metrics,
                round_label=f"Round {rounds} (100%)",
            )
            self.store.replace_checkpoint_records(session_id, "final", final)
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_completed",
                        "session_id": session_id,
                        "checkpoint_kind": "final",
                        "completed_agents": len(final),
                        "total_agents": len(sampled_rows),
                    },
                    {
                        "event_type": "metrics_updated",
                        "session_id": session_id,
                        "round_no": rounds,
                        "elapsed_seconds": total_elapsed,
                        "estimated_total_seconds": total_elapsed,
                        "estimated_remaining_seconds": 0,
                        "counters": final_counters or {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                        "discussion_momentum": current_state.get("discussion_momentum", {"approval_delta": 0.0, "dominant_stance": "mixed"}),
                        "top_threads": current_state.get("top_threads", []),
                        "metrics": final_metrics_payload,
                        **final_metrics_payload,
                    },
                    {
                        "event_type": "run_completed",
                        "session_id": session_id,
                        "round_no": rounds,
                        "elapsed_seconds": total_elapsed,
                    },
                ],
            )
            self._apply_checkpoint_scores_to_agents(session_id, sampled_rows, baseline, final)
            self.store.upsert_console_session(session_id=session_id, mode=mode, status="simulation_completed")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Simulation background failed for session %s", session_id)
            summary = self._summarize_simulation_failure(exc)
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "run_failed",
                        "session_id": session_id,
                        "error": summary,
                    }
                ],
            )
            failure_state = dict(self.streams.get_state(session_id) or {})
            latest_metrics = dict(failure_state.get("latest_metrics") or {})
            latest_metrics["error"] = summary
            failure_state.update(
                {
                    "session_id": session_id,
                    "status": "failed",
                    "latest_metrics": latest_metrics,
                    "recent_events": [],
                    "events_path": str(events_path),
                }
            )
            self.store.save_simulation_state_snapshot(session_id, failure_state)
            self.store.upsert_console_session(session_id=session_id, mode=mode, status="simulation_failed")

    def _merge_population_filters(self, request: Any, parsed_instructions: dict[str, Any], *, country: str) -> dict[str, Any]:
        hard_filters = parsed_instructions.get("hard_filters", {})
        selected_country = str(country or "singapore").strip().lower() or "singapore"
        geography_field = self.country_metadata.geography_field(selected_country)

        min_age = request.min_age
        max_age = request.max_age

        hard_min_age = self._parse_age_filter_value(hard_filters.get("min_age", []))
        hard_max_age = self._parse_age_filter_value(hard_filters.get("max_age", []))
        if hard_min_age is not None:
            min_age = hard_min_age if min_age is None else max(min_age, hard_min_age)
        if hard_max_age is not None:
            max_age = hard_max_age if max_age is None else min(max_age, hard_max_age)

        requested_age_cohorts = hard_filters.get("age_cohort", [])
        if requested_age_cohorts:
            age_bounds = [self._age_bounds_for_cohort(cohort) for cohort in requested_age_cohorts]
            age_bounds = [bounds for bounds in age_bounds if bounds is not None]
            if age_bounds:
                derived_min = min(bounds[0] for bounds in age_bounds)
                derived_max = max(bounds[1] for bounds in age_bounds)
                min_age = derived_min if min_age is None else max(min_age, derived_min)
                max_age = derived_max if max_age is None else min(max_age, derived_max)

        if min_age is not None and max_age is not None and min_age > max_age:
            raise HTTPException(status_code=422, detail="Sampling constraints are contradictory: min_age exceeds max_age.")

        dynamic_filters = self._merge_dynamic_filters(
            request_dynamic_filters=getattr(request, "dynamic_filters", {}) or {},
            hard_filters=hard_filters,
            geography_field=geography_field,
        )

        geography_values = self.country_metadata.normalize_geography_values(
            selected_country,
            [*(getattr(request, "planning_areas", []) or []), *(hard_filters.get(geography_field, []) or [])],
        )

        return {
            "min_age": min_age,
            "max_age": max_age,
            "geography_field": geography_field,
            "geography_values": geography_values,
            "sexes": self._merge_unique_values([], hard_filters.get("sex", []), title_case=True),
            "marital_statuses": self._merge_unique_values([], hard_filters.get("marital_status", [])),
            "education_levels": self._merge_unique_values([], hard_filters.get("education_level", [])),
            "occupations": self._merge_unique_values([], hard_filters.get("occupation", [])),
            "industries": self._merge_unique_values([], hard_filters.get("industry", [])),
            "dynamic_filters": dynamic_filters,
        }

    def _merge_unique_values(self, primary: list[str], secondary: list[str], *, title_case: bool = False) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for raw in [*(primary or []), *(secondary or [])]:
            text = str(raw).strip()
            if not text:
                continue
            value = text.replace("_", " ")
            if title_case:
                value = value.title()
            slug = value.lower()
            if slug in seen:
                continue
            seen.add(slug)
            merged.append(value)
        return merged

    def _merge_dynamic_filters(
        self,
        *,
        request_dynamic_filters: dict[str, Any],
        hard_filters: dict[str, Any],
        geography_field: str,
    ) -> dict[str, Any]:
        supported_keys = {
            "min_age",
            "max_age",
            "age_cohort",
            geography_field,
            "sex",
            "marital_status",
            "education_level",
            "occupation",
            "industry",
        }
        merged: dict[str, Any] = {}

        for key, value in (request_dynamic_filters or {}).items():
            clean_key = str(key or "").strip()
            if not clean_key or clean_key in supported_keys:
                continue
            normalized = self._normalize_dynamic_filter_value(value)
            if normalized is not None:
                merged[clean_key] = normalized

        for key, value in (hard_filters or {}).items():
            clean_key = str(key or "").strip()
            if not clean_key or clean_key in supported_keys:
                continue
            normalized = self._normalize_dynamic_filter_value(value)
            if normalized is None:
                continue
            if clean_key not in merged:
                merged[clean_key] = normalized
                continue
            existing = merged[clean_key]
            if isinstance(existing, list) and isinstance(normalized, list):
                for item in normalized:
                    if item not in existing:
                        existing.append(item)
        return merged

    def _normalize_dynamic_filter_value(self, value: Any) -> list[str] | str | dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            normalized: dict[str, Any] = {}
            for key in ("min", "max"):
                if value.get(key) is not None:
                    normalized[key] = value.get(key)
            return normalized or None
        if isinstance(value, list):
            values = [str(item).strip() for item in value if str(item).strip()]
            return values or None
        scalar = str(value).strip()
        return scalar or None

    def _age_bounds_for_cohort(self, cohort: str) -> tuple[int, int] | None:
        normalized = str(cohort).strip().lower()
        range_match = re.match(r"^(\d{1,3})_(\d{1,3})$", normalized)
        if range_match:
            lower = max(0, min(120, int(range_match.group(1))))
            upper = max(0, min(120, int(range_match.group(2))))
            return (min(lower, upper), max(lower, upper))
        plus_match = re.match(r"^(\d{1,3})_plus$", normalized)
        if plus_match:
            lower = max(0, min(120, int(plus_match.group(1))))
            return (lower, 120)
        if normalized == "youth":
            return (18, 24)
        if normalized == "adult":
            return (25, 59)
        if normalized == "senior":
            return (60, 100)
        return None

    def _parse_age_filter_value(self, values: Any) -> int | None:
        candidates = values if isinstance(values, list) else [values]
        for value in candidates:
            match = re.search(r"\d{1,3}", str(value))
            if not match:
                continue
            return max(0, min(120, int(match.group(0))))
        return None

    def _estimate_initial_runtime(self, *, agent_count: int, rounds: int, provider: str) -> int:
        checkpoint_seconds = self._estimate_checkpoint_runtime(agent_count=agent_count, provider=provider)
        round_seconds = self._estimate_round_runtime(agent_count=agent_count, provider=provider)
        return (checkpoint_seconds * 2) + (round_seconds * rounds)

    def _estimate_checkpoint_runtime(self, *, agent_count: int, provider: str) -> int:
        normalized_provider = str(provider or "ollama").strip().lower()
        if normalized_provider == "ollama":
            return max(40, int(agent_count * 3.6))
        return max(8, int(agent_count * 0.22))

    def _estimate_round_runtime(self, *, agent_count: int, provider: str) -> int:
        normalized_provider = str(provider or "ollama").strip().lower()
        if normalized_provider == "ollama":
            return max(45, int(agent_count * 6.8) + 20)
        return max(10, int(agent_count * 0.06) + 6)

    def _session_use_case(self, session_id: str) -> str:
        session_cfg = self._read_session_config(session_id)
        use_case = str(session_cfg.get("use_case") or "").strip().lower()
        return use_case or "public-policy-testing"

    def _checkpoint_questions_for_use_case(self, config_service: ConfigService, use_case: str) -> list[dict[str, Any]]:
        try:
            raw_questions = config_service.get_checkpoint_questions(use_case)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(raw_questions, list):
            return []
        return [item for item in raw_questions if isinstance(item, dict)]

    def _personality_modifiers_for_use_case(self, config_service: ConfigService, use_case: str) -> list[str]:
        try:
            raw_modifiers = config_service.get_agent_personality_modifiers(use_case)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(raw_modifiers, list):
            return []
        return [str(item).strip() for item in raw_modifiers if str(item).strip()]

    def _agents_for_dynamic_metrics(self, checkpoint_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        agents: list[dict[str, Any]] = []
        for record in checkpoint_records:
            if not isinstance(record, dict):
                continue
            row: dict[str, Any] = {}
            metric_answers = record.get("metric_answers", {})
            if isinstance(metric_answers, dict):
                for metric_name, value in metric_answers.items():
                    clean_name = str(metric_name or "").strip()
                    if not clean_name:
                        continue
                    row[f"checkpoint_{clean_name}"] = value
            if not row:
                # Backward-compat fallback for legacy checkpoint output.
                row["checkpoint_approval_rate"] = 1 + (float(record.get("stance_score", 0.5) or 0.5) * 9)
                row["checkpoint_net_sentiment"] = row["checkpoint_approval_rate"]
            agents.append(row)
        return agents

    def _flatten_dynamic_metrics_payload(
        self,
        dynamic_metrics: dict[str, Any],
        *,
        round_label: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for metric_name, value in (dynamic_metrics or {}).items():
            if not isinstance(value, dict):
                continue
            payload[metric_name] = value.get("value")
            payload[f"{metric_name}_meta"] = value
        if round_label:
            payload["round_progress_label"] = round_label
            payload["round_progress"] = {"label": round_label}
        return payload

    def _enrich_personas_for_simulation(
        self,
        personas: list[dict[str, Any]],
        sampled_rows: list[dict[str, Any]],
        context_bundles: dict[str, dict[str, Any]],
        *,
        personality_modifiers: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        modifiers = [str(item).strip() for item in (personality_modifiers or []) if str(item).strip()]
        modifier_suffix = ""
        if modifiers:
            modifier_suffix = " Personality modifiers: " + " ".join(f"- {item}" for item in modifiers)
        by_agent = {str(row.get("agent_id")): row for row in sampled_rows}
        for persona in personas:
            agent_id = str(persona.get("agent_id", "")).strip()
            row = by_agent.get(agent_id, {})
            reason = dict(row.get("selection_reason") or {})
            bundle = context_bundles.get(agent_id, {})
            enriched_persona = dict(persona)
            brief = str(bundle.get("brief") or "").strip()
            enriched_persona["mckainsey_context"] = f"{brief}{modifier_suffix}".strip()
            enriched_persona["mckainsey_matched_context_nodes"] = bundle.get("matched_context_nodes", [])
            enriched_persona["mckainsey_relevance_score"] = reason.get("score") or reason.get("selection_score") or 0.0
            enriched.append(enriched_persona)
        return enriched

    def _build_final_checkpoint_bundles(
        self,
        session_id: str,
        context_bundles: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        interactions = self.store.get_interactions(session_id)
        by_agent: dict[str, list[str]] = {}
        for interaction in interactions:
            agent_id = str(interaction.get("actor_agent_id", "")).strip()
            content = str(interaction.get("content", "")).strip()
            if not agent_id or not content:
                continue
            by_agent.setdefault(agent_id, []).append(content)

        bundles: dict[str, dict[str, Any]] = {}
        for agent_id, bundle in context_bundles.items():
            discussion = " ".join(by_agent.get(agent_id, [])[:4]).strip()
            updated = dict(bundle)
            if discussion:
                updated["brief"] = f"{bundle['brief']} Discussion excerpt: {discussion}"
            bundles[agent_id] = updated
        return bundles

    def _apply_checkpoint_scores_to_agents(
        self,
        session_id: str,
        sampled_rows: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
    ) -> None:
        baseline_map = {str(row.get("agent_id")): row for row in baseline}
        final_map = {str(row.get("agent_id")): row for row in final}
        updated_agents: list[dict[str, Any]] = []
        for row in sampled_rows:
            agent_id = str(row.get("agent_id"))
            persona = dict(row.get("persona") or {})
            baseline_row = baseline_map.get(agent_id, {})
            final_row = final_map.get(agent_id, baseline_row)
            pre_score = float(baseline_row.get("stance_score", 0.5))
            post_score = float(final_row.get("stance_score", pre_score))
            confirmed_name = str(final_row.get("confirmed_name") or baseline_row.get("confirmed_name") or "").strip()
            if confirmed_name:
                persona["confirmed_name"] = confirmed_name
                persona["display_name"] = confirmed_name
            updated_agents.append(
                {
                    "agent_id": agent_id,
                    "persona": persona,
                    "opinion_pre": round(1 + (pre_score * 9), 4),
                    "opinion_post": round(1 + (post_score * 9), 4),
                }
            )
        self.store.replace_agents(session_id, updated_agents)
