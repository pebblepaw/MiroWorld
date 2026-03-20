from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path
from typing import Any, cast

import duckdb
from datasets import load_dataset
from huggingface_hub import snapshot_download

from mckainsey.models.phase_a import PersonaFilterRequest


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
            if req.income_brackets and row.get("income_bracket") not in set(req.income_brackets):
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
            rows = conn.execute(query).fetch_df().to_dict(orient="records")
            return cast(list[dict[str, Any]], rows)
        finally:
            conn.close()


def _sql_quote(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
