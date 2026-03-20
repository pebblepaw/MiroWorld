from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from mckainsey.config import Settings


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


@dataclass
class PersonaRelevanceService:
    settings: Settings

    def score_personas(
        self,
        personas: list[dict[str, Any]],
        *,
        knowledge_artifact: dict[str, Any],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issue_profile = self._build_issue_profile(knowledge_artifact)
        scored: list[dict[str, Any]] = []
        for persona in personas:
            component_scores = {
                "semantic_relevance": self._semantic_relevance(issue_profile, persona),
                "geographic_relevance": self._geographic_relevance(issue_profile, persona),
                "socioeconomic_relevance": self._socioeconomic_relevance(issue_profile, persona),
                "digital_behavior_relevance": self._digital_behavior_relevance(issue_profile, persona),
                "filter_alignment": self._filter_alignment(filters, persona),
            }
            active_weights = {
                "semantic_relevance": 0.40,
                "geographic_relevance": 0.20,
                "socioeconomic_relevance": 0.20,
                "digital_behavior_relevance": 0.10,
                "filter_alignment": 0.10,
            }
            active = {
                key: weight
                for key, weight in active_weights.items()
                if component_scores[key] is not None
            }
            total_weight = sum(active.values()) or 1.0
            score = sum(component_scores[key] * (weight / total_weight) for key, weight in active.items())
            scored.append(
                {
                    "persona": persona,
                    "score": round(score, 4),
                    "component_scores": component_scores,
                }
            )
        return sorted(scored, key=lambda row: row["score"], reverse=True)

    def sample_balanced(self, scored_personas: list[dict[str, Any]], *, agent_count: int) -> list[dict[str, Any]]:
        if len(scored_personas) <= agent_count:
            return scored_personas

        strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in scored_personas:
            persona = row["persona"]
            key = (
                str(persona.get("planning_area", "Unknown")),
                str(persona.get("income_bracket", "Unknown")),
                self._age_bucket(persona.get("age")),
            )
            strata[key].append(row)

        total = len(scored_personas)
        allocations: dict[tuple[str, str, str], int] = {}
        remainders: list[tuple[float, float, tuple[str, str, str]]] = []
        used = 0
        for key, rows in strata.items():
            raw_quota = agent_count * (len(rows) / total)
            quota = min(len(rows), math.floor(raw_quota))
            allocations[key] = quota
            used += quota
            remainders.append((raw_quota - math.floor(raw_quota), rows[0]["score"], key))

        while used > agent_count:
            changed = False
            for _, _, key in sorted(remainders):
                if used <= agent_count:
                    break
                if allocations[key] > 1:
                    allocations[key] -= 1
                    used -= 1
                    changed = True
            if not changed:
                for _, _, key in sorted(remainders):
                    if used <= agent_count:
                        break
                    if allocations[key] > 0:
                        allocations[key] -= 1
                        used -= 1

        while used < agent_count:
            changed = False
            for _, _, key in sorted(remainders, reverse=True):
                if used >= agent_count:
                    break
                if allocations[key] < len(strata[key]):
                    allocations[key] += 1
                    used += 1
                    changed = True
            if not changed:
                break

        sampled: list[dict[str, Any]] = []
        for key, rows in strata.items():
            quota = allocations[key]
            sampled.extend(rows[:quota])
        return sorted(sampled, key=lambda row: row["score"], reverse=True)[:agent_count]

    def build_population_artifact(
        self,
        session_id: str,
        *,
        personas: list[dict[str, Any]],
        knowledge_artifact: dict[str, Any],
        filters: dict[str, Any],
        agent_count: int,
    ) -> dict[str, Any]:
        scored = self.score_personas(personas, knowledge_artifact=knowledge_artifact, filters=filters)
        sampled = self.sample_balanced(scored, agent_count=agent_count)
        sampled_personas: list[dict[str, Any]] = []
        for index, row in enumerate(sampled):
            sampled_personas.append(
                {
                    "agent_id": f"agent-{index + 1:04d}",
                    "persona": row["persona"],
                    "selection_reason": {
                        "score": row["score"],
                        **row["component_scores"],
                    },
                }
            )

        area_counts = Counter(str(row["persona"].get("planning_area", "Unknown")) for row in sampled)
        bucket_counts = Counter(self._age_bucket(row["persona"].get("age")) for row in sampled)

        return {
            "session_id": session_id,
            "candidate_count": len(personas),
            "sample_count": len(sampled_personas),
            "coverage": {
                "planning_areas": sorted(area_counts.keys()),
                "age_buckets": dict(bucket_counts),
            },
            "sampled_personas": sampled_personas,
            "agent_graph": self._build_agent_graph(sampled_personas),
            "representativeness": {
                "status": "balanced" if len(area_counts) > 1 else "narrow",
                "planning_area_distribution": dict(area_counts),
            },
        }

    def _build_issue_profile(self, artifact: dict[str, Any]) -> str:
        labels = " ".join(str(node.get("label", "")) for node in artifact.get("entity_nodes", []))
        return " ".join(
            part
            for part in [
                str(artifact.get("summary", "")),
                labels,
                str(artifact.get("demographic_focus_summary", "")),
            ]
            if part
        )

    def _persona_text(self, persona: dict[str, Any]) -> str:
        return " ".join(str(value) for value in persona.values() if value is not None)

    def _semantic_relevance(self, issue_profile: str, persona: dict[str, Any]) -> float:
        issue_tokens = self._tokens(issue_profile)
        persona_tokens = self._tokens(self._persona_text(persona))
        if not issue_tokens or not persona_tokens:
            return 0.0
        intersection = len(issue_tokens & persona_tokens)
        union = len(issue_tokens | persona_tokens)
        return round(intersection / union, 4) if union else 0.0

    def _geographic_relevance(self, issue_profile: str, persona: dict[str, Any]) -> float:
        area = str(persona.get("planning_area", "")).strip().lower()
        if not area:
            return 0.0
        return 1.0 if area and area in issue_profile.lower() else 0.2

    def _socioeconomic_relevance(self, issue_profile: str, persona: dict[str, Any]) -> float:
        score = 0.2
        age = persona.get("age")
        if isinstance(age, (int, float)) and age >= 60 and "senior" in issue_profile.lower():
            score += 0.4
        income = str(persona.get("income_bracket", "")).lower()
        if "transport" in issue_profile.lower() and ("$3,000" in income or "$2,000" in income):
            score += 0.2
        occupation = str(persona.get("occupation", "")).lower()
        if occupation and occupation in issue_profile.lower():
            score += 0.2
        return min(1.0, round(score, 4))

    def _digital_behavior_relevance(self, issue_profile: str, persona: dict[str, Any]) -> float:
        text = self._persona_text(persona).lower()
        if "online" in issue_profile.lower() or "digital" in issue_profile.lower():
            if "high" in text or "social" in text or "digital" in text:
                return 0.9
        return 0.4

    def _filter_alignment(self, filters: dict[str, Any], persona: dict[str, Any]) -> float:
        score = 1.0
        planning_areas = filters.get("planning_areas") or []
        if planning_areas and persona.get("planning_area") not in planning_areas:
            score -= 0.5
        income_brackets = filters.get("income_brackets") or []
        if income_brackets and persona.get("income_bracket") not in income_brackets:
            score -= 0.3
        min_age = filters.get("min_age")
        max_age = filters.get("max_age")
        age = persona.get("age")
        if min_age is not None and isinstance(age, (int, float)) and age < min_age:
            score -= 0.2
        if max_age is not None and isinstance(age, (int, float)) and age > max_age:
            score -= 0.2
        return max(0.0, round(score, 4))

    def _build_agent_graph(self, sampled_personas: list[dict[str, Any]]) -> dict[str, Any]:
        nodes = []
        links = []
        for row in sampled_personas:
            persona = row["persona"]
            agent_id = row["agent_id"]
            nodes.append(
                {
                    "id": agent_id,
                    "label": agent_id,
                    "planning_area": str(persona.get("planning_area", "Unknown")),
                    "score": row["selection_reason"]["score"],
                }
            )
        for i, left in enumerate(sampled_personas):
            for right in sampled_personas[i + 1 :]:
                if left["persona"].get("planning_area") == right["persona"].get("planning_area"):
                    links.append(
                        {
                            "source": left["agent_id"],
                            "target": right["agent_id"],
                            "weight": 1.0,
                            "reason": "shared_planning_area",
                        }
                    )
        return {"nodes": nodes, "links": links}

    def _tokens(self, text: str) -> set[str]:
        return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}

    def _age_bucket(self, age: Any) -> str:
        if not isinstance(age, (int, float)):
            return "unknown"
        age_int = int(age)
        start = (age_int // 10) * 10
        return f"{start}-{start + 9}"
