from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from mckainsey.config import BACKEND_DIR, Settings


logger = logging.getLogger(__name__)
REPO_ROOT = BACKEND_DIR.parent


USE_CASE_ALIASES = {
    "reviews": "customer-review",
    "customer-review": "customer-review",
    "policy-review": "policy-review",
    "ad-testing": "ad-testing",
    "pmf-discovery": "product-market-fit",
    "product-market-fit": "product-market-fit",
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

    def get_use_case(self, use_case_id: str) -> dict[str, Any]:
        normalized = str(use_case_id).strip().lower()
        canonical = USE_CASE_ALIASES.get(normalized, normalized)

        if canonical in self._prompt_cache:
            return self._prompt_cache[canonical]

        path = self.prompts_dir / f"{canonical}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Use-case config not found for: {use_case_id}")

        payload = self._load_yaml(path)
        self._prompt_cache[canonical] = payload
        return payload

    def get_checkpoint_questions(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        questions = payload.get("checkpoint_questions", [])
        return [item for item in questions if isinstance(item, dict)]

    def get_agent_personality_modifiers(self, use_case_id: str) -> list[str]:
        payload = self.get_use_case(use_case_id)
        modifiers = payload.get("agent_personality_modifiers", [])
        return [item for item in modifiers if isinstance(item, str)]

    def get_report_sections(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        sections = payload.get("report_sections", [])
        return [item for item in sections if isinstance(item, dict)]

    def resolve_dataset_path(self, dataset_path: str) -> str:
        source = str(dataset_path or "").strip()
        if not source:
            raise FileNotFoundError(f"Dataset path not found for filter inference: {dataset_path}")

        path = Path(source).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates = [REPO_ROOT / path, BACKEND_DIR / path] + candidates

        for candidate in candidates:
            resolved = self._resolve_dataset_candidate(candidate)
            if resolved is not None:
                return resolved

        raise FileNotFoundError(f"Dataset path not found for filter inference: {dataset_path}")

    def _resolve_dataset_candidate(self, candidate: Path) -> str | None:
        if candidate.exists():
            return str(candidate.resolve())

        if candidate.parent.exists():
            matches = sorted(candidate.parent.glob(candidate.name))
            if matches:
                if len(matches) == 1:
                    return str(matches[0].resolve())
                return str((candidate.parent.resolve() / candidate.name))

        for directory in (candidate.parent / "data", candidate.parent):
            if not directory.exists():
                continue
            for pattern in ("train-*.parquet", "train-*", "*.parquet"):
                matches = sorted(directory.glob(pattern))
                if not matches:
                    continue
                if len(matches) == 1:
                    return str(matches[0].resolve())
                return str(directory.resolve() / pattern)

        return None

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
