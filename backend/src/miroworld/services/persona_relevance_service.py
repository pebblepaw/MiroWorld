from __future__ import annotations

import ast
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService
from miroworld.services.country_metadata_service import CountryMetadataService, GENERIC_GEOGRAPHY_FIELDS
from miroworld.services.lightrag_service import (
    AGE_COHORT_ALIASES,
    EDUCATION_LEVEL_ALIASES,
    HOBBY_SLUGS,
    INDUSTRY_SLUGS,
    MARITAL_STATUS_ALIASES,
    OCCUPATION_SLUGS,
    SEX_ALIASES,
    SKILL_SLUGS,
)
from miroworld.services.llm_client import GeminiChatClient, GeminiEmbeddingClient


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_]+")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "their",
    "about",
    "support",
    "singapore",
}
SHORT_TEXT_FIELDS = (
    "planning_area",
    "sex",
    "marital_status",
    "education_level",
    "occupation",
    "industry",
    "skills_and_expertise_list",
    "hobbies_and_interests_list",
)
LONG_TEXT_FIELDS = (
    "travel_persona",
    "sports_persona",
    "professional_persona",
    "persona",
    "arts_persona",
    "cultural_background",
    "skills_and_expertise",
    "career_goals_and_ambitions",
)
EMPTY_PARSED_INSTRUCTIONS = {
    "hard_filters": {},
    "soft_boosts": {},
    "soft_penalties": {},
    "exclusions": {},
    "distribution_targets": {},
    "notes_for_ui": [],
    "source": "none",
}
SUPPORTED_INSTRUCTION_FIELDS = {
    "planning_area",
    "state",
    "sex",
    "age_cohort",
    "min_age",
    "max_age",
    "education_level",
    "marital_status",
    "occupation",
    "industry",
    "hobby",
    "skill",
}
MAX_SHORTLIST_SIZE = 300
MAX_SEMANTIC_RERANK_SIZE = 48
EDUCATION_WORKER_ALIASES = (
    "educator",
    "educators",
    "teacher",
    "teachers",
    "lecturer",
    "lecturers",
    "school staff",
    "school workers",
)
NAME_FIELD_PATTERN = re.compile(
    r"(?:\bname\b|\bfull name\b|\bpersona name\b|\bcharacter name\b)\s*[:\-]\s*([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})",
    flags=re.IGNORECASE,
)
NAME_WITH_VERB_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:grew|works|is|was|lives|resides|studies|believes|prefers)\b"
)
CAPITALIZED_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")
LEADING_NOISE_PATTERN = re.compile(r"^(?:At\s+\d{1,3},?\s*|In\s+\d{4},?\s*)+", flags=re.IGNORECASE)
NAME_TOKEN_PATTERN = re.compile(
    r"(?:[A-Z][A-Za-z'\-]+|[A-Z]\.|\([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*\))"
)
LEADING_NAME_TOKEN_PATTERN = re.compile(
    r"^(?P<token>[A-Z][A-Za-z'\-]+|[A-Z]\.|\([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*\))(?P<suffix>\s+|$)"
)
PERSONA_NAME_FIELDS = (
    "travel_persona",
    "sports_persona",
    "persona",
    "professional_persona",
    "arts_persona",
    "cultural_background",
)


