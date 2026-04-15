from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import yaml

from miroworld.config import BACKEND_DIR, Settings


logger = logging.getLogger(__name__)
REPO_ROOT = BACKEND_DIR.parent


USE_CASE_ALIASES: dict[str, str] = {
    # V2 canonical names
    "public-policy-testing": "public-policy-testing",
    "product-market-research": "product-market-research",
    "campaign-content-testing": "campaign-content-testing",
    # V1 backward-compatibility aliases → map to nearest V2 use case
    "reviews": "product-market-research",
    "customer-review": "product-market-research",
    "policy-review": "public-policy-testing",
    "ad-testing": "campaign-content-testing",
    "pmf-discovery": "product-market-research",
    "product-market-fit": "product-market-research",
}


class ConfigService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._country_cache: dict[str, dict[str, Any]] = {}
        self._prompt_cache: dict[str, dict[str, Any]] = {}

    @property
    def countries_dir(self) -> Path:
        return Path(self.settings.config_countries_dir)

    @property
    def prompts_dir(self) -> Path:
        return Path(self.settings.config_prompts_dir)

    @property
    def system_prompts_dir(self) -> Path:
        return self.prompts_dir / "system"

    # ── Country methods ──

    def list_countries(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.countries_dir.glob("*.yaml")):
            payload = self._safe_load_yaml(path)
            if payload is None:
                continue
            self._country_cache[path.stem] = payload
            items.append(payload)
        return items

    def get_country(self, country_id: str) -> dict[str, Any]:
        normalized = str(country_id).strip().lower()
        aliases = {normalized}
        if normalized == "sg":
            aliases.add("singapore")
        if normalized == "us":
            aliases.add("usa")

        for alias in aliases:
            if alias in self._country_cache:
                return self._country_cache[alias]

            path = self.countries_dir / f"{alias}.yaml"
            if path.exists():
                payload = self._load_yaml(path)
                self._country_cache[alias] = payload
                return payload

        raise FileNotFoundError(f"Country config not found for: {country_id}")

    def get_country_filterable_columns(self, country_id: str) -> list[dict[str, Any]]:
        payload = self.get_country(country_id)
        columns = payload.get("filterable_columns")
        if isinstance(columns, list) and columns:
            return [item for item in columns if isinstance(item, dict)]
        return []

    def get_country_dataset_config(self, country: str | dict[str, Any]) -> dict[str, Any]:
        payload = country if isinstance(country, dict) else self.get_country(country)
        raw = payload.get("dataset")
        config = dict(raw) if isinstance(raw, dict) else {}

        local_paths = config.get("local_paths")
        if not isinstance(local_paths, list) or not local_paths:
            local_path = config.get("local_path") or payload.get("dataset_path")
            local_paths = [local_path] if str(local_path or "").strip() else []

        download_dir = config.get("download_dir")
        if not download_dir and local_paths:
            first = Path(str(local_paths[0]))
            if first.name.startswith("train-"):
                download_dir = str(first.parent.parent)
            else:
                download_dir = str(first.parent)

        required_columns = config.get("required_columns")
        if not isinstance(required_columns, list) or not required_columns:
            required_columns = []

        country_values = config.get("country_values")
        if not isinstance(country_values, list):
            country_values = []

        allow_patterns = config.get("allow_patterns")
        if not isinstance(allow_patterns, list) or not allow_patterns:
            allow_patterns = ["data/train-*", "README.md"]

        return {
            **config,
            "local_paths": [str(item).strip() for item in local_paths if str(item).strip()],
            "download_dir": str(download_dir).strip() if str(download_dir or "").strip() else "",
            "required_columns": [str(item).strip() for item in required_columns if str(item).strip()],
            "country_values": [str(item).strip() for item in country_values if str(item).strip()],
            "allow_patterns": [str(item).strip() for item in allow_patterns if str(item).strip()],
        }

    def get_country_geography_config(self, country: str | dict[str, Any]) -> dict[str, Any]:
        payload = country if isinstance(country, dict) else self.get_country(country)
        raw = payload.get("geography")
        if isinstance(raw, dict):
            return raw
        return {}

    # ── Use-case methods ──

    def get_use_case(self, use_case_id: str) -> dict[str, Any]:
        normalized = str(use_case_id).strip().lower()
        canonical = USE_CASE_ALIASES.get(normalized, normalized)

        if canonical in self._prompt_cache:
            return self._prompt_cache[canonical]

        path = self.prompts_dir / f"{canonical}.yaml"
        if not path.exists() and normalized != canonical:
            # Backward-compatible fallback for tests or deployments that still
            # ship legacy prompt filenames.
            legacy_path = self.prompts_dir / f"{normalized}.yaml"
            if legacy_path.exists():
                path = legacy_path
        if not path.exists():
            raise FileNotFoundError(f"Use-case config not found for: {use_case_id}")

        payload = self._load_yaml(path)
        self._prompt_cache[canonical] = payload
        return payload

    def list_use_cases(self) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for path in sorted(self.prompts_dir.glob("*.yaml")):
            payload = self._safe_load_yaml(path)
            if payload is None:
                continue
            cases.append({
                "name": payload.get("name", path.stem),
                "code": payload.get("code", path.stem),
                "description": payload.get("description", ""),
                "icon": payload.get("icon", ""),
            })
        return cases

    def get_system_prompt_config(self, prompt_id: str) -> dict[str, Any]:
        normalized = str(prompt_id).strip().lower().replace("\\", "/")
        cache_key = f"system::{normalized}"
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        path = self.system_prompts_dir / f"{normalized}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"System prompt config not found for: {prompt_id}")

        payload = self._load_yaml(path)
        self._prompt_cache[cache_key] = payload
        return payload

    def get_system_prompt_value(self, prompt_id: str, *keys: str, default: str = "") -> str:
        payload: Any = self.get_system_prompt_config(prompt_id)
        for key in keys:
            if not isinstance(payload, dict):
                return default
            payload = payload.get(key)
        if payload is None:
            return default
        return str(payload).strip()

    def get_use_case_prompt_terms(self, use_case_id: str | None) -> dict[str, str]:
        normalized = str(use_case_id or "").strip().lower()
        if not normalized:
            return {}
        payload = self.get_use_case(normalized)
        raw_terms = payload.get("prompt_terms")
        if not isinstance(raw_terms, dict):
            return {}
        terms: dict[str, str] = {}
        for key, value in raw_terms.items():
            clean_key = str(key or "").strip()
            clean_value = str(value or "").strip()
            if clean_key and clean_value:
                terms[clean_key] = clean_value
        return terms

    def render_prompt_template(
        self,
        template: str | None,
        *,
        country_id: str | None = None,
        use_case_id: str | None = None,
        extra_replacements: dict[str, Any] | None = None,
    ) -> str:
        text = str(template or "").strip()
        if not text:
            return ""

        replacements = {
            "country_id": str(country_id or "").strip().lower(),
            "country_code": str(country_id or "").strip().lower(),
            "country_name": str(country_id or "").strip(),
            "geography_field": "planning_area",
            "geography_label": "Planning Area",
        }

        if country_id:
            try:
                country_cfg = self.get_country(country_id)
                geography_cfg = self.get_country_geography_config(country_cfg)
                replacements.update(
                    {
                        "country_id": str(country_cfg.get("code") or country_id).strip().lower(),
                        "country_code": str(country_cfg.get("code") or country_id).strip().lower(),
                        "country_name": str(country_cfg.get("name") or country_id).strip(),
                        "geography_field": str(geography_cfg.get("field") or "planning_area").strip(),
                        "geography_label": str(geography_cfg.get("label") or "Planning Area").strip(),
                    }
                )
            except FileNotFoundError:
                pass

        replacements.update(self.get_use_case_prompt_terms(use_case_id))
        for key, value in (extra_replacements or {}).items():
            replacements[str(key)] = str(value)

        rendered = text
        for key, value in replacements.items():
            rendered = rendered.replace(f"{{{key}}}", value)
        return rendered.strip()

    def get_system_prompt(self, use_case_id: str, *, country_id: str | None = None) -> str:
        payload = self.get_use_case(use_case_id)
        template = str(payload.get("guiding_prompt") or payload.get("system_prompt") or "").strip()
        return self.render_prompt_template(template, country_id=country_id, use_case_id=use_case_id)

    def get_analysis_questions(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        questions = payload.get("analysis_questions", [])
        if not questions:
            # Backward compat: fall back to checkpoint_questions
            questions = payload.get("checkpoint_questions", [])
        return [item for item in questions if isinstance(item, dict)]

    def get_insight_blocks(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        blocks = payload.get("insight_blocks", [])
        return [item for item in blocks if isinstance(item, dict)]

    def get_preset_sections(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        sections = payload.get("preset_sections", [])
        return [item for item in sections if isinstance(item, dict)]

    def get_report_writer_instructions(self, use_case_id: str) -> list[str]:
        payload = self.get_use_case(use_case_id)
        instructions = payload.get("report_writer_instructions", [])
        return [str(item).strip() for item in instructions if str(item).strip()]

    def get_agent_personality_modifiers(self, use_case_id: str) -> list[str]:
        payload = self.get_use_case(use_case_id)
        modifiers = payload.get("agent_personality_modifiers", [])
        return [item for item in modifiers if isinstance(item, str)]

    # Backward-compat wrappers
    def get_checkpoint_questions(self, use_case_id: str) -> list[dict[str, Any]]:
        """Backward-compat alias for get_analysis_questions."""
        return self.get_analysis_questions(use_case_id)

    def get_report_sections(self, use_case_id: str) -> list[dict[str, Any]]:
        """Backward-compat: builds report sections from analysis_questions + preset_sections."""
        payload = self.get_use_case(use_case_id)
        # Try new-style report_sections first
        sections = payload.get("report_sections", [])
        if sections:
            return [item for item in sections if isinstance(item, dict)]
        # Otherwise build from analysis_questions + preset_sections
        questions = self.get_analysis_questions(use_case_id)
        presets = self.get_preset_sections(use_case_id)
        result: list[dict[str, Any]] = []
        for q in questions:
            result.append({
                "title": q.get("report_title", q.get("question", "")),
                "prompt": q.get("question", ""),
            })
        for p in presets:
            result.append(p)
        return result

    def resolve_dataset_path(self, dataset_path: str, *, required_columns: list[str] | None = None) -> str:
        source = str(dataset_path or "").strip()
        if not source:
            raise FileNotFoundError(f"Dataset path not found for filter inference: {dataset_path}")

        path = Path(source).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates = [REPO_ROOT / path, BACKEND_DIR / path] + candidates

        resolved_candidates: list[str] = []
        for candidate in candidates:
            resolved_candidates.extend(self._resolve_dataset_candidates(candidate))

        deduped_candidates = list(dict.fromkeys(resolved_candidates))
        if required_columns:
            normalized_required = {self._normalize_required_column(column) for column in required_columns if str(column).strip()}
            for candidate in deduped_candidates:
                if self._dataset_has_columns(candidate, normalized_required):
                    return candidate
            raise FileNotFoundError(
                f"Dataset path not found with required columns {sorted(normalized_required)}: {dataset_path}"
            )

        if deduped_candidates:
            return deduped_candidates[0]

        raise FileNotFoundError(f"Dataset path not found for filter inference: {dataset_path}")

    def _resolve_dataset_candidates(self, candidate: Path) -> list[str]:
        resolved: list[str] = []
        if candidate.exists():
            resolved.append(str(candidate.resolve()))

        if candidate.parent.exists():
            matches = sorted(candidate.parent.glob(candidate.name))
            if matches:
                if len(matches) == 1:
                    resolved.append(str(matches[0].resolve()))
                else:
                    resolved.append(str((candidate.parent.resolve() / candidate.name)))

        for directory in (candidate.parent / "data", candidate.parent):
            if not directory.exists():
                continue
            for pattern in ("train-*.parquet", "train-*", "*.parquet"):
                matches = sorted(directory.glob(pattern))
                if not matches:
                    continue
                if len(matches) == 1:
                    resolved.append(str(matches[0].resolve()))
                else:
                    resolved.append(str(directory.resolve() / pattern))

        return resolved

    def _dataset_has_columns(self, parquet_source: str, required_columns: set[str]) -> bool:
        if not required_columns:
            return True
        conn = duckdb.connect()
        try:
            rows = conn.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{parquet_source}')"
            ).fetchall()
        finally:
            conn.close()
        available = {self._normalize_required_column(row[0]) for row in rows}
        return required_columns.issubset(available)

    def _normalize_required_column(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "gender":
            return "sex"
        return normalized

    def _safe_load_yaml(self, path: Path) -> dict[str, Any] | None:
        try:
            return self._load_yaml(path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to parse config file %s: %s", path.name, exc)
            return None

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        raw = path.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"Config file must be a mapping: {path}")
        return payload
