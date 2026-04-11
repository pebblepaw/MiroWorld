from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any

from fastapi import HTTPException
from huggingface_hub import snapshot_download

from miroworld.config import BACKEND_DIR, Settings
from miroworld.services.config_service import ConfigService
from miroworld.services.country_metadata_service import CountryMetadataService


REPO_ROOT = BACKEND_DIR.parent
_STATUS_LOCK = threading.Lock()
_DOWNLOAD_STATUS: dict[str, dict[str, Any]] = {}


@dataclass
class CountryDatasetService:
    settings: Settings
    config: ConfigService = field(init=False)
    metadata: CountryMetadataService = field(init=False)

    def __post_init__(self) -> None:
        self.config = ConfigService(self.settings)
        self.metadata = CountryMetadataService(self.settings)

    def list_country_payloads(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for country in self.config.list_countries():
            code = str(country.get("code") or "").strip().lower()
            if not code:
                continue
            payloads.append({
                **country,
                **self.country_status(code),
            })
        return payloads

    def country_status(self, country: str) -> dict[str, Any]:
        country_cfg = self.config.get_country(country)
        code = str(country_cfg.get("code") or country).strip().lower()
        runtime = self._runtime_status(code)
        resolved_path, invalid_local = self._resolve_declared_local_dataset_path(country_cfg)

        if resolved_path:
            ready = {
                "dataset_ready": True,
                "download_required": False,
                "download_status": "ready",
                "download_error": None,
                "missing_dependency": None,
                "resolved_dataset_path": resolved_path,
            }
            self._set_runtime_status(code, ready)
            return ready

        if runtime.get("download_status") == "downloading":
            return {
                "dataset_ready": False,
                "download_required": True,
                "download_status": "downloading",
                "download_error": runtime.get("download_error"),
                "missing_dependency": None,
                "resolved_dataset_path": None,
            }

        if runtime.get("download_status") == "error":
            return {
                "dataset_ready": False,
                "download_required": True,
                "download_status": "error",
                "download_error": runtime.get("download_error"),
                "missing_dependency": None if self.settings.huggingface_api_key else "huggingface_api_key",
                "resolved_dataset_path": None,
            }

        missing_dependency = None if self.settings.huggingface_api_key else "huggingface_api_key"
        download_status = "error" if invalid_local else "missing"
        download_error = "Local dataset exists but does not match the configured schema." if invalid_local else None
        return {
            "dataset_ready": False,
            "download_required": True,
            "download_status": download_status,
            "download_error": download_error,
            "missing_dependency": missing_dependency,
            "resolved_dataset_path": None,
        }

    def download_status(self, country: str) -> dict[str, Any]:
        return self.country_status(country)

    def resolve_dataset_path(self, country: str) -> str:
        country_cfg = self.config.get_country(country)
        resolved_path, invalid_local = self._resolve_declared_local_dataset_path(country_cfg)
        if resolved_path:
            return resolved_path
        detail = self._missing_dataset_detail(country, invalid_local=invalid_local)
        raise HTTPException(status_code=422, detail=detail)

    def ensure_country_ready(self, country: str) -> str:
        return self.resolve_dataset_path(country)

    def start_download(self, country: str) -> dict[str, Any]:
        country_cfg = self.config.get_country(country)
        code = str(country_cfg.get("code") or country).strip().lower()
        status = self.country_status(code)
        if status["dataset_ready"]:
            return status
        if not self.settings.huggingface_api_key:
            raise HTTPException(
                status_code=422,
                detail={
                    **self._missing_dataset_detail(code, invalid_local=(status["download_status"] == "error")),
                    "code": "huggingface_api_key_missing",
                    "message": "Add HUGGINGFACE_API_KEY to the root .env file before downloading country datasets.",
                },
            )
        if status["download_status"] == "downloading":
            return status

        self._set_runtime_status(code, {"download_status": "downloading", "download_error": None})
        thread = threading.Thread(target=self._download_country_dataset, args=(code,), daemon=True)
        thread.start()
        return self.country_status(code)

    def _download_country_dataset(self, country: str) -> None:
        try:
            country_cfg = self.config.get_country(country)
            dataset_cfg = self.config.get_country_dataset_config(country_cfg)
            snapshot_download(
                repo_id=str(dataset_cfg.get("repo_id")),
                repo_type="dataset",
                allow_patterns=list(dataset_cfg.get("allow_patterns") or ["data/train-*", "README.md"]),
                local_dir=str(dataset_cfg.get("download_dir")),
                max_workers=int(self.settings.nemotron_download_workers),
                token=self.settings.huggingface_api_key,
            )
            resolved_path = self.resolve_dataset_path(country)
            self._set_runtime_status(
                country,
                {
                    "download_status": "ready",
                    "download_error": None,
                    "resolved_dataset_path": resolved_path,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._set_runtime_status(
                country,
                {
                    "download_status": "error",
                    "download_error": str(exc).strip() or exc.__class__.__name__,
                    "resolved_dataset_path": None,
                },
            )

    def _missing_dataset_detail(self, country: str, *, invalid_local: bool) -> dict[str, Any]:
        status = self.country_status(country)
        if invalid_local:
            return {
                "code": "country_dataset_invalid",
                "message": f"The configured dataset for '{country}' is present locally but does not expose the required schema.",
                "country": country,
                "download_required": True,
                "download_status": status["download_status"],
                "missing_dependency": status["missing_dependency"],
            }
        return {
            "code": "country_dataset_missing",
            "message": f"The dataset for '{country}' is not downloaded yet.",
            "country": country,
            "download_required": True,
            "download_status": status["download_status"],
            "missing_dependency": status["missing_dependency"],
        }

    def _resolve_declared_local_dataset_path(self, country_cfg: dict[str, Any]) -> tuple[str | None, bool]:
        dataset_cfg = self.config.get_country_dataset_config(country_cfg)
        local_paths = list(dataset_cfg.get("local_paths") or [])
        required_columns = list(dataset_cfg.get("required_columns") or [self.metadata.geography_field(country_cfg)])
        saw_existing_candidate = False

        for raw_path in local_paths:
            source = str(raw_path or "").strip()
            if not source:
                continue
            resolved_candidates = self._expand_dataset_candidates(source)
            for candidate in resolved_candidates:
                saw_existing_candidate = True
                try:
                    return self.config.resolve_dataset_path(candidate, required_columns=required_columns), False
                except FileNotFoundError:
                    continue
        return None, saw_existing_candidate

    def _expand_dataset_candidates(self, source: str) -> list[str]:
        path = Path(source).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates = [REPO_ROOT / path, BACKEND_DIR / path] + candidates

        resolved: list[str] = []
        for candidate in candidates:
            if candidate.exists():
                resolved.append(str(candidate.resolve()))
                continue
            if candidate.parent.exists():
                matches = sorted(candidate.parent.glob(candidate.name))
                if matches:
                    if len(matches) == 1:
                        resolved.append(str(matches[0].resolve()))
                    else:
                        resolved.append(str((candidate.parent.resolve() / candidate.name)))
        return list(dict.fromkeys(resolved))

    def _runtime_status(self, country: str) -> dict[str, Any]:
        with _STATUS_LOCK:
            return dict(_DOWNLOAD_STATUS.get(country, {}))

    def _set_runtime_status(self, country: str, status: dict[str, Any]) -> None:
        with _STATUS_LOCK:
            current = dict(_DOWNLOAD_STATUS.get(country, {}))
            current.update(status)
            _DOWNLOAD_STATUS[country] = current