@dataclass
class PersonaRelevanceService:
    settings: Settings
    llm: GeminiChatClient = field(init=False)
    embeddings: GeminiEmbeddingClient = field(init=False)

    def __post_init__(self) -> None:
        self.llm = GeminiChatClient(self.settings)
        self.embeddings = GeminiEmbeddingClient(self.settings)
        self.config = ConfigService(self.settings)
        self.countries = CountryMetadataService(self.settings)

    def _country_geography_field(self, country: str | None) -> str:
        try:
            return self.countries.geography_field(country)
        except Exception:  # noqa: BLE001
            return "planning_area"

    def _persona_geography_value(
        self,
        persona: dict[str, Any],
        geography_field: str | None = None,
        *,
        country: str | None = None,
    ) -> str:
        display_value = str(persona.get("geography_value") or "").strip()
        if display_value:
            return display_value

        resolved_field = str(geography_field or persona.get("geography_field") or "").strip().lower()
        if not resolved_field and country:
            resolved_field = self._country_geography_field(country)

        if resolved_field:
            raw_value = persona.get(resolved_field)
            text = str(raw_value or "").strip()
            if text:
                return self.countries.display_geography_value(country, text)

        fallback = str(persona.get("planning_area") or "").strip()
        if fallback:
            return fallback
        return "Unknown"

    def _prepare_persona(self, persona: dict[str, Any], *, geography_field: str, country: str | None) -> dict[str, Any]:
        payload = dict(persona)
        payload["geography_field"] = geography_field

        raw_value = payload.get(geography_field)
        if raw_value is None:
            raw_value = payload.get("geography_value") or payload.get("planning_area")
            if raw_value is not None:
                payload[geography_field] = raw_value

        display_value = self.countries.display_geography_value(country, raw_value)
        if display_value and display_value != "Unknown":
            payload["geography_value"] = display_value
            payload["planning_area"] = display_value

        for field_name in self.countries.categorical_field_cleaning(country):
            if field_name not in payload:
                continue
            cleaned_value = self.countries.clean_categorical_value(country, field_name, payload.get(field_name))
            if cleaned_value:
                payload[field_name] = cleaned_value

        education_value = str(payload.get("education_level") or "").strip()
        if education_value and not str(payload.get("highest_education") or "").strip():
            payload["highest_education"] = education_value
        return payload

    def parse_sampling_instructions(
        self,
        instructions: str | None,
        *,
        knowledge_artifact: dict[str, Any] | None = None,
        live_mode: bool = False,
        country: str | None = None,
    ) -> dict[str, Any]:
        if not instructions or not instructions.strip():
            return dict(EMPTY_PARSED_INSTRUCTIONS)

        cleaned = instructions.strip()
        if not self.llm.is_enabled():
            if live_mode:
                raise RuntimeError("Live sampling instruction parsing requires a configured model provider.")
            raise RuntimeError("Sampling instruction parsing requires a configured model provider.")

        supported_fields = self._supported_instruction_fields(country)
        prompt = self._build_instruction_prompt(cleaned, knowledge_artifact or {}, country=country)
        raw = self.llm.complete_required(
            prompt,
            system_prompt=self.config.get_system_prompt_value(
                "sampling_parser",
                "prompts",
                "parser",
                "system_prompt",
                default="You parse sampling instructions for a population-sampling system. Return valid JSON only.",
            ),
        )
        parsed = self._extract_json_object(raw)
        if not parsed:
            if live_mode:
                raise RuntimeError("Live sampling instruction parsing returned invalid JSON.")
            fallback = self._augment_with_deterministic_constraints(
                cleaned,
                self._fallback_parse_sampling_instructions(cleaned, country=country),
                supported_fields=supported_fields,
                country=country,
            )
            if not fallback.get("notes_for_ui"):
                fallback["notes_for_ui"] = [cleaned]
            return fallback

        normalized = self._normalize_parsed_instructions(
            parsed,
            source=self.llm.provider,
            supported_fields=supported_fields,
            country=country,
        )
        normalized = self._augment_with_deterministic_constraints(
            cleaned,
            normalized,
            supported_fields=supported_fields,
            country=country,
        )
        if self._has_actionable_instruction_signal(normalized):
            return normalized
        if not normalized.get("notes_for_ui"):
            normalized["notes_for_ui"] = [cleaned]
        return normalized

    def score_personas(
        self,
        personas: list[dict[str, Any]],
        *,
        knowledge_artifact: dict[str, Any],
        filters: dict[str, Any],
        parsed_sampling_instructions: dict[str, Any] | None = None,
        shortlist_size: int | None = None,
        semantic_pool_size: int | None = None,
        live_mode: bool = False,
    ) -> list[dict[str, Any]]:
        scored, _ = self.rank_personas(
            personas,
            knowledge_artifact=knowledge_artifact,
            filters=filters,
            parsed_sampling_instructions=parsed_sampling_instructions,
            shortlist_size=shortlist_size,
            semantic_pool_size=semantic_pool_size,
            live_mode=live_mode,
        )
        return scored

    def rank_personas(
        self,
        personas: list[dict[str, Any]],
        *,
        knowledge_artifact: dict[str, Any],
        filters: dict[str, Any],
        parsed_sampling_instructions: dict[str, Any] | None = None,
        shortlist_size: int | None = None,
        semantic_pool_size: int | None = None,
        live_mode: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        parsed = self._normalize_parsed_instructions(parsed_sampling_instructions, source=(parsed_sampling_instructions or {}).get("source", "runtime"))
        issue_profile = self._build_issue_profile(knowledge_artifact, parsed)
        default_shortlist_size = max(60, min(len(personas), MAX_SHORTLIST_SIZE))
        default_semantic_pool_size = max(30, min(len(personas), MAX_SEMANTIC_RERANK_SIZE))
        shortlist_size = min(
            len(personas),
            min(int(shortlist_size or default_shortlist_size), MAX_SHORTLIST_SIZE),
        )
        semantic_pool_size = min(
            len(personas),
            shortlist_size,
            min(int(semantic_pool_size or default_semantic_pool_size), MAX_SEMANTIC_RERANK_SIZE),
        )

        short_docs = [self._persona_short_doc(persona) for persona in personas]
        bm25_payload = self._bm25_scores(issue_profile["bm25_terms"], short_docs)
        bm25_scores = bm25_payload["scores"]
        bm25_matches = bm25_payload["matches"]

        prelim_rows: list[dict[str, Any]] = []
        for index, persona in enumerate(personas):
            (
                matched_facets,
                instruction_matches,
                penalty_matches,
                distribution_matches,
                entity_matches,
                structured_alignment,
                excluded,
            ) = self._collect_matches(
                issue_profile,
                persona,
                filters=filters,
                parsed_sampling_instructions=parsed,
            )
            if excluded:
                continue
            geographic = self._geographic_relevance(issue_profile, persona)
            socioeconomic = self._socioeconomic_relevance(issue_profile, persona)
            digital = self._digital_behavior_relevance(issue_profile, persona)
            filter_alignment = self._filter_alignment(filters, persona)
            lexical_semantic = self._semantic_relevance(issue_profile, persona)
            bm25_score = bm25_scores[index]
            instruction_alignment = self._bounded_score((len(instruction_matches) * 0.24) + (len(distribution_matches) * 0.18))
            penalty_pressure = self._bounded_score(len(penalty_matches) * 0.22)

            prelim_rows.append(
                {
                    "persona": persona,
                    "index": index,
                    "pre_score": round(
                        (structured_alignment * 0.30)
                        + (bm25_score * 0.25)
                        + (lexical_semantic * 0.20)
                        + (geographic * 0.10)
                        + (socioeconomic * 0.10)
                        + (instruction_alignment * 0.12)
                        - (penalty_pressure * 0.12)
                        + (filter_alignment * 0.05),
                        4,
                    ),
                    "matched_facets": matched_facets,
                    "instruction_matches": instruction_matches,
                    "penalty_matches": penalty_matches,
                    "distribution_matches": distribution_matches,
                    "entity_matches": entity_matches,
                    "component_scores": {
                        "bm25_relevance": bm25_score,
                        "semantic_relevance": lexical_semantic,
                        "geographic_relevance": geographic,
                        "socioeconomic_relevance": socioeconomic,
                        "digital_behavior_relevance": digital,
                        "filter_alignment": filter_alignment,
                        "instruction_alignment": instruction_alignment,
                        "penalty_pressure": penalty_pressure,
                    },
                    "bm25_terms": bm25_matches[index],
                }
            )

        prelim_rows.sort(key=lambda row: row["pre_score"], reverse=True)
        shortlist_rows = prelim_rows[:shortlist_size]
        semantic_rows = shortlist_rows[:semantic_pool_size]
        semantic_scores = self._semantic_rerank(
            issue_profile["semantic_query"],
            [row["persona"] for row in semantic_rows],
            live_mode=live_mode,
        )

        scored: list[dict[str, Any]] = []
        semantic_index_map = {
            semantic_rows[idx]["index"]: semantic_scores[idx]
            for idx in range(min(len(semantic_rows), len(semantic_scores)))
        }
        for row in prelim_rows:
            index = row["index"]
            semantic_score = semantic_index_map.get(index, row["component_scores"]["semantic_relevance"])
            bm25_score = row["component_scores"]["bm25_relevance"]
            geographic = row["component_scores"]["geographic_relevance"]
            socioeconomic = row["component_scores"]["socioeconomic_relevance"]
            digital = row["component_scores"]["digital_behavior_relevance"]
            filter_alignment = row["component_scores"]["filter_alignment"]
            instruction_alignment = row["component_scores"]["instruction_alignment"]
            penalty_pressure = row["component_scores"]["penalty_pressure"]
            structured_alignment = self._bounded_score(
                len(row["matched_facets"]) * 0.18
                + len(row["entity_matches"]) * 0.08
                + len(row["instruction_matches"]) * 0.16
                + len(row["distribution_matches"]) * 0.12
            )

            score = (
                semantic_score * 0.24
                + bm25_score * 0.18
                + structured_alignment * 0.18
                + instruction_alignment * 0.18
                + geographic * 0.12
                + socioeconomic * 0.10
                + digital * 0.02
                + filter_alignment * 0.04
                - penalty_pressure * 0.06
            )

            component_scores = {
                **row["component_scores"],
                "semantic_relevance": round(semantic_score, 4),
            }
            scored.append(
                {
                    "persona": row["persona"],
                    "score": round(score, 4),
                    "component_scores": component_scores,
                    "matched_facets": row["matched_facets"],
                    "matched_document_entities": row["entity_matches"],
                    "instruction_matches": row["instruction_matches"],
                    "bm25_terms": row["bm25_terms"],
                    "semantic_summary": self._build_semantic_summary(
                        matched_facets=row["matched_facets"],
                        entity_matches=row["entity_matches"],
                        instruction_matches=row["instruction_matches"],
                    ),
                }
            )

        scored.sort(key=lambda row: row["score"], reverse=True)
        diagnostics = {
            "candidate_count": len(personas),
            "structured_filter_count": len(personas),
            "shortlist_count": len(shortlist_rows),
            "bm25_shortlist_count": len(shortlist_rows),
            "semantic_rerank_count": len(semantic_rows),
        }
        return scored, diagnostics

    def sample_balanced(
        self,
        scored_personas: list[dict[str, Any]],
        *,
        agent_count: int,
        seed: int | None = None,
        parsed_sampling_instructions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if len(scored_personas) <= agent_count:
            return list(scored_personas)

        rng = random.Random(seed)
        strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in scored_personas:
            persona = row["persona"]
            key = (
                self._persona_geography_value(persona),
                str(persona.get("industry") or persona.get("occupation") or "Unknown"),
                self._age_bucket(persona.get("age")),
            )
            strata[key].append(row)

        total = len(scored_personas)
        quotas = self._allocate_strata_quotas(
            strata,
            total=total,
            agent_count=agent_count,
            seed=seed,
            use_score_bias=True,
            distribution_targets=(parsed_sampling_instructions or {}).get("distribution_targets", {}),
        )
        sampled: list[dict[str, Any]] = []
        for key, rows in strata.items():
            quota = quotas.get(key, 0)
            sampled.extend(self._weighted_sample_without_replacement(rows, quota, rng))
        rng.shuffle(sampled)
        sampled.sort(key=lambda row: row["score"], reverse=True)
        return sampled[:agent_count]

    def sample_population_baseline(
        self,
        scored_personas: list[dict[str, Any]],
        *,
        agent_count: int,
        seed: int | None = None,
        parsed_sampling_instructions: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if len(scored_personas) <= agent_count:
            return list(scored_personas)

        rng = random.Random(seed)
        strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in scored_personas:
            persona = row["persona"]
            key = (
                self._persona_geography_value(persona),
                str(persona.get("sex", "Unknown")),
                self._age_bucket(persona.get("age")),
            )
            strata[key].append(row)

        quotas = self._allocate_strata_quotas(
            strata,
            total=len(scored_personas),
            agent_count=agent_count,
            seed=seed,
            use_score_bias=False,
            distribution_targets=(parsed_sampling_instructions or {}).get("distribution_targets", {}),
        )
        sampled: list[dict[str, Any]] = []
        for key, rows in strata.items():
            quota = quotas.get(key, 0)
            if quota <= 0:
                continue
            chosen = list(rows)
            rng.shuffle(chosen)
            sampled.extend(chosen[:quota])

        rng.shuffle(sampled)
        return sampled[:agent_count]

    def build_population_artifact(
        self,
        session_id: str,
        *,
        personas: list[dict[str, Any]],
        knowledge_artifact: dict[str, Any],
        filters: dict[str, Any],
        agent_count: int,
        sample_mode: str = "affected_groups",
        seed: int | None = None,
        parsed_sampling_instructions: dict[str, Any] | None = None,
        live_mode: bool = False,
        country: str | None = None,
    ) -> dict[str, Any]:
        parsed = self._normalize_parsed_instructions(
            parsed_sampling_instructions,
            source=(parsed_sampling_instructions or {}).get("source", "runtime"),
            country=country,
        )
        geography_field = self._country_geography_field(country)
        prepared_personas = [
            self._prepare_persona(persona, geography_field=geography_field, country=country)
            for persona in personas
        ]
        scored, diagnostics = self.rank_personas(
            prepared_personas,
            knowledge_artifact=knowledge_artifact,
            filters=filters,
            parsed_sampling_instructions=parsed,
            shortlist_size=max(agent_count * 8, 80),
            semantic_pool_size=max(agent_count * 4, 40),
            live_mode=live_mode,
        )
        effective_seed = int(seed if seed is not None else random.randint(1, 2_147_483_647))
        if sample_mode == "population_baseline":
            sampled = self.sample_population_baseline(
                scored,
                agent_count=agent_count,
                seed=effective_seed,
                parsed_sampling_instructions=parsed,
            )
        else:
            sampled = self.sample_balanced(
                scored,
                agent_count=agent_count,
                seed=effective_seed,
                parsed_sampling_instructions=parsed,
            )

        sampled_personas: list[dict[str, Any]] = []
        for index, row in enumerate(sampled):
            persona_payload = self._prepare_persona(row["persona"], geography_field=geography_field, country=country)
            display_name = self._extract_persona_display_name(persona_payload)
            persona_payload["display_name"] = display_name
            sampled_personas.append(
                {
                    "agent_id": f"agent-{index + 1:04d}",
                    "display_name": display_name,
                    "persona": persona_payload,
                    "selection_reason": {
                        "score": row["score"],
                        "selection_score": row["score"],
                        "matched_facets": row["matched_facets"],
                        "matched_document_entities": row["matched_document_entities"],
                        "instruction_matches": row["instruction_matches"],
                        "bm25_terms": row["bm25_terms"],
                        "semantic_summary": row["semantic_summary"],
                        **row["component_scores"],
                    },
                }
            )

        area_counts = Counter(self._persona_geography_value(row["persona"], geography_field, country=country) for row in sampled)
        bucket_counts = Counter(self._age_bucket(row["persona"].get("age")) for row in sampled)
        sex_counts = Counter(str(row["persona"].get("sex", "Unknown")) for row in sampled)

        return {
            "session_id": session_id,
            "candidate_count": len(personas),
            "sample_count": len(sampled_personas),
            "sample_mode": sample_mode,
            "sample_seed": effective_seed,
            "geography_field": geography_field,
            "parsed_sampling_instructions": parsed,
            "coverage": {
                "planning_areas": sorted(area_counts.keys()),
                "geographies": sorted(area_counts.keys()),
                "age_buckets": dict(bucket_counts),
                "sex_distribution": dict(sex_counts),
                "geography_field": geography_field,
            },
            "sampled_personas": sampled_personas,
            "agent_graph": self._build_agent_graph(sampled_personas, geography_field=geography_field),
            "representativeness": {
                "status": "balanced" if len(area_counts) > 1 else "narrow",
                "planning_area_distribution": dict(area_counts),
                "geography_distribution": dict(area_counts),
                "sex_distribution": dict(sex_counts),
                f"{geography_field}_distribution": dict(area_counts),
                "geography_field": geography_field,
            },
            "selection_diagnostics": diagnostics,
        }

    def _build_issue_profile(self, artifact: dict[str, Any], parsed_sampling_instructions: dict[str, Any]) -> dict[str, Any]:
        labels: list[str] = []
        relation_labels: list[str] = []
        facets: dict[str, set[str]] = defaultdict(set)
        document_entities: list[str] = []

        for node in artifact.get("entity_nodes", []):
            if node.get("ui_default_hidden") and not node.get("facet_kind"):
                continue
            label = str(node.get("label", "")).strip()
            display_bucket = str(node.get("display_bucket") or "").strip().lower()
            if label:
                labels.append(label)
                if not node.get("facet_kind") and display_bucket != "location":
                    document_entities.append(label)
            facet_kind, canonical_value = self._node_facet(node)
            if facet_kind and canonical_value:
                facets[facet_kind].add(canonical_value)

        for edge in artifact.get("relationship_edges", []):
            label = str(edge.get("label") or edge.get("raw_relation_text") or edge.get("type") or "").strip()
            if label:
                relation_labels.append(label)

        notes = parsed_sampling_instructions.get("notes_for_ui", [])
        combined_text = " ".join(
            part
            for part in [
                str(artifact.get("summary", "")),
                " ".join(labels),
                " ".join(relation_labels),
                str(artifact.get("demographic_focus_summary", "")),
                " ".join(str(item) for item in notes),
            ]
            if part
        ).strip()
        bm25_terms = sorted(
            {
                *self._tokens(combined_text),
                *{value.replace("_", " ") for values in facets.values() for value in values},
            }
        )

        return {
            "text": combined_text,
            "text_lower": combined_text.lower(),
            "tokens": self._tokens(combined_text),
            "facets": {kind: values for kind, values in facets.items() if values},
            "document_entities": sorted({self._slug(entity).replace("_", " ") for entity in document_entities if entity}),
            "bm25_terms": bm25_terms,
            "semantic_query": combined_text or "population sampling query",
        }

    def _persona_short_doc(self, persona: dict[str, Any]) -> list[str]:
        pieces: list[str] = []
        for field_name in SHORT_TEXT_FIELDS:
            value = persona.get(field_name)
            if value is None:
                continue
            if field_name.endswith("_list"):
                pieces.extend(self._parse_list_field(value))
            else:
                pieces.append(str(value))
        return [token for token in self._tokens(" ".join(pieces))]

    def _persona_long_doc(self, persona: dict[str, Any]) -> str:
        return " ".join(str(persona.get(field, "")) for field in LONG_TEXT_FIELDS if persona.get(field))

    def _semantic_relevance(self, issue_profile: dict[str, Any], persona: dict[str, Any]) -> float:
        issue_tokens = issue_profile["tokens"]
        persona_tokens = self._tokens(self._persona_long_doc(persona) or self._persona_text(persona))
        if not issue_tokens or not persona_tokens:
            return 0.0
        intersection = len(issue_tokens & persona_tokens)
        union = len(issue_tokens | persona_tokens)
        return round(intersection / union, 4) if union else 0.0

    def _semantic_rerank_fallback(self, query_text: str, persona: dict[str, Any]) -> float:
        query_tokens = self._tokens(query_text)
        persona_tokens = self._tokens(self._persona_long_doc(persona) or self._persona_text(persona))
        if not query_tokens or not persona_tokens:
            return 0.0
        intersection = len(query_tokens & persona_tokens)
        union = len(query_tokens | persona_tokens)
        return round(intersection / union, 4) if union else 0.0

    def _semantic_rerank(self, query_text: str, personas: list[dict[str, Any]], *, live_mode: bool = False) -> list[float]:
        candidate_texts = [self._persona_long_doc(persona) for persona in personas]
        if not personas:
            return []
        if not self.embeddings.is_enabled():
            if live_mode:
                raise RuntimeError("Live persona ranking requires configured embeddings.")
            return [self._semantic_rerank_fallback(query_text, persona) for persona in personas]

        try:
            vectors = self.embeddings.embed_texts([query_text, *candidate_texts])
            if len(vectors) != len(candidate_texts) + 1:
                raise RuntimeError("Semantic reranking failed because the embedding response size was invalid.")
            query_vector = vectors[0]
            return [round(self._cosine_similarity(query_vector, vector), 4) for vector in vectors[1:]]
        except Exception as exc:
            if live_mode:
                raise RuntimeError("Live persona ranking failed while computing semantic relevance.") from exc
            return [self._semantic_rerank_fallback(query_text, persona) for persona in personas]

    def _geographic_relevance(self, issue_profile: dict[str, Any], persona: dict[str, Any]) -> float:
        area = self._persona_geography_value(persona).strip().lower()
        if not area:
            return 0.0
        geography_field = str(persona.get("geography_field") or "planning_area").strip().lower()
        geography_targets = issue_profile["facets"].get(geography_field, set()) or issue_profile["facets"].get("planning_area", set())
        if geography_targets:
            return 1.0 if self._slug(area) in geography_targets else 0.05
        return 1.0 if area and area in issue_profile["text_lower"] else 0.2

    def _socioeconomic_relevance(self, issue_profile: dict[str, Any], persona: dict[str, Any]) -> float:
        facets = issue_profile["facets"]
        text_lower = issue_profile["text_lower"]
        score = 0.15
        age = persona.get("age")
        if isinstance(age, (int, float)):
            age_cohort = self._persona_age_cohort(age)
            if age_cohort and age_cohort in facets.get("age_cohort", set()):
                score += 0.3
            elif age >= 60 and "senior" in text_lower:
                score += 0.2

        occupation = str(persona.get("occupation", "")).lower()
        if occupation and self._slug(occupation) in facets.get("occupation", set()):
            score += 0.2
        elif occupation and occupation in text_lower:
            score += 0.1

        industry = str(persona.get("industry", "")).lower()
        if industry and self._slug(industry) in facets.get("industry", set()):
            score += 0.2

        education_level = str(persona.get("education_level", "")).lower()
        if education_level and self._slug(education_level) in facets.get("education_level", set()):
            score += 0.15

        marital_status = str(persona.get("marital_status", "")).lower()
        if marital_status and self._slug(marital_status) in facets.get("marital_status", set()):
            score += 0.1

        sex = str(persona.get("sex", "")).lower()
        if sex and self._slug(sex) in facets.get("sex", set()):
            score += 0.2

        return min(1.0, round(score, 4))

    def _digital_behavior_relevance(self, issue_profile: dict[str, Any], persona: dict[str, Any]) -> float:
        text = self._persona_text(persona).lower()
        if "online" in issue_profile["text_lower"] or "digital" in issue_profile["text_lower"]:
            if "high" in text or "social" in text or "digital" in text:
                return 0.9
        return 0.4

    def _filter_alignment(self, filters: dict[str, Any], persona: dict[str, Any]) -> float:
        score = 1.0
        geography_values = filters.get("geography_values") or filters.get("planning_areas") or []
        persona_geo_candidates = {
            self._persona_geography_value(persona),
            str(persona.get(str(persona.get("geography_field") or "")) or "").strip(),
        }
        if geography_values and not any(candidate in geography_values for candidate in persona_geo_candidates if candidate):
            score -= 0.5
        min_age = filters.get("min_age")
        max_age = filters.get("max_age")
        age = persona.get("age")
        if min_age is not None and isinstance(age, (int, float)) and age < min_age:
            score -= 0.2
        if max_age is not None and isinstance(age, (int, float)) and age > max_age:
            score -= 0.2
        return max(0.0, round(score, 4))

    def _build_agent_graph(self, sampled_personas: list[dict[str, Any]], *, geography_field: str = "planning_area") -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        for row in sampled_personas:
            persona = row["persona"]
            agent_id = row["agent_id"]
            display_name = str(row.get("display_name") or persona.get("display_name") or agent_id)
            geography_value = self._persona_geography_value(persona, geography_field)
            nodes.append(
                {
                    "id": agent_id,
                    "label": display_name,
                    "subtitle": f"{geography_value} · {persona.get('occupation', 'Resident')}",
                    "planning_area": geography_value,
                    "geography_field": geography_field,
                    "geography_value": geography_value,
                    "industry": str(persona.get("industry", "Unknown")),
                    "node_type": "sampled_persona",
                    "score": row["selection_reason"]["score"],
                    "age": persona.get("age"),
                    "sex": persona.get("sex"),
                }
            )

        for index, left in enumerate(sampled_personas):
            for right in sampled_personas[index + 1 :]:
                reasons: list[str] = []
                left_persona = left["persona"]
                right_persona = right["persona"]
                if self._persona_geography_value(left_persona, geography_field) == self._persona_geography_value(right_persona, geography_field):
                    reasons.append("shared_planning_area")
                if left_persona.get("industry") and left_persona.get("industry") == right_persona.get("industry"):
                    reasons.append("shared_industry")
                if left_persona.get("occupation") and left_persona.get("occupation") == right_persona.get("occupation"):
                    reasons.append("shared_occupation")
                if not reasons:
                    continue
                links.append(
                    {
                        "source": left["agent_id"],
                        "target": right["agent_id"],
                        "weight": float(len(reasons)),
                        "reason": reasons[0],
                        "reasons": reasons,
                        "label": ", ".join(reason.replace("_", " ") for reason in reasons),
                    }
                )
        return {"nodes": nodes, "links": links}

    def _extract_persona_display_name(self, persona: dict[str, Any]) -> str:
        for key in ("confirmed_name", "display_name", "name", "full_name"):
            value = persona.get(key)
            if isinstance(value, str):
                candidate = value.strip()
                if self._is_valid_display_name(candidate):
                    return candidate

        candidates: list[str] = []
        combined_sections: list[str] = []
        for field_name in PERSONA_NAME_FIELDS:
            raw_text = str(persona.get(field_name, "") or "").strip()
            if not raw_text:
                continue
            combined_sections.append(raw_text)
            candidate = self._extract_name_candidate_from_text(raw_text)
            if candidate:
                candidates.append(candidate)

        if candidates:
            ordered_counts = Counter(candidates)
            first_seen = {candidate: index for index, candidate in enumerate(candidates)}
            return max(
                ordered_counts,
                key=lambda candidate: (ordered_counts[candidate], -first_seen[candidate], len(candidate)),
            )

        persona_text = "\n".join(combined_sections)
        if persona_text:
            match = NAME_FIELD_PATTERN.search(persona_text)
            if match:
                candidate = match.group(1).strip()
                if self._is_valid_display_name(candidate):
                    return candidate

            contextual_match = NAME_WITH_VERB_PATTERN.search(persona_text)
            if contextual_match:
                candidate = contextual_match.group(1).strip()
                if self._is_valid_display_name(candidate):
                    return candidate

            for candidate in CAPITALIZED_NAME_PATTERN.findall(persona_text):
                normalized = candidate.strip()
                if self._is_valid_display_name(normalized):
                    return normalized

        occupation = str(persona.get("occupation") or "Resident").strip().title()
        geography = self._persona_geography_value(persona).strip().title()
        return f"{occupation} ({geography})"

    def _extract_name_candidate_from_text(self, text: str) -> str | None:
        cleaned = LEADING_NOISE_PATTERN.sub("", str(text or "").strip())
        if not cleaned:
            return None

        segments = [cleaned, *re.split(r"\n+", cleaned)]
        for segment in segments:
            normalized_segment = LEADING_NOISE_PATTERN.sub("", segment.strip())
            if not normalized_segment:
                continue
            candidate = self._consume_leading_name_tokens(normalized_segment)
            if not candidate:
                continue
            if self._is_valid_display_name(candidate):
                return candidate
        return None

    def _consume_leading_name_tokens(self, text: str) -> str | None:
        remainder = str(text or "").strip()
        tokens: list[str] = []
        while remainder and len(tokens) < 7:
            match = LEADING_NAME_TOKEN_PATTERN.match(remainder)
            if not match:
                break
            tokens.append(match.group("token"))
            remainder = remainder[match.end():].lstrip()
        candidate = " ".join(tokens).strip(" ,.;:")
        return candidate or None

    def _is_valid_display_name(self, value: str) -> bool:
        if not value:
            return False
        cleaned = re.sub(r"\s+", " ", value).strip()
        if len(cleaned) < 3 or len(cleaned) > 40:
            return False
        lowered = cleaned.lower()
        blocked_terms = {
            "singapore",
            "resident",
            "persona",
            "male",
            "female",
            "year old",
            "manager",
            "official",
            "engineer",
            "teacher",
            "student",
            "consultant",
            "professional",
            "retired",
            "service",
            "worker",
            "director",
            "executive",
            "officer",
            "and",
            "or",
        }
        words = set(re.split(r"\s+", lowered))
        if any(term in lowered for term in {"year old", "persona", "singapore"}):
            return False
        if words & blocked_terms:
            return False
        tokens = NAME_TOKEN_PATTERN.findall(cleaned)
        if not tokens or " ".join(tokens) != cleaned:
            return False
        return 2 <= len(tokens) <= 7

    def _collect_matches(
        self,
        issue_profile: dict[str, Any],
        persona: dict[str, Any],
        *,
        filters: dict[str, Any],
        parsed_sampling_instructions: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str], list[str], list[str], float, bool]:
        matched_facets: list[str] = []
        instruction_matches: list[str] = []
        penalty_matches: list[str] = []
        distribution_matches: list[str] = []
        entity_matches: list[str] = []
        facet_map = issue_profile["facets"]

        for facet_kind, canonical_values in facet_map.items():
            for persona_value in self._persona_values_for_facet(persona, facet_kind):
                if persona_value in canonical_values:
                    matched_facets.append(f"{facet_kind}:{persona_value}")

        for term in issue_profile["document_entities"]:
            if term and term in self._slug(self._persona_text(persona)).replace("_", " "):
                entity_matches.append(term)

        for bucket_name in ("soft_boosts", "hard_filters"):
            for field_name, values in parsed_sampling_instructions.get(bucket_name, {}).items():
                if self._persona_matches_instruction_field(persona, field_name, values):
                    instruction_matches.append(field_name)
        for field_name, values in parsed_sampling_instructions.get("soft_penalties", {}).items():
            if self._persona_matches_instruction_field(persona, field_name, values):
                penalty_matches.append(field_name)
        for field_name, values in parsed_sampling_instructions.get("distribution_targets", {}).items():
            if self._persona_matches_instruction_field(persona, field_name, values):
                distribution_matches.append(field_name)
        excluded = any(
            self._persona_matches_instruction_field(persona, field_name, values)
            for field_name, values in parsed_sampling_instructions.get("exclusions", {}).items()
        )

        structured_alignment = self._bounded_score(
            (len(matched_facets) * 0.20)
            + (len(entity_matches) * 0.08)
            + (len(instruction_matches) * 0.12)
        )
        return (
            sorted(set(matched_facets)),
            sorted(set(instruction_matches)),
            sorted(set(penalty_matches)),
            sorted(set(distribution_matches)),
            sorted(set(entity_matches)),
            structured_alignment,
            excluded,
        )

    def _persona_matches_instruction_field(self, persona: dict[str, Any], field_name: str, values: Any) -> bool:
        if not isinstance(values, list):
            values = [values]
        normalized_values = {self._slug(value) for value in values if value}
        if not normalized_values:
            return False

        if field_name == "age_cohort":
            cohort = self._persona_age_cohort(persona.get("age"))
            return cohort in normalized_values
        if field_name == str(persona.get("geography_field") or "") or field_name in GENERIC_GEOGRAPHY_FIELDS:
            candidate_values = {
                self._slug(self._persona_geography_value(persona, field_name or None)),
                self._slug(persona.get(field_name)),
            }
            return bool({value for value in candidate_values if value} & normalized_values)
        if field_name in {"hobby", "skill"}:
            field_map = {
                "hobby": "hobbies_and_interests_list",
                "skill": "skills_and_expertise_list",
            }
            tokens = {self._slug(value) for value in self._parse_list_field(persona.get(field_map[field_name], ""))}
            return bool(tokens & normalized_values)

        persona_value = persona.get(field_name)
        if persona_value is None:
            return False
        if field_name.endswith("_list"):
            tokens = {self._slug(value) for value in self._parse_list_field(persona_value)}
            return bool(tokens & normalized_values)
        return self._slug(persona_value) in normalized_values

    def _persona_values_for_facet(self, persona: dict[str, Any], facet_kind: str) -> set[str]:
        if facet_kind == "age_cohort":
            cohort = self._persona_age_cohort(persona.get("age"))
            return {cohort} if cohort else set()
        if facet_kind == str(persona.get("geography_field") or "") or facet_kind in GENERIC_GEOGRAPHY_FIELDS:
            return {self._slug(self._persona_geography_value(persona, facet_kind or None))}
        if facet_kind in {"hobby", "skill"}:
            field_name = "hobbies_and_interests_list" if facet_kind == "hobby" else "skills_and_expertise_list"
            return {self._slug(value) for value in self._parse_list_field(persona.get(field_name, ""))}
        field_map = {
            "planning_area": "planning_area",
            "sex": "sex",
            "education_level": "education_level",
            "marital_status": "marital_status",
            "occupation": "occupation",
            "industry": "industry",
        }
        field_name = field_map.get(facet_kind)
        if not field_name:
            return set()
        value = persona.get(field_name)
        return {self._slug(value)} if value is not None else set()

    def _bm25_scores(self, query_terms: list[str], docs: list[list[str]]) -> dict[str, Any]:
        if not docs or not query_terms:
            return {"scores": [0.0 for _ in docs], "matches": [[] for _ in docs]}

        doc_freq: Counter[str] = Counter()
        doc_lengths = [len(doc) or 1 for doc in docs]
        for doc in docs:
            for token in set(doc):
                doc_freq[token] += 1

        avg_doc_len = sum(doc_lengths) / len(doc_lengths)
        k1 = 1.5
        b = 0.75
        unique_query_terms = [self._slug(term) for term in query_terms]
        scores: list[float] = []
        matches: list[list[str]] = []
        raw_scores: list[float] = []

        for doc, doc_len in zip(docs, doc_lengths, strict=True):
            tf = Counter(doc)
            score = 0.0
            matched_terms: list[str] = []
            for term in unique_query_terms:
                if term not in tf:
                    continue
                matched_terms.append(term.replace("_", " "))
                df = doc_freq.get(term, 0)
                idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
                numerator = tf[term] * (k1 + 1)
                denominator = tf[term] + k1 * (1 - b + b * (doc_len / max(avg_doc_len, 1)))
                score += idf * (numerator / denominator)
            raw_scores.append(score)
            matches.append(matched_terms[:6])

        max_score = max(raw_scores) if raw_scores else 0.0
        for raw_score in raw_scores:
            scores.append(round(raw_score / max_score, 4) if max_score else 0.0)
        return {"scores": scores, "matches": matches}

    def _allocate_strata_quotas(
        self,
        strata: dict[tuple[str, str, str], list[dict[str, Any]]],
        *,
        total: int,
        agent_count: int,
        seed: int | None,
        use_score_bias: bool,
        distribution_targets: dict[str, Any] | None = None,
    ) -> dict[tuple[str, str, str], int]:
        rng = random.Random(seed)
        quotas: dict[tuple[str, str, str], int] = {}
        remainders: list[tuple[float, float, tuple[str, str, str]]] = []
        used = 0
        distribution_targets = distribution_targets or {}
        target_planning_areas = {
            self._slug(value)
            for field_name in ("planning_area", "state", "province", "region", "district", "county")
            for value in distribution_targets.get(field_name, [])
            if value
        }
        target_age_cohorts = {self._slug(value) for value in distribution_targets.get("age_cohort", []) if value}
        target_sexes = {self._slug(value) for value in distribution_targets.get("sex", []) if value}

        for key, rows in strata.items():
            raw_quota = agent_count * (len(rows) / max(total, 1))
            quota = min(len(rows), math.floor(raw_quota))
            quotas[key] = quota
            used += quota
            bias = max((row["score"] for row in rows), default=0.0) if use_score_bias else 0.0
            planning_area_key = self._slug(key[0])
            secondary_key = self._slug(key[1])
            tertiary_key = self._slug(key[2])
            target_bias = 0.0
            if target_planning_areas and planning_area_key in target_planning_areas:
                target_bias += 0.35
            if target_age_cohorts and tertiary_key in target_age_cohorts:
                target_bias += 0.20
            if target_sexes and secondary_key in target_sexes:
                target_bias += 0.20
            remainders.append((raw_quota - math.floor(raw_quota), bias + target_bias, key))

        if used == 0:
            if use_score_bias:
                ordered = sorted(
                    remainders,
                    key=lambda item: item[1] + (rng.random() * 0.5),
                    reverse=True,
                )
                for _, _, key in ordered[: min(agent_count, len(ordered))]:
                    quotas[key] = 1
                used = sum(quotas.values())
            else:
                ordered = list(remainders)
                rng.shuffle(ordered)
                for _, _, key in ordered[: min(agent_count, len(ordered))]:
                    quotas[key] = 1
                used = sum(quotas.values())

        while used < agent_count:
            ordered = sorted(
                remainders,
                key=lambda item: (item[0], item[1], rng.random()),
                reverse=True,
            )
            changed = False
            for _, _, key in ordered:
                if used >= agent_count:
                    break
                if quotas.get(key, 0) < len(strata[key]):
                    quotas[key] = quotas.get(key, 0) + 1
                    used += 1
                    changed = True
            if not changed:
                break

        while used > agent_count:
            ordered = sorted(
                remainders,
                key=lambda item: (item[0], item[1], rng.random()),
            )
            changed = False
            for _, _, key in ordered:
                if used <= agent_count:
                    break
                if quotas.get(key, 0) > 0:
                    quotas[key] -= 1
                    used -= 1
                    changed = True
            if not changed:
                break
        return quotas

    def _weighted_sample_without_replacement(
        self,
        rows: list[dict[str, Any]],
        quota: int,
        rng: random.Random,
    ) -> list[dict[str, Any]]:
        if quota <= 0:
            return []
        if quota >= len(rows):
            return list(rows)
        pool = list(rows)
        chosen: list[dict[str, Any]] = []
        while pool and len(chosen) < quota:
            weights = [max(0.01, row.get("score", 0.0)) for row in pool]
            total = sum(weights)
            pick = rng.random() * total
            cumulative = 0.0
            for index, weight in enumerate(weights):
                cumulative += weight
                if cumulative >= pick:
                    chosen.append(pool.pop(index))
                    break
        return chosen

    def _build_instruction_prompt(
        self,
        instructions: str,
        knowledge_artifact: dict[str, Any],
        *,
        country: str | None = None,
    ) -> str:
        summary = str(knowledge_artifact.get("summary", "")).strip()
        facets = sorted(
            {
                str(node.get("canonical_key"))
                for node in knowledge_artifact.get("entity_nodes", [])
                if node.get("canonical_key")
            }
        )
        country_name = "Selected country"
        if country:
            try:
                country_name = str(self.config.get_country(country).get("name") or country).strip() or country_name
            except Exception:
                country_name = str(country).strip().title() or country_name
        return self.config.get_system_prompt_value(
            "sampling_parser",
            "prompts",
            "parser",
            "user_template",
        ).format(
            supported_filter_keys=", ".join(self._format_filterable_columns_for_prompt(country)),
            country_name=country_name,
            document_summary=summary or "n/a",
            graph_facets=facets or ["none"],
            instructions=instructions,
        )

    def _extract_json_object(self, raw: str) -> dict[str, Any] | None:
        raw = raw.strip()
        candidates = [raw]
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
        candidates.extend(fenced)
        brace_match = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
        if brace_match:
            candidates.append(brace_match.group(1))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _normalize_parsed_instructions(
        self,
        parsed: dict[str, Any] | None,
        *,
        source: str,
        supported_fields: set[str] | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        base = dict(EMPTY_PARSED_INSTRUCTIONS)
        base["source"] = source
        if not parsed:
            return base
        allowed_fields = supported_fields or set(SUPPORTED_INSTRUCTION_FIELDS)

        normalized = dict(base)
        for key in ("hard_filters", "soft_boosts", "soft_penalties", "exclusions", "distribution_targets"):
            value = parsed.get(key, {})
            if isinstance(value, dict):
                normalized[key] = {
                    self._slug(field_name): self._normalize_instruction_values(field_name, field_value, country=country)
                    for field_name, field_value in value.items()
                    if self._slug(field_name) in allowed_fields
                    if field_value not in (None, "", [], {})
                }
        notes = parsed.get("notes_for_ui", [])
        if isinstance(notes, str):
            notes = [notes]
        normalized["notes_for_ui"] = [str(item).strip() for item in notes if str(item).strip()]
        return normalized

    def _normalize_instruction_values(self, field_name: str, values: Any, *, country: str | None = None) -> list[str]:
        if not isinstance(values, list):
            values = [values]
        geography_field = self._country_geography_field(country)
        if field_name == geography_field:
            return [self._slug(value) for value in self.countries.normalize_geography_values(country, values)]
        normalized: list[str] = []
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            if field_name in {"min_age", "max_age"}:
                age_value = self._coerce_age_value(text)
                if age_value is None:
                    continue
                normalized.append(str(age_value))
                continue
            normalized.append(self._slug(text))
        return sorted(dict.fromkeys(normalized))

    def _coerce_age_value(self, value: Any) -> int | None:
        text = str(value).strip()
        match = re.search(r"\d{1,3}", text)
        if not match:
            return None
        age = int(match.group(0))
        return max(0, min(120, age))

    def _augment_with_deterministic_constraints(
        self,
        instructions: str,
        parsed: dict[str, Any],
        *,
        supported_fields: set[str] | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_parsed_instructions(
            parsed,
            source=str(parsed.get("source", "runtime")),
            supported_fields=supported_fields,
            country=country,
        )
        hard_filters = dict(normalized.get("hard_filters") or {})
        notes = list(normalized.get("notes_for_ui") or [])

        extracted = self._extract_age_constraints(instructions)
        if extracted.get("min_age") is not None:
            hard_filters["min_age"] = [str(extracted["min_age"])]
            notes.append(f"Hard age floor applied: age >= {extracted['min_age']}.")
        if extracted.get("max_age") is not None:
            hard_filters["max_age"] = [str(extracted["max_age"])]
            notes.append(f"Hard age ceiling applied: age <= {extracted['max_age']}.")

        if notes:
            notes = list(dict.fromkeys(note for note in notes if note))
            normalized["notes_for_ui"] = notes
        normalized["hard_filters"] = hard_filters
        return normalized

    def _supported_instruction_fields(self, country: str | None) -> set[str]:
        configured = {
            self._slug(item.get("field"))
            for item in self._country_filterable_columns(country)
            if self._slug(item.get("field"))
        }
        return configured or set(SUPPORTED_INSTRUCTION_FIELDS)

    def _country_filterable_columns(self, country: str | None) -> list[dict[str, Any]]:
        if not country:
            return []
        try:
            return self.config.get_country_filterable_columns(country)
        except Exception:
            return []

    def _format_filterable_columns_for_prompt(self, country: str | None) -> list[str]:
        columns = self._country_filterable_columns(country)
        if not columns:
            return sorted(SUPPORTED_INSTRUCTION_FIELDS)
        rendered: list[str] = []
        for item in columns:
            field = self._slug(item.get("field"))
            description = str(item.get("description") or "").strip()
            if not field:
                continue
            rendered.append(f"{field} ({description})" if description else field)
        return rendered or sorted(self._supported_instruction_fields(country))

    def _extract_age_constraints(self, instructions: str) -> dict[str, int | None]:
        lower = instructions.lower()
        min_age: int | None = None
        max_age: int | None = None

        range_match = re.search(r"\b(?:age(?:d)?\s*)?(\d{1,3})\s*(?:-|to)\s*(\d{1,3})\b", lower)
        if range_match:
            a = int(range_match.group(1))
            b = int(range_match.group(2))
            min_age = max(0, min(120, min(a, b)))
            max_age = max(0, min(120, max(a, b)))

        hard_max_patterns: list[tuple[str, bool]] = [
            (r"\bno\s+one\s+over(?:\s+the\s+age\s+of)?\s*(\d{1,3})\b", False),
            (r"\bno\s+one\s+above\s*(\d{1,3})\b", False),
            (r"\bunder\s*(\d{1,3})\b", True),
            (r"\bbelow\s*(\d{1,3})\b", True),
            (r"\bat\s+most\s*(\d{1,3})\b", False),
            (r"\bmax(?:imum)?(?:\s+age)?(?:\s+of)?\s*(\d{1,3})\b", False),
        ]
        for pattern, strict_less_than in hard_max_patterns:
            match = re.search(pattern, lower)
            if not match:
                continue
            value = int(match.group(1))
            candidate = value - 1 if strict_less_than else value
            candidate = max(0, min(120, candidate))
            max_age = candidate if max_age is None else min(max_age, candidate)

        hard_min_patterns = [
            r"\bno\s+one\s+under\s*(\d{1,3})\b",
            r"\bat\s+least\s*(\d{1,3})\b",
            r"\bminimum(?:\s+age)?(?:\s+of)?\s*(\d{1,3})\b",
        ]
        for pattern in hard_min_patterns:
            match = re.search(pattern, lower)
            if not match:
                continue
            candidate = max(0, min(120, int(match.group(1))))
            min_age = candidate if min_age is None else max(min_age, candidate)

        if min_age is not None and max_age is not None and min_age > max_age:
            return {"min_age": None, "max_age": None}

        return {"min_age": min_age, "max_age": max_age}

    def _has_actionable_instruction_signal(self, parsed: dict[str, Any]) -> bool:
        for key in ("hard_filters", "soft_boosts", "soft_penalties", "exclusions", "distribution_targets"):
            bucket = parsed.get(key, {})
            if isinstance(bucket, dict) and any(values for values in bucket.values()):
                return True
        return False

    def _country_geography_aliases(self, country: str | None) -> list[tuple[str, list[str]]]:
        aliases: list[tuple[str, list[str]]] = []
        field_name = self._country_geography_field(country)
        for row in self.countries.geography_values(country):
            raw_aliases = [row.get("code"), row.get("label"), *((row.get("aliases") or []))]
            aliases.append(
                (
                    field_name,
                    [str(alias).strip() for alias in raw_aliases if str(alias or "").strip()],
                )
            )
        for row in self.countries.geography_groups(country):
            raw_aliases = [row.get("code"), row.get("label"), *((row.get("aliases") or []))]
            aliases.append(
                (
                    field_name,
                    [str(alias).strip() for alias in raw_aliases if str(alias or "").strip()],
                )
            )
        return aliases

    def _fallback_parse_sampling_instructions(self, instructions: str, *, country: str | None = None) -> dict[str, Any]:
        lower = instructions.lower()
        parsed = dict(EMPTY_PARSED_INSTRUCTIONS)
        parsed["source"] = "fallback"
        soft_boosts: dict[str, list[str]] = defaultdict(list)
        hard_filters: dict[str, list[str]] = defaultdict(list)
        notes: list[str] = []
        geography_field = self._country_geography_field(country)

        restrictive = any(marker in lower for marker in ("only ", "must include", "strictly", "limit to"))
        target = hard_filters if restrictive else soft_boosts

        for _field_name, aliases in self._country_geography_aliases(country):
            for alias in aliases:
                candidate = str(alias).strip().lower()
                if candidate and candidate in lower:
                    target[geography_field].extend(
                        self._slug(value)
                        for value in self.countries.normalize_geography_values(country, [alias])
                    )
                    if geography_field == "planning_area":
                        notes.append(f"Regional {self.countries.geography_label(country).lower()} bias detected: {candidate}.")
        for label, canonical in OCCUPATION_SLUGS.items():
            if label.replace("_", " ") in lower:
                target["occupation"].append(self._slug(canonical))
        if any(alias in lower for alias in EDUCATION_WORKER_ALIASES):
            target["industry"].append("public_administration_education_services")
            notes.append("Education-worker language detected; biasing toward education-service personas.")
        for label, canonical in INDUSTRY_SLUGS.items():
            if label.replace("_", " ") in lower:
                target["industry"].append(self._slug(canonical))
        for alias, canonical in EDUCATION_LEVEL_ALIASES.items():
            if alias in lower:
                target["education_level"].append(self._slug(canonical))
        for alias, canonical in MARITAL_STATUS_ALIASES.items():
            if alias in lower:
                target["marital_status"].append(self._slug(canonical))
        for alias, canonical in SEX_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                target["sex"].append(self._slug(canonical))
        if any(term in lower for term in ("young", "younger", "student", "youth")):
            soft_boosts["age_cohort"].append("youth")
        if any(term in lower for term in ("elderly", "senior", "older adults", "retiree")):
            soft_boosts["age_cohort"].append("senior")
        if "parent" in lower or "parents" in lower:
            notes.append("Instruction references parents; this is tracked as a soft narrative preference rather than a direct categorical filter.")

        parsed["hard_filters"] = {key: sorted(dict.fromkeys(values)) for key, values in hard_filters.items()}
        parsed["soft_boosts"] = {key: sorted(dict.fromkeys(values)) for key, values in soft_boosts.items()}
        parsed["notes_for_ui"] = notes or [instructions]
        return parsed

    def _build_semantic_summary(
        self,
        *,
        matched_facets: list[str],
        entity_matches: list[str],
        instruction_matches: list[str],
    ) -> str:
        parts: list[str] = []
        if matched_facets:
            parts.append(f"Matched facets: {', '.join(matched_facets[:3])}.")
        if entity_matches:
            parts.append(f"Matched document entities: {', '.join(entity_matches[:3])}.")
        if instruction_matches:
            parts.append(f"Aligned with instructions via {', '.join(instruction_matches[:3])}.")
        if not parts:
            return "Selected from the shortlist based on overall narrative and demographic overlap."
        return " ".join(parts)

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _bounded_score(self, value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def _persona_text(self, persona: dict[str, Any]) -> str:
        parts: list[str] = []
        for key, value in persona.items():
            if value is None:
                continue
            if key in {"hobbies_and_interests_list", "skills_and_expertise_list"}:
                parts.extend(self._parse_list_field(value))
            else:
                parts.append(str(value))
        return " ".join(parts)

    def _tokens(self, text: str) -> set[str]:
        return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}

    def _node_facet(self, node: dict[str, Any]) -> tuple[str | None, str | None]:
        canonical_key = str(node.get("canonical_key", "")).strip()
        if ":" in canonical_key:
            kind, value = canonical_key.split(":", 1)
            return kind, value

        label = str(node.get("label", "")).strip()
        normalized = self._slug(label).replace("_", " ")
        combined = " ".join(part for part in [label.lower(), str(node.get("description", "")).lower()] if part)

        for country_cfg in self.config.list_countries():
            geography_field = self.countries.geography_field(country_cfg)
            geography_catalog = {
                self._slug(row.get("label") or row.get("code")).replace("_", " "): self._slug(row.get("label") or row.get("code"))
                for row in self.countries.geography_values(country_cfg)
            }
            if geography_match := self._match_from_catalog(normalized, geography_catalog):
                return geography_field, geography_match
        if age_cohort := AGE_COHORT_ALIASES.get(normalized) or self._phrase_match(combined, AGE_COHORT_ALIASES):
            return "age_cohort", self._slug(age_cohort)
        if sex := SEX_ALIASES.get(normalized):
            return "sex", self._slug(sex)
        if education := EDUCATION_LEVEL_ALIASES.get(normalized):
            return "education_level", self._slug(education)
        if marital_status := MARITAL_STATUS_ALIASES.get(normalized):
            return "marital_status", self._slug(marital_status)
        if occupation := self._match_from_catalog(normalized, OCCUPATION_SLUGS):
            return "occupation", occupation
        if industry := self._match_from_catalog(normalized, INDUSTRY_SLUGS):
            return "industry", industry
        if hobby := self._match_from_catalog(normalized, HOBBY_SLUGS):
            return "hobby", hobby
        if skill := self._match_from_catalog(normalized, SKILL_SLUGS):
            return "skill", skill
        return None, None

    def _match_from_catalog(self, normalized_label: str, catalog: dict[str, str]) -> str | None:
        slug = normalized_label.replace(" ", "_")
        canonical = catalog.get(slug)
        return self._slug(canonical) if canonical else None

    def _phrase_match(self, text: str, aliases: dict[str, str]) -> str | None:
        for phrase, canonical in aliases.items():
            if phrase in text:
                return canonical
        return None

    def _parse_list_field(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if not isinstance(value, str):
            return [str(value)]
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [part.strip() for part in value.split(",") if part.strip()]

    def _persona_age_cohort(self, age: Any) -> str | None:
        if not isinstance(age, (int, float)):
            return None
        age_value = int(age)
        if age_value <= 14:
            return "child"
        if age_value <= 24:
            return "youth"
        if age_value >= 60:
            return "senior"
        return "adult"

    def _slug(self, value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")

    def _age_bucket(self, age: Any) -> str:
        if not isinstance(age, (int, float)):
            return "unknown"
        age_int = int(age)
        start = (age_int // 10) * 10
        return f"{start}-{start + 9}"
