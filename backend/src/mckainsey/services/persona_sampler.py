from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import duckdb
from datasets import load_dataset

from mckainsey.models.phase_a import PersonaFilterRequest


@dataclass
class PersonaSampler:
    dataset_name: str
    split: str

    def sample(self, req: PersonaFilterRequest) -> list[dict[str, Any]]:
        if req.mode == "duckdb":
            return self._sample_duckdb(req)
        return self._sample_stream(req)

    def _sample_stream(self, req: PersonaFilterRequest) -> list[dict[str, Any]]:
        ds = load_dataset(self.dataset_name, split=self.split, streaming=True)

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

        filtered = ds.filter(_matches).shuffle(seed=42, buffer_size=10_000)
        return [dict(item) for item in filtered.take(req.limit)]

    def _sample_duckdb(self, req: PersonaFilterRequest) -> list[dict[str, Any]]:
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

        query = f"""
            SELECT *
            FROM 'hf://datasets/{self.dataset_name}/data/*.parquet'
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
