from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService


GENERIC_GEOGRAPHY_FIELDS = ("planning_area", "state", "province", "region", "district", "county", "city", "territory", "area")


def _slug(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _humanize_slug_value(value: Any) -> str:
    parts = [
        part
        for part in re.split(r"[_\-]+", str(value or "").strip())
        if part
    ]
    words: list[str] = []
    for part in parts:
        if part[:1].isalpha():
            words.append(part[:1].upper() + part[1:].lower())
        else:
            words.append(part.lower())
    return " ".join(words).strip()


@dataclass
class CountryMetadataService:
    settings: Settings
    config: ConfigService = field(init=False)

    def __post_init__(self) -> None:
        self.config = ConfigService(self.settings)

    def country_payload(self, country: str | dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(country, dict):
            return country
        if not country:
            return {}
        return self.config.get_country(country)

    def geography_config(self, country: str | dict[str, Any] | None) -> dict[str, Any]:
        payload = self.country_payload(country)
        raw = payload.get("geography")
        if isinstance(raw, dict):
            return raw

        field_name = ""
        for key in ("filter_fields", "filterable_columns"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for item in rows:
                if not isinstance(item, dict):
                    continue
                candidate = str(item.get("field") or "").strip().lower()
                if candidate in GENERIC_GEOGRAPHY_FIELDS:
                    field_name = candidate
                    break
            if field_name:
                break
        return {
            "field": field_name or "planning_area",
            "label": (field_name or "planning_area").replace("_", " ").title(),
            "values": [],
            "groups": [],
        }

    def geography_field(self, country: str | dict[str, Any] | None) -> str:
        return str(self.geography_config(country).get("field") or "planning_area").strip().lower() or "planning_area"

    def geography_label(self, country: str | dict[str, Any] | None) -> str:
        return str(self.geography_config(country).get("label") or self.geography_field(country)).strip()

    def geography_values(self, country: str | dict[str, Any] | None) -> list[dict[str, Any]]:
        rows = self.geography_config(country).get("values")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def geography_groups(self, country: str | dict[str, Any] | None) -> list[dict[str, Any]]:
        rows = self.geography_config(country).get("groups")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def geography_options(self, country: str | dict[str, Any] | None) -> list[str]:
        options: list[str] = []
        seen: set[str] = set()
        for row in self.geography_values(country):
            label = str(row.get("label") or row.get("code") or "").strip()
            if not label:
                continue
            lowered = label.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            options.append(label)
        return options

    def normalize_geography_values(self, country: str | dict[str, Any] | None, values: Any) -> list[str]:
        if not isinstance(values, list):
            values = [values]

        code_by_alias: dict[str, str] = {}
        members_by_alias: dict[str, list[str]] = {}

        for row in self.geography_values(country):
            code = str(row.get("code") or row.get("label") or "").strip()
            label = str(row.get("label") or code).strip()
            if not code:
                continue
            aliases = [code, label, *(row.get("aliases") or [])]
            for alias in aliases:
                key = _slug(alias)
                if key:
                    code_by_alias[key] = code

        for row in self.geography_groups(country):
            members = [str(item).strip() for item in (row.get("members") or []) if str(item).strip()]
            if not members:
                continue
            aliases = [row.get("code"), row.get("label"), *((row.get("aliases") or []))]
            for alias in aliases:
                key = _slug(alias)
                if key:
                    members_by_alias[key] = members

        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values:
            text = str(raw or "").strip()
            if not text:
                continue
            key = _slug(text)
            expanded = members_by_alias.get(key)
            if expanded:
                for member in expanded:
                    if member not in seen:
                        seen.add(member)
                        normalized.append(member)
                continue
            code = code_by_alias.get(key)
            candidate = code or text
            if candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
        return normalized

    def display_geography_value(self, country: str | dict[str, Any] | None, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "Unknown"
        key = _slug(text)
        for row in self.geography_values(country):
            code = str(row.get("code") or row.get("label") or "").strip()
            label = str(row.get("label") or code).strip()
            aliases = [code, label, *(row.get("aliases") or [])]
            if any(_slug(alias) == key for alias in aliases):
                return label or code
        return text

    def is_geography_field(self, country: str | dict[str, Any] | None, field_name: str) -> bool:
        return _slug(field_name) == self.geography_field(country)

    def text_cleaning_config(self, country: str | dict[str, Any] | None) -> dict[str, Any]:
        payload = self.country_payload(country)
        raw = payload.get("text_cleaning")
        return raw if isinstance(raw, dict) else {}

    def categorical_field_cleaning(self, country: str | dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        raw = self.text_cleaning_config(country).get("categorical_fields")
        if not isinstance(raw, dict):
            return {}
        cleaned: dict[str, dict[str, Any]] = {}
        for field_name, config in raw.items():
            key = str(field_name or "").strip()
            if key and isinstance(config, dict):
                cleaned[key] = config
        return cleaned

    def clean_categorical_value(self, country: str | dict[str, Any] | None, field_name: str, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        config = self.categorical_field_cleaning(country).get(str(field_name or "").strip())
        if not isinstance(config, dict):
            return text

        overrides = config.get("overrides")
        if isinstance(overrides, dict):
            override_lookup = {
                _slug(raw_key): str(raw_value).strip()
                for raw_key, raw_value in overrides.items()
                if str(raw_key).strip() and str(raw_value).strip()
            }
            override = override_lookup.get(_slug(text))
            if override:
                return override

        strategy = str(config.get("strategy") or "").strip().lower()
        if strategy in {"preserve", "identity", ""}:
            return text
        if strategy == "geography_display":
            return self.display_geography_value(country, text)
        if strategy == "slug_title":
            return _humanize_slug_value(text) or text
        return text
