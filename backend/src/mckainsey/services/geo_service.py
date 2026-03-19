from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mckainsey.config import Settings


class PlanningAreaGeoService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache_path = Path(settings.planning_area_geojson_cache_path)

    def get_geojson(self, force_refresh: bool = False) -> dict[str, Any]:
        if self.cache_path.exists() and not force_refresh:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))

        payload = self._download_geojson()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _download_geojson(self) -> dict[str, Any]:
        endpoint = (
            "https://api-open.data.gov.sg/v1/public/api/datasets/"
            f"{self.settings.planning_area_dataset_id}/poll-download"
        )
        metadata: dict[str, Any] | None = None

        def _try_poll_download(use_key: bool) -> dict[str, Any]:
            req = Request(endpoint, method="GET")
            req.add_header("User-Agent", "Mozilla/5.0")
            req.add_header("Accept", "application/json")
            if use_key and self.settings.datagov_api_key:
                req.add_header("x-api-key", self.settings.datagov_api_key)
            with urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            metadata = _try_poll_download(use_key=True)
        except HTTPError as exc:
            # Some public Data.gov datasets reject API-key headers for poll-download.
            if exc.code == 403 and self.settings.datagov_api_key:
                try:
                    metadata = _try_poll_download(use_key=False)
                except (HTTPError, URLError) as retry_exc:
                    if self.cache_path.exists():
                        return json.loads(self.cache_path.read_text(encoding="utf-8"))
                    raise RuntimeError(f"Failed to fetch planning-area dataset URL: {retry_exc}") from retry_exc
            else:
                if self.cache_path.exists():
                    return json.loads(self.cache_path.read_text(encoding="utf-8"))
                raise RuntimeError(f"Failed to fetch planning-area dataset URL: {exc}") from exc
        except URLError as exc:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            raise RuntimeError(f"Failed to fetch planning-area dataset URL: {exc}") from exc

        download_url = metadata.get("data", {}).get("url")
        if not download_url:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            raise RuntimeError("Data.gov poll-download returned no URL for planning-area dataset.")

        try:
            dl_req = Request(download_url, method="GET")
            dl_req.add_header("User-Agent", "Mozilla/5.0")
            with urlopen(dl_req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            raise RuntimeError(f"Failed to download planning-area GeoJSON: {exc}") from exc

        if payload.get("type") != "FeatureCollection":
            raise RuntimeError("Downloaded planning-area payload is not a GeoJSON FeatureCollection.")

        for feature in payload.get("features", []):
            props = feature.setdefault("properties", {})
            candidate = (
                props.get("name")
                or props.get("PLN_AREA_N")
                or props.get("planning_area")
                or props.get("Planning Area")
            )
            if candidate:
                props["name"] = str(candidate).upper()

        return payload
