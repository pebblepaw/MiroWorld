from __future__ import annotations

from dataclasses import dataclass
import random
import re
from pathlib import Path
from typing import Any, cast

import duckdb
from datasets import load_dataset
from huggingface_hub import snapshot_download

from miroworld.config import BACKEND_DIR
from miroworld.models.phase_a import PersonaFilterRequest


REPO_ROOT = BACKEND_DIR.parent


@dataclass
class PersonaSampler:
    dataset_name: str
    split: str
    cache_dir: str | None = None
    download_workers: int = 4

    def sample(self, req: PersonaFilterRequest) -> list[dict[str, Any]]:
        if req.mode in {"local", "duckdb"}:
            try:
                return self._sample_local_parquet(req)
            except Exception:
                if req.mode == "duckdb":
                    raise
        return self._sample_stream(req)

    def _local_parquet_glob(self) -> str:
        base_dir = Path(self.cache_dir or ".cache/nemotron")
        base_dir.mkdir(parents=True, exist_ok=True)
        local_parquet_files = sorted((base_dir / "data").glob("train-*"))
        if local_parquet_files:
            return str(base_dir / "data" / "train-*")
        snapshot_path = Path(
            snapshot_download(
                repo_id=self.dataset_name,
                repo_type="dataset",
                allow_patterns=["data/train-*", "README.md"],
                local_dir=str(base_dir),
                max_workers=self.download_workers,
            )
        )
        parquet_files = sorted(snapshot_path.glob("data/train-*"))
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files downloaded for {self.dataset_name}")
        return str(snapshot_path / "data" / "train-*")

    def query_candidates(
        self,
        *,
        limit: int,
        seed: int,
        dataset_path: str | None = None,
        country_values: list[str] | None = None,
        geography_field: str | None = None,
        geography_values: list[str] | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        sexes: list[str] | None = None,
        marital_statuses: list[str] | None = None,
        education_levels: list[str] | None = None,
        occupations: list[str] | None = None,
        industries: list[str] | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        parquet_glob = self._resolve_filter_inference_source(dataset_path) if dataset_path else self._local_parquet_glob()
        available_columns = self._parquet_columns(parquet_glob)
        location_column = geography_field if geography_field in available_columns else _resolve_location_column(available_columns)
        country_column = "country" if "country" in available_columns else None
        where_clauses: list[str] = []

        if min_age is not None:
            where_clauses.append(f"age >= {min_age}")
        if max_age is not None:
            where_clauses.append(f"age <= {max_age}")
        if country_values and country_column is not None:
            normalized_countries = [str(value).strip().lower() for value in country_values if str(value).strip()]
            if normalized_countries:
                where_clauses.append(_build_text_in_clause(country_column, normalized_countries))
        if geography_values and location_column is not None:
            normalized_locations = _normalize_filter_values_for_column(location_column, geography_values)
            if normalized_locations:
                where_clauses.append(_build_text_in_clause(location_column, normalized_locations))
        if sexes:
            where_clauses.append(_build_text_in_clause("sex", sexes))
        if marital_statuses:
            where_clauses.append(_build_text_in_clause("marital_status", marital_statuses))
        if education_levels:
            where_clauses.append(_build_text_in_clause("education_level", education_levels))
        if occupations:
            where_clauses.append(_build_text_in_clause("occupation", occupations))
        if industries:
            where_clauses.append(_build_text_in_clause("industry", industries))
        where_clauses.extend(_build_dynamic_filter_clauses(extra_filters))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        order_expr = _seeded_order_expression(available_columns, seed=seed)
        query = f"""
            SELECT *
            FROM read_parquet('{parquet_glob}')
            {where_sql}
            ORDER BY {order_expr}
            LIMIT {limit}
        """

        conn = duckdb.connect()
        try:
            rows = conn.execute(query).fetch_df().to_dict(orient="records")
            if location_column:
                for row in rows:
                    value = row.get(location_column)
                    text = str(value or "").strip()
                    if text:
                        row["geography_field"] = location_column
                        row["geography_value"] = text
                        if location_column != "planning_area":
                            row["planning_area"] = text
            return cast(list[dict[str, Any]], rows)
        finally:
            conn.close()

    def infer_filter_schema(self, *, dataset_path: str, filter_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not filter_fields:
            return []

        parquet_source = self._resolve_filter_inference_source(dataset_path)
        available_columns = self._parquet_columns(parquet_source)

        conn = duckdb.connect()
        try:
            rows: list[dict[str, Any]] = []
            for field_cfg in filter_fields:
                field_name = str(field_cfg.get("field", "")).strip()
                filter_type = str(field_cfg.get("type", "")).strip()
                label = str(field_cfg.get("label", field_name)).strip() or field_name
                if not field_name or not filter_type:
                    continue

                column_name = _normalize_filter_field_name(field_name)
                if column_name not in available_columns:
                    continue

                identifier = _sql_identifier(column_name)
                payload: dict[str, Any] = {
                    "field": field_name,
                    "type": filter_type,
                    "label": label,
                }

                if filter_type == "range":
                    min_max = conn.execute(
                        f"""
                        SELECT MIN({identifier}) AS min_value, MAX({identifier}) AS max_value
                        FROM read_parquet({_sql_quote(parquet_source)})
                        """
                    ).fetchone()
                    if min_max:
                        payload["min"] = min_max[0]
                        payload["max"] = min_max[1]
                    if "default_min" in field_cfg:
                        payload["default_min"] = field_cfg.get("default_min")
                    if "default_max" in field_cfg:
                        payload["default_max"] = field_cfg.get("default_max")
                else:
                    values = conn.execute(
                        f"""
                        SELECT DISTINCT CAST({identifier} AS VARCHAR) AS value
                        FROM read_parquet({_sql_quote(parquet_source)})
                        WHERE {identifier} IS NOT NULL
                          AND TRIM(CAST({identifier} AS VARCHAR)) <> ''
                        ORDER BY value
                        LIMIT 500
                        """
                    ).fetchall()
                    payload["options"] = [str(value[0]) for value in values if value and str(value[0]).strip()]
                    if "default" in field_cfg:
                        payload["default"] = field_cfg.get("default")
                rows.append(payload)
            return rows
        finally:
            conn.close()

    def _sample_stream(self, req: PersonaFilterRequest) -> list[dict[str, Any]]:
        ds = load_dataset(self.dataset_name, split=self.split, streaming=True)
        rng = random.Random(42)

        def _matches(row: dict[str, Any]) -> bool:
            age = row.get("age")
            if req.min_age is not None and (age is None or age < req.min_age):
                return False
            if req.max_age is not None and (age is None or age > req.max_age):
                return False
            location_value = _row_location_value(row)
            if req.planning_areas and location_value not in set(req.planning_areas):
                return False
            row_income = row.get("income_bracket")
            if req.income_brackets and row_income not in {None, ""} and row_income not in set(req.income_brackets):
                return False
            return True

        matches: list[dict[str, Any]] = []
        matched_rows = 0
        target_matches = max(req.limit * 2, req.limit)
        for row in ds:
            if not _matches(row):
                continue
            matched_rows += 1
            item = dict(row)
            if len(matches) < req.limit:
                matches.append(item)
            else:
                replacement_index = rng.randint(0, matched_rows - 1)
                if replacement_index < req.limit:
                    matches[replacement_index] = item
            if matched_rows >= target_matches and len(matches) >= req.limit:
                break
        return matches

    def _sample_local_parquet(self, req: PersonaFilterRequest) -> list[dict[str, Any]]:
        where_clauses: list[str] = []
        parquet_glob = self._local_parquet_glob()
        available_columns = self._parquet_columns(parquet_glob)
        location_column = _resolve_location_column(available_columns)

        if req.min_age is not None:
            where_clauses.append(f"age >= {req.min_age}")
        if req.max_age is not None:
            where_clauses.append(f"age <= {req.max_age}")
        if req.planning_areas and location_column is not None:
            where_clauses.append(_build_text_in_clause(location_column, req.planning_areas))
        if req.income_brackets:
            where_clauses.append(_build_text_in_clause("income_bracket", req.income_brackets))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT *
            FROM '{parquet_glob}'
            {where_sql}
            ORDER BY RANDOM()
            LIMIT {req.limit}
        """

        conn = duckdb.connect()
        try:
            try:
                rows = conn.execute(query).fetch_df().to_dict(orient="records")
            except Exception as exc:
                if req.income_brackets and "income_bracket" in str(exc).lower():
                    retry_clauses = [clause for clause in where_clauses if "income_bracket" not in clause]
                    retry_where_sql = ""
                    if retry_clauses:
                        retry_where_sql = "WHERE " + " AND ".join(retry_clauses)
                    retry_query = f"""
                        SELECT *
                        FROM '{parquet_glob}'
                        {retry_where_sql}
                        ORDER BY RANDOM()
                        LIMIT {req.limit}
                    """
                    rows = conn.execute(retry_query).fetch_df().to_dict(orient="records")
                else:
                    raise
            return cast(list[dict[str, Any]], rows)
        finally:
            conn.close()

    def _resolve_filter_inference_source(self, dataset_path: str) -> str:
        source = str(dataset_path or "").strip()
        if not source:
            raise FileNotFoundError(f"Dataset path not found for filter inference: {dataset_path}")

        path = Path(source).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates = [REPO_ROOT / path, BACKEND_DIR / path] + candidates

        for candidate in candidates:
            resolved = self._resolve_filter_candidate(candidate)
            if resolved is not None:
                return resolved

        raise FileNotFoundError(f"Dataset path not found for filter inference: {dataset_path}")

    def _resolve_filter_candidate(self, candidate: Path) -> str | None:
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

    def _parquet_columns(self, parquet_source: str) -> set[str]:
        conn = duckdb.connect()
        try:
            rows = conn.execute(
                f"DESCRIBE SELECT * FROM read_parquet({_sql_quote(parquet_source)})"
            ).fetchall()
            return {str(row[0]) for row in rows}
        finally:
            conn.close()


def _sql_quote(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _sql_identifier(name: str) -> str:
    cleaned = str(name or "").strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", cleaned):
        raise ValueError(f"Invalid filter field name: {name!r}")
    return f'"{cleaned}"'


def _build_dynamic_filter_clauses(extra_filters: dict[str, Any] | None) -> list[str]:
    if not extra_filters:
        return []

    clauses: list[str] = []
    reserved_fields = {
        "min_age",
        "max_age",
        "sex",
        "marital_status",
        "education_level",
        "occupation",
        "industry",
        "age",
    }
    for raw_field, raw_value in (extra_filters or {}).items():
        field = str(raw_field or "").strip()
        if not field or field in reserved_fields:
            continue
        column_name = _normalize_filter_field_name(field)
        identifier = _sql_identifier(column_name)

        if isinstance(raw_value, dict):
            range_clauses: list[str] = []
            if raw_value.get("min") is not None:
                min_value = _numeric_literal(raw_value.get("min"))
                if min_value is not None:
                    range_clauses.append(f"{identifier} >= {min_value}")
            if raw_value.get("max") is not None:
                max_value = _numeric_literal(raw_value.get("max"))
                if max_value is not None:
                    range_clauses.append(f"{identifier} <= {max_value}")
            clauses.extend(range_clauses)
            continue

        if isinstance(raw_value, list):
            values = _normalize_filter_values_for_column(column_name, raw_value)
            if values:
                clauses.append(_build_text_in_clause(column_name, values))
            continue

        scalar_values = _normalize_filter_values_for_column(column_name, [raw_value])
        scalar = scalar_values[0] if scalar_values else ""
        if scalar:
            clauses.append(_build_text_equals_clause(column_name, scalar))
    return clauses


def _numeric_literal(value: Any) -> str | None:
    try:
        numeric = float(value)
    except Exception:  # noqa: BLE001
        return None
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def _normalize_filter_field_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if normalized == "gender":
        return "sex"
    return normalized


def _normalize_filter_values_for_column(column_name: str, values: list[Any]) -> list[str]:
    normalized_values: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        normalized_values.append(text.lower())
    return normalized_values


def _resolve_location_column(available_columns: set[str]) -> str | None:
    for field_name in ("planning_area", "state", "province", "region", "district", "city", "county", "territory", "area"):
        if field_name in available_columns:
            return field_name
    return None


def _seeded_order_expression(available_columns: set[str], *, seed: int) -> str:
    location_column = _resolve_location_column(available_columns)
    candidate_columns = [
        column
        for column in ("uuid", "persona", "occupation", "age")
        if column in available_columns
    ]
    if location_column and location_column not in candidate_columns:
        candidate_columns.append(location_column)
    if not candidate_columns:
        return f"hash('{seed}')"

    parts = [f"coalesce(CAST({_sql_identifier(column)} AS VARCHAR), '')" for column in candidate_columns]
    return f"hash({' || '.join(parts)} || '{seed}')"


def _build_text_in_clause(column_name: str, values: list[Any]) -> str:
    identifier = _sql_identifier(column_name)
    normalized_values = [str(value).strip().lower() for value in values if str(value).strip()]
    return f"lower(CAST({identifier} AS VARCHAR)) IN ({', '.join(_sql_quote(value) for value in normalized_values)})"


def _build_text_equals_clause(column_name: str, value: Any) -> str:
    identifier = _sql_identifier(column_name)
    normalized_value = str(value).strip().lower()
    return f"lower(CAST({identifier} AS VARCHAR)) = {_sql_quote(normalized_value)}"


def _row_location_value(row: dict[str, Any]) -> str | None:
    location_column = _resolve_location_column(set(row.keys()))
    if not location_column:
        return None
    text = str(row.get(location_column) or "").strip()
    return text or None
