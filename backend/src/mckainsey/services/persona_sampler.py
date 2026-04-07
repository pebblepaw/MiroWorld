from __future__ import annotations

from dataclasses import dataclass
import random
import re
from pathlib import Path
from typing import Any, cast

import duckdb
from datasets import load_dataset
from huggingface_hub import snapshot_download

from mckainsey.config import BACKEND_DIR
from mckainsey.models.phase_a import PersonaFilterRequest


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
        min_age: int | None = None,
        max_age: int | None = None,
        planning_areas: list[str] | None = None,
        sexes: list[str] | None = None,
        marital_statuses: list[str] | None = None,
        education_levels: list[str] | None = None,
        occupations: list[str] | None = None,
        industries: list[str] | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        parquet_glob = self._local_parquet_glob()
        where_clauses: list[str] = []

        if min_age is not None:
            where_clauses.append(f"age >= {min_age}")
        if max_age is not None:
            where_clauses.append(f"age <= {max_age}")
        if planning_areas:
            where_clauses.append(f"planning_area IN ({', '.join(_sql_quote(v) for v in planning_areas)})")
        if sexes:
            where_clauses.append(f"sex IN ({', '.join(_sql_quote(v) for v in sexes)})")
        if marital_statuses:
            where_clauses.append(f"marital_status IN ({', '.join(_sql_quote(v) for v in marital_statuses)})")
        if education_levels:
            where_clauses.append(f"education_level IN ({', '.join(_sql_quote(v) for v in education_levels)})")
        if occupations:
            where_clauses.append(f"occupation IN ({', '.join(_sql_quote(v) for v in occupations)})")
        if industries:
            where_clauses.append(f"industry IN ({', '.join(_sql_quote(v) for v in industries)})")
        where_clauses.extend(_build_dynamic_filter_clauses(extra_filters))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        order_expr = f"hash(coalesce(uuid, persona, occupation, planning_area, '') || '{seed}')"
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
            if req.planning_areas and row.get("planning_area") not in set(req.planning_areas):
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

        if req.min_age is not None:
            where_clauses.append(f"age >= {req.min_age}")
        if req.max_age is not None:
            where_clauses.append(f"age <= {req.max_age}")
        if req.planning_areas:
            quoted = ", ".join(_sql_quote(v) for v in req.planning_areas)
            where_clauses.append(f"planning_area IN ({quoted})")
        if req.income_brackets:
            quoted = ", ".join(_sql_quote(v) for v in req.income_brackets)
            where_clauses.append(f"income_bracket IN ({quoted})")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        parquet_glob = self._local_parquet_glob()
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
        "planning_area",
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
            values = [str(value).strip() for value in raw_value if str(value).strip()]
            if values:
                clauses.append(f"{identifier} IN ({', '.join(_sql_quote(value) for value in values)})")
            continue

        scalar = str(raw_value).strip()
        if scalar:
            clauses.append(f"{identifier} = {_sql_quote(scalar)}")
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
