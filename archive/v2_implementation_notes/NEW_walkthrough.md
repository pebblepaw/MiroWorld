# McKAInsey V2 Platform Redesign — Final Walkthrough

## Overview

Complete architectural transition from V1 to V2, pivoting from 4 rigid use cases to 3 flexible, configuration-driven use cases centered on a unified `analysis_questions` schema.

**All 7 phases are complete.**

---

## 1. Config Consolidation (4 → 3 Use Cases)

**Deleted:** `policy-review.yaml`, `ad-testing.yaml`, `customer-review.yaml`, `product-market-fit.yaml`

**Created:**

| File | Use Case ID | Display Name |
|------|------------|--------------|
| [public-policy-testing.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/public-policy-testing.yaml) | `public-policy-testing` | 🏛️ Public Policy Testing |
| [product-market-research.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/product-market-research.yaml) | `product-market-research` | 📦 Product & Market Research |
| [campaign-content-testing.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/campaign-content-testing.yaml) | `campaign-content-testing` | 📢 Campaign & Content Testing |

Each YAML now includes:
- `analysis_questions` — unified schema driving checkpoints + report
- `insight_blocks` — per-use-case modular analytics
- `preset_sections` — LLM-synthesized narrative report sections

---

## 2. Backend Changes

### ConfigService
```diff:config_service.py
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
===
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from mckainsey.config import BACKEND_DIR, Settings


logger = logging.getLogger(__name__)
REPO_ROOT = BACKEND_DIR.parent


USE_CASE_ALIASES: dict[str, str] = {
    # V2 canonical names
    "public-policy-testing": "public-policy-testing",
    "product-market-research": "product-market-research",
    "campaign-content-testing": "campaign-content-testing",
    # V1 backward-compatibility aliases → map to nearest V2 use case
    "reviews": "product-market-research",
    "customer-review": "product-market-research",
    "policy-review": "public-policy-testing",
    "ad-testing": "campaign-content-testing",
    "pmf-discovery": "product-market-research",
    "product-market-fit": "product-market-research",
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

    # ── Country methods ──

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

    # ── Use-case methods ──

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

    def list_use_cases(self) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for path in sorted(self.prompts_dir.glob("*.yaml")):
            payload = self._safe_load_yaml(path)
            if payload is None:
                continue
            cases.append({
                "name": payload.get("name", path.stem),
                "code": payload.get("code", path.stem),
                "description": payload.get("description", ""),
                "icon": payload.get("icon", ""),
            })
        return cases

    def get_system_prompt(self, use_case_id: str) -> str:
        payload = self.get_use_case(use_case_id)
        return str(payload.get("system_prompt") or payload.get("guiding_prompt") or "").strip()

    def get_analysis_questions(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        questions = payload.get("analysis_questions", [])
        if not questions:
            # Backward compat: fall back to checkpoint_questions
            questions = payload.get("checkpoint_questions", [])
        return [item for item in questions if isinstance(item, dict)]

    def get_insight_blocks(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        blocks = payload.get("insight_blocks", [])
        return [item for item in blocks if isinstance(item, dict)]

    def get_preset_sections(self, use_case_id: str) -> list[dict[str, Any]]:
        payload = self.get_use_case(use_case_id)
        sections = payload.get("preset_sections", [])
        return [item for item in sections if isinstance(item, dict)]

    def get_agent_personality_modifiers(self, use_case_id: str) -> list[str]:
        payload = self.get_use_case(use_case_id)
        modifiers = payload.get("agent_personality_modifiers", [])
        return [item for item in modifiers if isinstance(item, str)]

    # Backward-compat wrappers
    def get_checkpoint_questions(self, use_case_id: str) -> list[dict[str, Any]]:
        """Backward-compat alias for get_analysis_questions."""
        return self.get_analysis_questions(use_case_id)

    def get_report_sections(self, use_case_id: str) -> list[dict[str, Any]]:
        """Backward-compat: builds report sections from analysis_questions + preset_sections."""
        payload = self.get_use_case(use_case_id)
        # Try new-style report_sections first
        sections = payload.get("report_sections", [])
        if sections:
            return [item for item in sections if isinstance(item, dict)]
        # Otherwise build from analysis_questions + preset_sections
        questions = self.get_analysis_questions(use_case_id)
        presets = self.get_preset_sections(use_case_id)
        result: list[dict[str, Any]] = []
        for q in questions:
            result.append({
                "title": q.get("report_title", q.get("question", "")),
                "prompt": q.get("question", ""),
            })
        for p in presets:
            result.append(p)
        return result

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
```

- `USE_CASE_MAP` with V1→V2 backward-compatible aliases
- New methods: `get_analysis_questions()`, `get_system_prompt()`, `get_insight_blocks()`, `get_preset_sections()`

### MetricsService
```diff:metrics_service.py
from __future__ import annotations

from collections import defaultdict
from statistics import mean as _mean
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:  # noqa: BLE001
        return int(default)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _summarize_text(value: Any, limit: int = 160) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean_text(row.get(key))
        if value:
            return value
    return ""


def _stance_from_score(score: float) -> str:
    if score >= 7:
        return "supporter"
    if score >= 5:
        return "neutral"
    return "dissenter"


def _stance_from_text(text: str) -> str:
    lowered = text.lower()
    support_hits = sum(1 for token in ("support", "agree", "upside", "benefit", "positive", "yes", "pro") if token in lowered)
    dissent_hits = sum(1 for token in ("risk", "concern", "oppose", "against", "problem", "negative", "no", "worry") if token in lowered)
    if support_hits > dissent_hits:
        return "supporter"
    if dissent_hits > support_hits:
        return "dissenter"
    return "neutral"


def _row_stance(row: dict[str, Any], agent: dict[str, Any] | None = None) -> str:
    stance = _clean_text(row.get("stance") or row.get("segment"))
    if stance:
        return stance
    if agent:
        agent_stance = _stance_from_score(_as_float(agent.get("opinion_post", agent.get("opinion_pre", 5.0))))
        if agent_stance:
            return agent_stance
    delta = _as_float(row.get("delta", 0.0))
    if delta > 0:
        return "supporter"
    if delta < 0:
        return "dissenter"
    text = _first_text(row, ("content", "body", "title", "summary"))
    return _stance_from_text(text) if text else "neutral"


def _agent_name(agent: dict[str, Any] | None, fallback: str) -> str:
    if not agent:
        return fallback
    for key in ("name", "agent_name", "display_name", "label"):
        value = _clean_text(agent.get(key))
        if value:
            return value
    persona = agent.get("persona")
    if isinstance(persona, dict):
        for key in ("name", "agent_name", "display_name", "label"):
            value = _clean_text(persona.get(key))
            if value:
                return value
    return fallback


def _actor_id(row: dict[str, Any]) -> str:
    return _clean_text(row.get("actor_agent_id") or row.get("author_agent_id") or row.get("agent_id") or row.get("author") or row.get("name"))


def _row_id(row: dict[str, Any]) -> str:
    return _clean_text(row.get("id") or row.get("post_id") or row.get("comment_id") or row.get("interaction_id"))


def _post_text(row: dict[str, Any]) -> str:
    return _first_text(row, ("title", "content", "body", "summary"))


def _is_discourse_interaction(row: dict[str, Any]) -> bool:
    action_type = _clean_text(row.get("action_type") or row.get("type")).lower()
    if action_type == "trace":
        return False
    content = _clean_text(row.get("content") or row.get("body") or row.get("title"))
    if not content:
        return False
    if content.startswith(("sign_up:", "refresh:", "search_posts:", "search_user:", "like_comment:", "like_post:")):
        return False
    return True


def _engagement_score(row: dict[str, Any]) -> float:
    likes = _as_int(row.get("likes", row.get("upvotes", 0)))
    dislikes = _as_int(row.get("dislikes", row.get("downvotes", 0)))
    delta = abs(_as_float(row.get("delta", 0.0)))
    return float(likes + dislikes) + delta


def _numeric_engagement(row: dict[str, Any]) -> tuple[int, int]:
    likes = _as_int(row.get("likes", row.get("upvotes", 0)))
    dislikes = _as_int(row.get("dislikes", row.get("downvotes", 0)))
    return likes, dislikes


def compute_group_polarization(agents: list[dict[str, Any]], group_key: str = "planning_area") -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []
    for agent in agents:
        key = str(agent.get("persona", {}).get(group_key, "Unknown"))
        score = _as_float(agent.get("opinion_post", 0.0))
        groups[key].append(score)
        all_scores.append(score)

    if not all_scores:
        return {
            "polarization_index": 0.0,
            "severity": "low",
            "by_group_means": {},
            "group_sizes": {},
        }

    overall_mean = _mean(all_scores)
    n = max(1, len(all_scores))
    between = sum(len(values) * ((_mean(values) - overall_mean) ** 2) for values in groups.values()) / n
    total_var = sum((score - overall_mean) ** 2 for score in all_scores) / n
    polarization_index = (between / total_var) if total_var > 0 else 0.0
    severity = (
        "low" if polarization_index < 0.2 else
        "moderate" if polarization_index < 0.5 else
        "high" if polarization_index < 0.8 else
        "critical"
    )

    return {
        "polarization_index": round(polarization_index, 4),
        "severity": severity,
        "by_group_means": {key: round(_mean(values), 4) for key, values in groups.items()},
        "group_sizes": {key: len(values) for key, values in groups.items()},
    }


def compute_opinion_flow(agents: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket(score: float) -> str:
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    initial = {"supporter": 0, "neutral": 0, "dissenter": 0}
    final = {"supporter": 0, "neutral": 0, "dissenter": 0}
    flows: dict[tuple[str, str], int] = defaultdict(int)

    for agent in agents:
        pre = bucket(_as_float(agent.get("opinion_pre", 5)))
        post = bucket(_as_float(agent.get("opinion_post", 5)))
        initial[pre] += 1
        final[post] += 1
        flows[(pre, post)] += 1

    return {
        "initial": initial,
        "final": final,
        "flows": [{"from": source, "to": target, "count": count} for (source, target), count in flows.items()],
    }


def build_influence_graph(interactions: list[dict[str, Any]], agents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in (agents or [])
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }
    edges: dict[tuple[str, str], float] = {}
    actor_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    node_scores: dict[str, float] = defaultdict(float)
    for event in interactions:
        actor = _actor_id(event)
        target = _clean_text(event.get("target_agent_id") or event.get("target") or event.get("reply_to_agent_id"))
        if not actor:
            continue
        if not _is_discourse_interaction(event):
            continue
        actor_rows[actor].append(event)
        engagement_score = _engagement_score(event)
        node_scores[actor] += abs(_as_float(event.get("delta", 0.0))) + (engagement_score * 0.1) + (0.25 if _clean_text(event.get("action_type")).lower() == "comment" else 0.5)
        if not target:
            continue
        weight = abs(_as_float(event.get("delta", 0.0)))
        edges[(str(actor), str(target))] = edges.get((str(actor), str(target)), 0.0) + weight

    top_influencers = sorted(node_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    top_ids = {agent_id for agent_id, _score in top_influencers}
    enriched_influencers: list[dict[str, Any]] = []
    for agent_id, score in top_influencers:
        rows = actor_rows.get(agent_id, [])
        agent = agent_lookup.get(agent_id)
        if rows:
            rows_sorted = sorted(rows, key=lambda row: (_engagement_score(row), abs(_as_float(row.get("delta", 0.0)))), reverse=True)
            top_row = rows_sorted[0]
        else:
            top_row = {}
        top_content = _post_text(top_row)
        viewpoint = _summarize_text(top_content or top_row.get("content") or top_row.get("body") or top_row.get("title"), 160)
        stance = _row_stance(top_row, agent)
        name = _agent_name(agent, agent_id)
        enriched_influencers.append(
            {
                "agent_id": agent_id,
                "name": name,
                "agent_name": name,
                "stance": stance,
                "segment": stance,
                "influence": round(score, 4),
                "influence_score": round(score, 4),
                "score": round(score, 4),
                "top_view": viewpoint,
                "core_viewpoint": viewpoint,
                "top_post": {
                    "post_id": _row_id(top_row) or None,
                    "title": _clean_text(top_row.get("title")) or None,
                    "content": _clean_text(top_row.get("content") or top_row.get("body")) or None,
                    "body": _clean_text(top_row.get("body") or top_row.get("content")) or None,
                    "likes": _numeric_engagement(top_row)[0],
                    "dislikes": _numeric_engagement(top_row)[1],
                    "stance": stance,
                },
            }
        )

    return {
        "top_influencers": enriched_influencers,
        "leaders": [dict(item) for item in enriched_influencers],
        "items": [dict(item) for item in enriched_influencers],
        "nodes": [
            {
                "id": item["agent_id"],
                "name": item["name"],
                "agent_name": item["agent_name"],
                "stance": item["stance"],
                "influence_score": item["influence_score"],
                "top_view": item["top_view"],
                "top_post": item["top_post"],
            }
            for item in enriched_influencers
        ],
        "edges": [
            {"source": actor, "target": target, "weight": round(weight, 4)}
            for (actor, target), weight in edges.items()
            if actor in top_ids or target in top_ids
        ],
        "total_nodes": len(node_scores),
        "total_edges": len(edges),
    }


def compute_top_cascade(posts: list[dict[str, Any]], comments: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any]:
    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in agents
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }
    posts_by_id: dict[str, dict[str, Any]] = {}
    posts_by_actor_round: dict[tuple[str, int], str] = {}
    posts_by_actor: dict[str, list[str]] = defaultdict(list)
    for post in posts:
        post_id = _row_id(post)
        if not post_id:
            continue
        posts_by_id[post_id] = post
        actor_id = _actor_id(post)
        round_no = _as_int(post.get("round_no", 0))
        if actor_id:
            posts_by_actor_round[(actor_id, round_no)] = post_id
            posts_by_actor[actor_id].append(post_id)

    comments_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for comment in comments:
        parent = _clean_text(
            comment.get("parent_post_id")
            or comment.get("parent_id")
            or comment.get("root_post_id")
            or comment.get("reply_to_post_id")
            or comment.get("post_id")
        )
        if not parent:
            actor_id = _actor_id(comment)
            round_no = _as_int(comment.get("round_no", 0))
            target_agent = _clean_text(comment.get("target_agent_id"))
            if actor_id and (actor_id, round_no) in posts_by_actor_round:
                parent = posts_by_actor_round[(actor_id, round_no)]
            elif target_agent and posts_by_actor.get(target_agent):
                parent = posts_by_actor[target_agent][-1]
            elif posts:
                parent = _row_id(posts[-1])
        if parent:
            comments_by_parent[parent].append(comment)

    def build_comment_node(comment: dict[str, Any]) -> dict[str, Any]:
        actor_id = _actor_id(comment)
        agent = agent_lookup.get(actor_id)
        children = [build_comment_node(child) for child in comments_by_parent.get(_row_id(comment), []) if _row_id(child) != _row_id(comment)]
        likes, dislikes = _numeric_engagement(comment)
        stance = _row_stance(comment, agent)
        node = {
            "comment_id": _row_id(comment) or None,
            "author": actor_id or None,
            "author_name": _agent_name(agent, actor_id or "unknown"),
            "stance": stance,
            "content": _clean_text(comment.get("content") or comment.get("body")) or None,
            "body": _clean_text(comment.get("body") or comment.get("content")) or None,
            "likes": likes,
            "upvotes": likes,
            "dislikes": dislikes,
            "downvotes": dislikes,
        }
        if children:
            node["comments"] = children
        return node

    viral_posts: list[dict[str, Any]] = []
    for post in posts:
        post_id = _row_id(post)
        if not post_id:
            continue
        actor_id = _actor_id(post)
        agent = agent_lookup.get(actor_id)
        thread_comments = [build_comment_node(comment) for comment in comments_by_parent.get(post_id, [])]
        comment_count = len(thread_comments)
        comment_likes = sum(int(comment.get("likes", 0) or 0) for comment in thread_comments)
        comment_dislikes = sum(int(comment.get("dislikes", 0) or 0) for comment in thread_comments)
        post_likes, post_dislikes = _numeric_engagement(post)
        raw_likes = post_likes + comment_likes + max(0, int(round(_as_float(post.get("delta", 0.0)) * 2)))
        raw_dislikes = post_dislikes + comment_dislikes + max(0, int(round(abs(min(0.0, _as_float(post.get("delta", 0.0)))) * 2)))
        discussion_deltas: list[float] = []
        engaged_agents = {actor_id} if actor_id else set()
        for comment in comments_by_parent.get(post_id, []):
            comment_actor = _actor_id(comment)
            if comment_actor:
                engaged_agents.add(comment_actor)
            if comment_actor and (agent := agent_lookup.get(comment_actor)):
                discussion_deltas.append(_as_float(agent.get("opinion_post", 0.0)) - _as_float(agent.get("opinion_pre", 0.0)))
        if actor_id and (agent := agent_lookup.get(actor_id)):
            discussion_deltas.append(_as_float(agent.get("opinion_post", 0.0)) - _as_float(agent.get("opinion_pre", 0.0)))
        mean_delta = _mean(discussion_deltas) if discussion_deltas else 0.0
        content = _post_text(post)
        title = _clean_text(post.get("title")) or _summarize_text(content, 80) or f"Post {post_id}"
        stance = _row_stance(post, agent)
        engagement_score = _engagement_score(post) + comment_count + sum(abs(delta) for delta in discussion_deltas)
        viral_posts.append(
            {
                "post_id": post_id,
                "author": actor_id or None,
                "author_name": _agent_name(agent, actor_id or "unknown"),
                "stance": stance,
                "segment": stance,
                "title": title,
                "content": content or None,
                "body": _clean_text(post.get("body") or content) or None,
                "likes": raw_likes,
                "upvotes": raw_likes,
                "dislikes": raw_dislikes,
                "downvotes": raw_dislikes,
                "comments": thread_comments,
                "engagement_score": round(engagement_score, 4),
                "tree_size": comment_count,
                "total_engagement": raw_likes + raw_dislikes,
                "mean_opinion_delta": round(mean_delta, 4),
                "engaged_agents": sorted(engaged_agents),
            }
        )

    viral_posts.sort(key=lambda item: (item["engagement_score"], item["total_engagement"], item["tree_size"]), reverse=True)
    best = viral_posts[0] if viral_posts else {
        "post_id": None,
        "author": None,
        "author_name": None,
        "stance": "neutral",
        "segment": "neutral",
        "title": None,
        "content": None,
        "body": None,
        "likes": 0,
        "upvotes": 0,
        "dislikes": 0,
        "downvotes": 0,
        "comments": [],
        "engagement_score": 0.0,
        "tree_size": 0,
        "total_engagement": 0,
        "mean_opinion_delta": 0.0,
        "engaged_agents": [],
    }

    return {
        "viral_posts": viral_posts,
        "cascades": viral_posts,
        "top_threads": viral_posts,
        "posts": viral_posts,
        "post_id": best["post_id"],
        "tree_size": best["tree_size"],
        "total_engagement": best["total_engagement"],
        "mean_opinion_delta": best["mean_opinion_delta"],
        "engaged_agents": best["engaged_agents"],
    }


def select_group_chat_agents(
    agents: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
    segment: str,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    influence: dict[str, dict[str, float]] = {}
    for agent in agents:
        agent_id = str(agent.get("id") or agent.get("agent_id") or "")
        if not agent_id:
            continue
        agent_posts = [item for item in interactions if str(item.get("actor_agent_id")) == agent_id]
        post_engagement = sum(int(item.get("likes", 0) or 0) + int(item.get("dislikes", 0) or 0) for item in agent_posts)
        comment_count = sum(1 for item in agent_posts if item.get("type") == "comment")
        replies_received = sum(1 for item in interactions if str(item.get("target_agent_id")) == agent_id)
        influence[agent_id] = {
            "raw_engagement": float(post_engagement),
            "raw_comments": float(comment_count),
            "raw_replies": float(replies_received),
        }

    if not influence:
        return []

    max_eng = max((value["raw_engagement"] for value in influence.values()), default=1.0) or 1.0
    max_com = max((value["raw_comments"] for value in influence.values()), default=1.0) or 1.0
    max_rep = max((value["raw_replies"] for value in influence.values()), default=1.0) or 1.0

    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in agents
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }

    def get_stance(agent_id: str) -> str:
        agent = agent_lookup.get(agent_id)
        if not agent:
            return "unknown"
        score = _as_float(agent.get("opinion_post", 5))
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    ranked: list[tuple[str, dict[str, float]]] = []
    for agent_id, value in influence.items():
        value["score"] = (
            0.4 * (value["raw_engagement"] / max_eng)
            + 0.3 * (value["raw_comments"] / max_com)
            + 0.3 * (value["raw_replies"] / max_rep)
        )
        ranked.append((agent_id, value))

    ranked.sort(key=lambda item: item[1]["score"], reverse=True)
    if segment != "engaged":
        ranked = [item for item in ranked if get_stance(item[0]) == segment]

    return [{"agent_id": agent_id, "influence_score": round(value["score"], 4)} for agent_id, value in ranked[: max(0, int(top_n))]]


class MetricsService:
    """Compute simulation analytics metrics from checkpoint and trace data."""

    def __init__(self, config_service: Any) -> None:
        self.config = config_service

    def _checkpoint_questions(self, use_case: str) -> list[dict[str, Any]]:
        getter = getattr(self.config, "get_checkpoint_questions", None)
        if callable(getter):
            try:
                questions = getter(use_case)
                if isinstance(questions, list):
                    return [item for item in questions if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                return []
        use_case_getter = getattr(self.config, "get_use_case", None)
        if not callable(use_case_getter):
            return []
        try:
            payload = use_case_getter(use_case)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(payload, dict):
            return []
        questions = payload.get("checkpoint_questions", [])
        if not isinstance(questions, list):
            return []
        return [item for item in questions if isinstance(item, dict)]

    def compute_dynamic_metrics(self, agents: list[dict[str, Any]], use_case: str, round_no: int | None = None) -> dict[str, Any]:
        del round_no
        questions = self._checkpoint_questions(use_case)
        results: dict[str, Any] = {}
        total_agents = max(len(agents), 1)

        for question in questions:
            name = question["metric_name"]
            label = question["display_label"]
            field = f"checkpoint_{name}"
            if question["type"] == "scale":
                scores = [_as_float(agent.get(field, 5)) for agent in agents]
                if "threshold" in question:
                    threshold = _as_float(question["threshold"], 7)
                    direction = question.get("threshold_direction", "gte")
                    if direction == "gte":
                        pct = sum(1 for score in scores if score >= threshold) / total_agents * 100
                    else:
                        pct = sum(1 for score in scores if score <= threshold) / total_agents * 100
                    results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
                else:
                    results[name] = {"value": round(_mean(scores) if scores else 0.0, 1), "unit": "/10", "label": label}
            elif question["type"] == "yes-no":
                yes_count = sum(1 for agent in agents if str(agent.get(field, "")).strip().lower() in {"yes", "y"})
                pct = yes_count / total_agents * 100
                results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
        return results

    def compute_polarization_timeseries(self, agents_by_round: dict[int, list[dict[str, Any]]], group_key: str) -> list[dict[str, Any]]:
        return [{"round": round_no, **compute_group_polarization(agents, group_key)} for round_no, agents in agents_by_round.items()]

    def compute_group_polarization(self, agents: list[dict[str, Any]], group_key: str = "planning_area") -> dict[str, Any]:
        return compute_group_polarization(agents, group_key)

    def compute_opinion_flow(self, agents: list[dict[str, Any]]) -> dict[str, Any]:
        return compute_opinion_flow(agents)

    def compute_influence(self, interactions: list[dict[str, Any]], agents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return build_influence_graph(interactions, agents)

    def compute_cascades(self, posts: list[dict[str, Any]], comments: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any]:
        return compute_top_cascade(posts, comments, agents)

    def select_group_chat_agents(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        segment: str,
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        return select_group_chat_agents(agents, interactions, segment, top_n=top_n)
===
from __future__ import annotations

from collections import defaultdict
from statistics import mean as _mean
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:  # noqa: BLE001
        return int(default)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _summarize_text(value: Any, limit: int = 160) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean_text(row.get(key))
        if value:
            return value
    return ""


def _stance_from_score(score: float) -> str:
    if score >= 7:
        return "supporter"
    if score >= 5:
        return "neutral"
    return "dissenter"


def _stance_from_text(text: str) -> str:
    lowered = text.lower()
    support_hits = sum(1 for token in ("support", "agree", "upside", "benefit", "positive", "yes", "pro") if token in lowered)
    dissent_hits = sum(1 for token in ("risk", "concern", "oppose", "against", "problem", "negative", "no", "worry") if token in lowered)
    if support_hits > dissent_hits:
        return "supporter"
    if dissent_hits > support_hits:
        return "dissenter"
    return "neutral"


def _row_stance(row: dict[str, Any], agent: dict[str, Any] | None = None) -> str:
    stance = _clean_text(row.get("stance") or row.get("segment"))
    if stance:
        return stance
    if agent:
        agent_stance = _stance_from_score(_as_float(agent.get("opinion_post", agent.get("opinion_pre", 5.0))))
        if agent_stance:
            return agent_stance
    delta = _as_float(row.get("delta", 0.0))
    if delta > 0:
        return "supporter"
    if delta < 0:
        return "dissenter"
    text = _first_text(row, ("content", "body", "title", "summary"))
    return _stance_from_text(text) if text else "neutral"


def _agent_name(agent: dict[str, Any] | None, fallback: str) -> str:
    if not agent:
        return fallback
    for key in ("name", "agent_name", "display_name", "label"):
        value = _clean_text(agent.get(key))
        if value:
            return value
    persona = agent.get("persona")
    if isinstance(persona, dict):
        for key in ("name", "agent_name", "display_name", "label"):
            value = _clean_text(persona.get(key))
            if value:
                return value
    return fallback


def _actor_id(row: dict[str, Any]) -> str:
    return _clean_text(row.get("actor_agent_id") or row.get("author_agent_id") or row.get("agent_id") or row.get("author") or row.get("name"))


def _row_id(row: dict[str, Any]) -> str:
    return _clean_text(row.get("id") or row.get("post_id") or row.get("comment_id") or row.get("interaction_id"))


def _post_text(row: dict[str, Any]) -> str:
    return _first_text(row, ("title", "content", "body", "summary"))


def _is_discourse_interaction(row: dict[str, Any]) -> bool:
    action_type = _clean_text(row.get("action_type") or row.get("type")).lower()
    if action_type == "trace":
        return False
    content = _clean_text(row.get("content") or row.get("body") or row.get("title"))
    if not content:
        return False
    if content.startswith(("sign_up:", "refresh:", "search_posts:", "search_user:", "like_comment:", "like_post:")):
        return False
    return True


def _engagement_score(row: dict[str, Any]) -> float:
    likes = _as_int(row.get("likes", row.get("upvotes", 0)))
    dislikes = _as_int(row.get("dislikes", row.get("downvotes", 0)))
    delta = abs(_as_float(row.get("delta", 0.0)))
    return float(likes + dislikes) + delta


def _numeric_engagement(row: dict[str, Any]) -> tuple[int, int]:
    likes = _as_int(row.get("likes", row.get("upvotes", 0)))
    dislikes = _as_int(row.get("dislikes", row.get("downvotes", 0)))
    return likes, dislikes


def compute_group_polarization(agents: list[dict[str, Any]], group_key: str = "planning_area") -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []
    for agent in agents:
        key = str(agent.get("persona", {}).get(group_key, "Unknown"))
        score = _as_float(agent.get("opinion_post", 0.0))
        groups[key].append(score)
        all_scores.append(score)

    if not all_scores:
        return {
            "polarization_index": 0.0,
            "severity": "low",
            "by_group_means": {},
            "group_sizes": {},
        }

    overall_mean = _mean(all_scores)
    n = max(1, len(all_scores))
    between = sum(len(values) * ((_mean(values) - overall_mean) ** 2) for values in groups.values()) / n
    total_var = sum((score - overall_mean) ** 2 for score in all_scores) / n
    polarization_index = (between / total_var) if total_var > 0 else 0.0
    severity = (
        "low" if polarization_index < 0.2 else
        "moderate" if polarization_index < 0.5 else
        "high" if polarization_index < 0.8 else
        "critical"
    )

    return {
        "polarization_index": round(polarization_index, 4),
        "severity": severity,
        "by_group_means": {key: round(_mean(values), 4) for key, values in groups.items()},
        "group_sizes": {key: len(values) for key, values in groups.items()},
    }


def compute_opinion_flow(agents: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket(score: float) -> str:
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    initial = {"supporter": 0, "neutral": 0, "dissenter": 0}
    final = {"supporter": 0, "neutral": 0, "dissenter": 0}
    flows: dict[tuple[str, str], int] = defaultdict(int)

    for agent in agents:
        pre = bucket(_as_float(agent.get("opinion_pre", 5)))
        post = bucket(_as_float(agent.get("opinion_post", 5)))
        initial[pre] += 1
        final[post] += 1
        flows[(pre, post)] += 1

    return {
        "initial": initial,
        "final": final,
        "flows": [{"from": source, "to": target, "count": count} for (source, target), count in flows.items()],
    }


def build_influence_graph(interactions: list[dict[str, Any]], agents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in (agents or [])
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }
    edges: dict[tuple[str, str], float] = {}
    actor_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    node_scores: dict[str, float] = defaultdict(float)
    for event in interactions:
        actor = _actor_id(event)
        target = _clean_text(event.get("target_agent_id") or event.get("target") or event.get("reply_to_agent_id"))
        if not actor:
            continue
        if not _is_discourse_interaction(event):
            continue
        actor_rows[actor].append(event)
        engagement_score = _engagement_score(event)
        node_scores[actor] += abs(_as_float(event.get("delta", 0.0))) + (engagement_score * 0.1) + (0.25 if _clean_text(event.get("action_type")).lower() == "comment" else 0.5)
        if not target:
            continue
        weight = abs(_as_float(event.get("delta", 0.0)))
        edges[(str(actor), str(target))] = edges.get((str(actor), str(target)), 0.0) + weight

    top_influencers = sorted(node_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    top_ids = {agent_id for agent_id, _score in top_influencers}
    enriched_influencers: list[dict[str, Any]] = []
    for agent_id, score in top_influencers:
        rows = actor_rows.get(agent_id, [])
        agent = agent_lookup.get(agent_id)
        if rows:
            rows_sorted = sorted(rows, key=lambda row: (_engagement_score(row), abs(_as_float(row.get("delta", 0.0)))), reverse=True)
            top_row = rows_sorted[0]
        else:
            top_row = {}
        top_content = _post_text(top_row)
        viewpoint = _summarize_text(top_content or top_row.get("content") or top_row.get("body") or top_row.get("title"), 160)
        stance = _row_stance(top_row, agent)
        name = _agent_name(agent, agent_id)
        enriched_influencers.append(
            {
                "agent_id": agent_id,
                "name": name,
                "agent_name": name,
                "stance": stance,
                "segment": stance,
                "influence": round(score, 4),
                "influence_score": round(score, 4),
                "score": round(score, 4),
                "top_view": viewpoint,
                "core_viewpoint": viewpoint,
                "top_post": {
                    "post_id": _row_id(top_row) or None,
                    "title": _clean_text(top_row.get("title")) or None,
                    "content": _clean_text(top_row.get("content") or top_row.get("body")) or None,
                    "body": _clean_text(top_row.get("body") or top_row.get("content")) or None,
                    "likes": _numeric_engagement(top_row)[0],
                    "dislikes": _numeric_engagement(top_row)[1],
                    "stance": stance,
                },
            }
        )

    return {
        "top_influencers": enriched_influencers,
        "leaders": [dict(item) for item in enriched_influencers],
        "items": [dict(item) for item in enriched_influencers],
        "nodes": [
            {
                "id": item["agent_id"],
                "name": item["name"],
                "agent_name": item["agent_name"],
                "stance": item["stance"],
                "influence_score": item["influence_score"],
                "top_view": item["top_view"],
                "top_post": item["top_post"],
            }
            for item in enriched_influencers
        ],
        "edges": [
            {"source": actor, "target": target, "weight": round(weight, 4)}
            for (actor, target), weight in edges.items()
            if actor in top_ids or target in top_ids
        ],
        "total_nodes": len(node_scores),
        "total_edges": len(edges),
    }


def compute_top_cascade(posts: list[dict[str, Any]], comments: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any]:
    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in agents
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }
    posts_by_id: dict[str, dict[str, Any]] = {}
    posts_by_actor_round: dict[tuple[str, int], str] = {}
    posts_by_actor: dict[str, list[str]] = defaultdict(list)
    for post in posts:
        post_id = _row_id(post)
        if not post_id:
            continue
        posts_by_id[post_id] = post
        actor_id = _actor_id(post)
        round_no = _as_int(post.get("round_no", 0))
        if actor_id:
            posts_by_actor_round[(actor_id, round_no)] = post_id
            posts_by_actor[actor_id].append(post_id)

    comments_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for comment in comments:
        parent = _clean_text(
            comment.get("parent_post_id")
            or comment.get("parent_id")
            or comment.get("root_post_id")
            or comment.get("reply_to_post_id")
            or comment.get("post_id")
        )
        if not parent:
            actor_id = _actor_id(comment)
            round_no = _as_int(comment.get("round_no", 0))
            target_agent = _clean_text(comment.get("target_agent_id"))
            if actor_id and (actor_id, round_no) in posts_by_actor_round:
                parent = posts_by_actor_round[(actor_id, round_no)]
            elif target_agent and posts_by_actor.get(target_agent):
                parent = posts_by_actor[target_agent][-1]
            elif posts:
                parent = _row_id(posts[-1])
        if parent:
            comments_by_parent[parent].append(comment)

    def build_comment_node(comment: dict[str, Any]) -> dict[str, Any]:
        actor_id = _actor_id(comment)
        agent = agent_lookup.get(actor_id)
        children = [build_comment_node(child) for child in comments_by_parent.get(_row_id(comment), []) if _row_id(child) != _row_id(comment)]
        likes, dislikes = _numeric_engagement(comment)
        stance = _row_stance(comment, agent)
        node = {
            "comment_id": _row_id(comment) or None,
            "author": actor_id or None,
            "author_name": _agent_name(agent, actor_id or "unknown"),
            "stance": stance,
            "content": _clean_text(comment.get("content") or comment.get("body")) or None,
            "body": _clean_text(comment.get("body") or comment.get("content")) or None,
            "likes": likes,
            "upvotes": likes,
            "dislikes": dislikes,
            "downvotes": dislikes,
        }
        if children:
            node["comments"] = children
        return node

    viral_posts: list[dict[str, Any]] = []
    for post in posts:
        post_id = _row_id(post)
        if not post_id:
            continue
        actor_id = _actor_id(post)
        agent = agent_lookup.get(actor_id)
        thread_comments = [build_comment_node(comment) for comment in comments_by_parent.get(post_id, [])]
        comment_count = len(thread_comments)
        comment_likes = sum(int(comment.get("likes", 0) or 0) for comment in thread_comments)
        comment_dislikes = sum(int(comment.get("dislikes", 0) or 0) for comment in thread_comments)
        post_likes, post_dislikes = _numeric_engagement(post)
        raw_likes = post_likes + comment_likes + max(0, int(round(_as_float(post.get("delta", 0.0)) * 2)))
        raw_dislikes = post_dislikes + comment_dislikes + max(0, int(round(abs(min(0.0, _as_float(post.get("delta", 0.0)))) * 2)))
        discussion_deltas: list[float] = []
        engaged_agents = {actor_id} if actor_id else set()
        for comment in comments_by_parent.get(post_id, []):
            comment_actor = _actor_id(comment)
            if comment_actor:
                engaged_agents.add(comment_actor)
            if comment_actor and (agent := agent_lookup.get(comment_actor)):
                discussion_deltas.append(_as_float(agent.get("opinion_post", 0.0)) - _as_float(agent.get("opinion_pre", 0.0)))
        if actor_id and (agent := agent_lookup.get(actor_id)):
            discussion_deltas.append(_as_float(agent.get("opinion_post", 0.0)) - _as_float(agent.get("opinion_pre", 0.0)))
        mean_delta = _mean(discussion_deltas) if discussion_deltas else 0.0
        content = _post_text(post)
        title = _clean_text(post.get("title")) or _summarize_text(content, 80) or f"Post {post_id}"
        stance = _row_stance(post, agent)
        engagement_score = _engagement_score(post) + comment_count + sum(abs(delta) for delta in discussion_deltas)
        viral_posts.append(
            {
                "post_id": post_id,
                "author": actor_id or None,
                "author_name": _agent_name(agent, actor_id or "unknown"),
                "stance": stance,
                "segment": stance,
                "title": title,
                "content": content or None,
                "body": _clean_text(post.get("body") or content) or None,
                "likes": raw_likes,
                "upvotes": raw_likes,
                "dislikes": raw_dislikes,
                "downvotes": raw_dislikes,
                "comments": thread_comments,
                "engagement_score": round(engagement_score, 4),
                "tree_size": comment_count,
                "total_engagement": raw_likes + raw_dislikes,
                "mean_opinion_delta": round(mean_delta, 4),
                "engaged_agents": sorted(engaged_agents),
            }
        )

    viral_posts.sort(key=lambda item: (item["engagement_score"], item["total_engagement"], item["tree_size"]), reverse=True)
    best = viral_posts[0] if viral_posts else {
        "post_id": None,
        "author": None,
        "author_name": None,
        "stance": "neutral",
        "segment": "neutral",
        "title": None,
        "content": None,
        "body": None,
        "likes": 0,
        "upvotes": 0,
        "dislikes": 0,
        "downvotes": 0,
        "comments": [],
        "engagement_score": 0.0,
        "tree_size": 0,
        "total_engagement": 0,
        "mean_opinion_delta": 0.0,
        "engaged_agents": [],
    }

    return {
        "viral_posts": viral_posts,
        "cascades": viral_posts,
        "top_threads": viral_posts,
        "posts": viral_posts,
        "post_id": best["post_id"],
        "tree_size": best["tree_size"],
        "total_engagement": best["total_engagement"],
        "mean_opinion_delta": best["mean_opinion_delta"],
        "engaged_agents": best["engaged_agents"],
    }


def select_group_chat_agents(
    agents: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
    segment: str,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    influence: dict[str, dict[str, float]] = {}
    for agent in agents:
        agent_id = str(agent.get("id") or agent.get("agent_id") or "")
        if not agent_id:
            continue
        agent_posts = [item for item in interactions if str(item.get("actor_agent_id")) == agent_id]
        post_engagement = sum(int(item.get("likes", 0) or 0) + int(item.get("dislikes", 0) or 0) for item in agent_posts)
        comment_count = sum(1 for item in agent_posts if item.get("type") == "comment")
        replies_received = sum(1 for item in interactions if str(item.get("target_agent_id")) == agent_id)
        influence[agent_id] = {
            "raw_engagement": float(post_engagement),
            "raw_comments": float(comment_count),
            "raw_replies": float(replies_received),
        }

    if not influence:
        return []

    max_eng = max((value["raw_engagement"] for value in influence.values()), default=1.0) or 1.0
    max_com = max((value["raw_comments"] for value in influence.values()), default=1.0) or 1.0
    max_rep = max((value["raw_replies"] for value in influence.values()), default=1.0) or 1.0

    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in agents
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }

    def get_stance(agent_id: str) -> str:
        agent = agent_lookup.get(agent_id)
        if not agent:
            return "unknown"
        score = _as_float(agent.get("opinion_post", 5))
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    ranked: list[tuple[str, dict[str, float]]] = []
    for agent_id, value in influence.items():
        value["score"] = (
            0.4 * (value["raw_engagement"] / max_eng)
            + 0.3 * (value["raw_comments"] / max_com)
            + 0.3 * (value["raw_replies"] / max_rep)
        )
        ranked.append((agent_id, value))

    ranked.sort(key=lambda item: item[1]["score"], reverse=True)
    if segment != "engaged":
        ranked = [item for item in ranked if get_stance(item[0]) == segment]

    return [{"agent_id": agent_id, "influence_score": round(value["score"], 4)} for agent_id, value in ranked[: max(0, int(top_n))]]


class MetricsService:
    """Compute simulation analytics metrics from checkpoint and trace data."""

    def __init__(self, config_service: Any) -> None:
        self.config = config_service

    def _checkpoint_questions(self, use_case: str) -> list[dict[str, Any]]:
        # Try new V2 analysis_questions first
        getter = getattr(self.config, "get_analysis_questions", None)
        if callable(getter):
            try:
                questions = getter(use_case)
                if isinstance(questions, list) and questions:
                    return [item for item in questions if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                pass
        # Fallback to V1 checkpoint_questions
        getter = getattr(self.config, "get_checkpoint_questions", None)
        if callable(getter):
            try:
                questions = getter(use_case)
                if isinstance(questions, list):
                    return [item for item in questions if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                return []
        use_case_getter = getattr(self.config, "get_use_case", None)
        if not callable(use_case_getter):
            return []
        try:
            payload = use_case_getter(use_case)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(payload, dict):
            return []
        questions = payload.get("analysis_questions", payload.get("checkpoint_questions", []))
        if not isinstance(questions, list):
            return []
        return [item for item in questions if isinstance(item, dict)]

    def compute_dynamic_metrics(self, agents: list[dict[str, Any]], use_case: str, round_no: int | None = None) -> dict[str, Any]:
        del round_no
        questions = self._checkpoint_questions(use_case)
        results: dict[str, Any] = {}
        total_agents = max(len(agents), 1)

        for question in questions:
            q_type = question.get("type", "scale")
            name = question.get("metric_name", "")
            if not name:
                continue
            # V2 uses metric_label, V1 uses display_label
            label = question.get("metric_label", question.get("display_label", name))
            field = f"checkpoint_{name}"

            # Skip open-ended questions — no numeric metric to compute
            if q_type == "open-ended":
                continue

            if q_type == "scale":
                scores = [_as_float(agent.get(field, 5)) for agent in agents]
                if "threshold" in question:
                    threshold = _as_float(question["threshold"], 7)
                    direction = question.get("threshold_direction", "gte")
                    if direction == "gte":
                        pct = sum(1 for score in scores if score >= threshold) / total_agents * 100
                    else:
                        pct = sum(1 for score in scores if score <= threshold) / total_agents * 100
                    results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
                else:
                    results[name] = {"value": round(_mean(scores) if scores else 0.0, 1), "unit": "/10", "label": label}
            elif q_type == "yes-no":
                yes_count = sum(1 for agent in agents if str(agent.get(field, "")).strip().lower() in {"yes", "y"})
                pct = yes_count / total_agents * 100
                results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
        return results

    # ── Existing analytics methods ──

    def compute_polarization_timeseries(self, agents_by_round: dict[int, list[dict[str, Any]]], group_key: str) -> list[dict[str, Any]]:
        return [{"round": round_no, **compute_group_polarization(agents, group_key)} for round_no, agents in agents_by_round.items()]

    def compute_group_polarization(self, agents: list[dict[str, Any]], group_key: str = "planning_area") -> dict[str, Any]:
        return compute_group_polarization(agents, group_key)

    def compute_opinion_flow(self, agents: list[dict[str, Any]]) -> dict[str, Any]:
        return compute_opinion_flow(agents)

    def compute_influence(self, interactions: list[dict[str, Any]], agents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return build_influence_graph(interactions, agents)

    def compute_cascades(self, posts: list[dict[str, Any]], comments: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any]:
        return compute_top_cascade(posts, comments, agents)

    def select_group_chat_agents(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        segment: str,
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        return select_group_chat_agents(agents, interactions, segment, top_n=top_n)

    # ── New V2 insight-block methods ──

    def compute_segment_heatmap(
        self,
        agents: list[dict[str, Any]],
        analysis_questions: list[dict[str, Any]],
        group_key: str = "planning_area",
    ) -> dict[str, Any]:
        """Compute metric scores broken out by demographic segment.

        Returns a heatmap-ready structure: {segments: [{segment, metrics: {name: value}}]}.
        Only quantitative analysis_questions are included.
        """
        quantitative = [q for q in analysis_questions if q.get("type") in ("scale", "yes-no")]
        if not quantitative:
            return {"status": "not_applicable", "reason": "No quantitative analysis questions to segment."}

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for agent in agents:
            key = str(agent.get("persona", {}).get(group_key, "Unknown"))
            groups[key].append(agent)

        segments: list[dict[str, Any]] = []
        for segment_name, segment_agents in sorted(groups.items(), key=lambda x: -len(x[1])):
            metrics: dict[str, float] = {}
            total = max(len(segment_agents), 1)
            for q in quantitative:
                field = f"checkpoint_{q['metric_name']}"
                if q["type"] == "scale":
                    scores = [_as_float(a.get(field, 5)) for a in segment_agents]
                    if "threshold" in q:
                        threshold = _as_float(q["threshold"], 7)
                        metrics[q["metric_name"]] = round(sum(1 for s in scores if s >= threshold) / total * 100, 1)
                    else:
                        metrics[q["metric_name"]] = round(_mean(scores) if scores else 0.0, 1)
                elif q["type"] == "yes-no":
                    yes_count = sum(1 for a in segment_agents if str(a.get(field, "")).strip().lower() in {"yes", "y"})
                    metrics[q["metric_name"]] = round(yes_count / total * 100, 1)
            segments.append({"segment": segment_name, "count": len(segment_agents), "metrics": metrics})

        return {"segments": segments[:15]}

    def extract_pain_points(
        self,
        interactions: list[dict[str, Any]],
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Extract top pain points from negative-sentiment interactions.

        Uses a simple heuristic: interactions with negative delta or dissenting stance.
        Returns ranked list of complaint themes with frequency counts.
        """
        negative_content: list[str] = []
        for row in interactions:
            if not _is_discourse_interaction(row):
                continue
            delta = _as_float(row.get("delta", 0.0))
            content = _clean_text(row.get("content") or row.get("body") or "")
            if delta < 0 and content:
                negative_content.append(content)

        if not negative_content:
            return {"status": "not_applicable", "reason": "No negative interactions found to extract pain points."}

        # Simple keyword frequency extraction as a heuristic
        # In production, this would use LLM-assisted theme extraction
        word_freq: dict[str, int] = defaultdict(int)
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "i", "my", "me",
                       "this", "that", "it", "to", "of", "in", "for", "and", "or", "not", "with",
                       "but", "on", "at", "by", "from", "as", "do", "does", "did", "have", "has",
                       "will", "would", "could", "should", "can", "may", "no", "so", "if", "we"}
        for text in negative_content:
            words = text.lower().split()
            for word in words:
                cleaned = "".join(c for c in word if c.isalnum())
                if len(cleaned) > 3 and cleaned not in stop_words:
                    word_freq[cleaned] += 1

        top_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        pain_points = [{"term": term, "frequency": freq, "sample_count": len(negative_content)} for term, freq in top_terms]
        return {"pain_points": pain_points, "total_negative_posts": len(negative_content)}

    def extract_top_objections(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        metric_name: str,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Extract top objections from agents who scored low on a metric."""
        field = f"checkpoint_{metric_name}"
        low_agents = {
            str(a.get("id") or a.get("agent_id"))
            for a in agents
            if _as_float(a.get(field, 5)) < 4
        }

        if not low_agents:
            return {"status": "not_applicable", "reason": "No agents scored low enough to extract objections."}

        objection_texts: list[dict[str, Any]] = []
        for row in interactions:
            if not _is_discourse_interaction(row):
                continue
            actor = _actor_id(row)
            if actor in low_agents:
                content = _clean_text(row.get("content") or row.get("body") or "")
                if content:
                    objection_texts.append({
                        "agent_id": actor,
                        "content": _summarize_text(content, 200),
                        "round_no": _as_int(row.get("round_no", 0)),
                    })

        objection_texts.sort(key=lambda x: _engagement_score(x) if isinstance(x, dict) else 0, reverse=True)
        return {"objections": objection_texts[:top_n], "low_scoring_agents": len(low_agents)}

    def get_top_advocates(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        metric_name: str | None = None,
        top_n: int = 3,
    ) -> dict[str, Any]:
        """Get agents with highest scores on a given metric, plus their key posts."""
        if metric_name:
            field = f"checkpoint_{metric_name}"
            scored = [(a, _as_float(a.get(field, 5))) for a in agents]
        else:
            scored = [(a, _as_float(a.get("opinion_post", 5))) for a in agents]

        scored.sort(key=lambda x: x[1], reverse=True)
        top_agents = scored[:top_n]

        advocates: list[dict[str, Any]] = []
        for agent, score in top_agents:
            agent_id = str(agent.get("id") or agent.get("agent_id") or "")
            # Find their best post
            agent_posts = [
                row for row in interactions
                if _actor_id(row) == agent_id and _is_discourse_interaction(row)
            ]
            agent_posts.sort(key=lambda r: _engagement_score(r), reverse=True)
            best_post = agent_posts[0] if agent_posts else {}
            advocates.append({
                "agent_id": agent_id,
                "name": _agent_name(agent, agent_id),
                "score": round(score, 1),
                "key_post": _summarize_text(_post_text(best_post), 200) if best_post else None,
                "persona_summary": _build_persona_summary(agent),
            })

        return {"advocates": advocates}

    def get_viral_posts(
        self,
        interactions: list[dict[str, Any]],
        top_n: int = 3,
    ) -> dict[str, Any]:
        """Get posts sorted by total engagement (likes + dislikes + comments)."""
        posts = [
            row for row in interactions
            if str(row.get("action_type", "")).lower() in {"create_post", "post_created", "post"}
        ]
        if not posts:
            return {"status": "not_applicable", "reason": "No posts found in simulation data."}

        enriched: list[dict[str, Any]] = []
        for post in posts:
            engagement = _engagement_score(post)
            likes, dislikes = _numeric_engagement(post)
            enriched.append({
                "post_id": _row_id(post),
                "author": _actor_id(post),
                "content": _summarize_text(_post_text(post), 200),
                "likes": likes,
                "dislikes": dislikes,
                "engagement_score": round(engagement, 2),
                "round_no": _as_int(post.get("round_no", 0)),
            })

        enriched.sort(key=lambda x: x["engagement_score"], reverse=True)
        return {"viral_posts": enriched[:top_n]}

    def compute_reaction_distribution(
        self,
        agents: list[dict[str, Any]],
        metric_name: str,
    ) -> dict[str, Any]:
        """Compute histogram distribution of a metric across agents."""
        field = f"checkpoint_{metric_name}"
        scores = [_as_float(a.get(field, 5)) for a in agents]
        if not scores:
            return {"status": "not_applicable", "reason": "No scores found for this metric."}

        # Build histogram buckets (1-10 scale)
        buckets = {i: 0 for i in range(1, 11)}
        for score in scores:
            bucket = max(1, min(10, int(round(score))))
            buckets[bucket] += 1

        return {
            "metric_name": metric_name,
            "distribution": [{"score": k, "count": v} for k, v in sorted(buckets.items())],
            "mean": round(_mean(scores), 2),
            "total_agents": len(scores),
        }

    def compute_insight_block(
        self,
        block_type: str,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        analysis_questions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Dispatch an insight block computation by type.

        Returns the computed data, or a not_applicable status if data is insufficient.
        """
        try:
            if block_type == "polarization_index":
                return self.compute_group_polarization(agents, kwargs.get("group_key", "planning_area"))
            elif block_type == "opinion_flow":
                return self.compute_opinion_flow(agents)
            elif block_type == "top_influencers":
                return self.compute_influence(interactions, agents)
            elif block_type == "viral_cascade":
                posts = [r for r in interactions if str(r.get("action_type", "")).lower() in {"create_post", "post_created", "post"}]
                comments = [r for r in interactions if "comment" in str(r.get("action_type", "")).lower()]
                return compute_top_cascade(posts, comments, agents)
            elif block_type == "segment_heatmap":
                return self.compute_segment_heatmap(agents, analysis_questions, kwargs.get("group_key", "planning_area"))
            elif block_type == "pain_points":
                return self.extract_pain_points(interactions, top_n=kwargs.get("count", 5))
            elif block_type == "top_advocates":
                metric_ref = kwargs.get("metric_ref")
                return self.get_top_advocates(agents, interactions, metric_name=metric_ref, top_n=kwargs.get("count", 3))
            elif block_type == "competitive_mentions":
                # Placeholder — would require LLM extraction in production
                return {"status": "not_applicable", "reason": "Competitive mention extraction requires LLM analysis."}
            elif block_type == "reaction_spectrum":
                metric_ref = kwargs.get("metric_ref", "engagement_score")
                return self.compute_reaction_distribution(agents, metric_ref)
            elif block_type == "top_objections":
                metric_ref = kwargs.get("metric_ref", "conversion_intent")
                return self.extract_top_objections(agents, interactions, metric_ref, top_n=kwargs.get("count", 5))
            elif block_type == "viral_posts":
                return self.get_viral_posts(interactions, top_n=kwargs.get("count", 3))
            else:
                return {"status": "not_applicable", "reason": f"Unknown insight block type: {block_type}"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "not_applicable", "reason": str(exc)}


def _build_persona_summary(agent: dict[str, Any]) -> str:
    """Build a short persona summary from agent data."""
    persona = agent.get("persona", {})
    parts: list[str] = []
    for key in ("age", "occupation", "planning_area", "income_bracket"):
        val = _clean_text(persona.get(key))
        if val:
            parts.append(val)
    return ", ".join(parts) if parts else "Unknown"

```

- `compute_insight_block()` dispatcher with 9 block types
- Graceful `not_applicable` fallback for unused block types

### QuestionMetadataService (NEW)
```diff:question_metadata_service.py
===
"""Service for generating metric metadata for user-defined analysis questions.

When a user adds or edits a custom analysis question on Screen 1,
this service calls the LLM to infer a type, metric_name, metric_label,
metric_unit, threshold, report_title, and tooltip.
"""
from __future__ import annotations

import json
from typing import Any

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient


_METADATA_PROMPT_TEMPLATE = """\
Given this analysis question that will be asked to simulated agents:
"{question}"

Generate the following metadata as JSON:
- type: "scale" if the question asks for a 1-10 rating, "yes-no" if it asks yes/no, "open-ended" otherwise
- metric_name: a snake_case identifier (e.g., "approval_rate")
- metric_label: a short human-readable label (e.g., "Approval Rate")
- metric_unit: "%" if measuring a percentage of agents, "/10" if measuring a mean score, "text" if qualitative
- threshold: if type is "scale" and metric_unit is "%", suggest a reasonable threshold (usually 7)
- threshold_direction: "gte" (default)
- report_title: a concise section title for the report
- tooltip: a one-sentence explanation of how this metric is computed

Return valid JSON only.
"""


class QuestionMetadataService:
    """Generates metric metadata for user-defined analysis questions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = GeminiChatClient(settings)

    async def generate_metric_metadata(self, question_text: str) -> dict[str, Any]:
        """Calls LLM to generate type, metric_name, metric_label, etc."""
        prompt = _METADATA_PROMPT_TEMPLATE.format(question=question_text.strip())
        try:
            raw = self.llm.complete_required(
                prompt,
                system_prompt=(
                    "You are a metric schema designer. Return valid JSON only "
                    "with the exact keys requested. No markdown fences."
                ),
            )
            parsed = _parse_json_object(raw)
        except Exception:  # noqa: BLE001
            # Fallback: return an open-ended metadata stub
            parsed = self._fallback_metadata(question_text)
        return self._normalize(parsed, question_text)

    def generate_metric_metadata_sync(self, question_text: str) -> dict[str, Any]:
        """Synchronous variant of generate_metric_metadata."""
        prompt = _METADATA_PROMPT_TEMPLATE.format(question=question_text.strip())
        try:
            raw = self.llm.complete_required(
                prompt,
                system_prompt=(
                    "You are a metric schema designer. Return valid JSON only "
                    "with the exact keys requested. No markdown fences."
                ),
            )
            parsed = _parse_json_object(raw)
        except Exception:  # noqa: BLE001
            parsed = self._fallback_metadata(question_text)
        return self._normalize(parsed, question_text)

    def validate_question(self, question: dict[str, Any]) -> bool:
        """Validates that a question has all required fields."""
        required = {"question", "type", "metric_name", "report_title"}
        return all(question.get(key) for key in required)

    def _fallback_metadata(self, question_text: str) -> dict[str, Any]:
        slug = question_text[:40].strip().lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        metric_name = "_".join(slug.split()[:4]) or "custom_metric"
        return {
            "type": "open-ended",
            "metric_name": metric_name,
            "metric_label": "",
            "metric_unit": "text",
            "report_title": question_text[:60],
            "tooltip": f"Qualitative analysis based on: {question_text[:80]}",
        }

    def _normalize(self, parsed: dict[str, Any], question_text: str) -> dict[str, Any]:
        q_type = str(parsed.get("type", "open-ended")).strip().lower()
        if q_type not in {"scale", "yes-no", "open-ended"}:
            q_type = "open-ended"

        result: dict[str, Any] = {
            "question": question_text.strip(),
            "type": q_type,
            "metric_name": str(parsed.get("metric_name", "custom_metric")).strip(),
            "report_title": str(parsed.get("report_title", question_text[:60])).strip(),
            "tooltip": str(parsed.get("tooltip", "")).strip(),
        }

        # Only include metric fields for quantitative types
        if q_type in {"scale", "yes-no"}:
            result["metric_label"] = str(parsed.get("metric_label", "")).strip()
            result["metric_unit"] = str(parsed.get("metric_unit", "/10")).strip()
            if q_type == "scale" and result["metric_unit"] == "%":
                try:
                    result["threshold"] = int(parsed.get("threshold", 7))
                except (TypeError, ValueError):
                    result["threshold"] = 7
                result["threshold_direction"] = str(parsed.get("threshold_direction", "gte")).strip()

        return result


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data
```

- LLM-based metadata inference: auto-generates `type`, `metric_label`, `metric_unit`, `threshold`

### ReportService
```diff:report_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import io
import json
from typing import Any

from docx import Document

from mckainsey.config import Settings
from mckainsey.services.config_service import ConfigService
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.memory_service import MemoryService
from mckainsey.services.storage import SimulationStore


class ReportService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        self.memory = MemoryService(settings)

    def generate_structured_report(self, simulation_id: str, use_case: str | None = None) -> dict[str, Any]:
        existing = self.store.get_report_state(simulation_id)
        if existing and existing.get("status") == "completed":
            return existing

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        knowledge = self.store.get_knowledge_artifact(simulation_id) or {}
        population = self.store.get_population_artifact(simulation_id) or {}
        baseline = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="baseline")
        final = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="final")
        events = self.store.list_simulation_events(simulation_id)

        payload: dict[str, Any] = {}
        if self._should_request_structured_report_seed():
            prompt = self._build_structured_report_prompt(
                simulation_id=simulation_id,
                use_case=use_case,
                knowledge=knowledge,
                population=population,
                agents=agents,
                interactions=interactions,
                baseline=baseline,
                final=final,
                events=events,
            )
            try:
                raw = self.llm.complete_required(
                    prompt,
                    system_prompt=(
                        "You are McKAInsey ReportAgent. Return valid JSON only using the requested schema. "
                        "Every claim must be grounded in provided evidence."
                    ),
                )
            except Exception:  # noqa: BLE001
                raw = ""
            try:
                parsed_payload = _parse_json_object(raw) if raw else {}
            except Exception:  # noqa: BLE001
                parsed_payload = {}
            if isinstance(parsed_payload, dict):
                payload = parsed_payload

        normalized = self._normalize_structured_report_payload(simulation_id, payload)
        return self._enrich_structured_report_payload(
            simulation_id,
            normalized,
            use_case=use_case,
            agents=agents,
            interactions=interactions,
            baseline=baseline,
            final=final,
            events=events,
            knowledge=knowledge,
            population=population,
        )

    def _should_request_structured_report_seed(self) -> bool:
        # Local Ollama models have been the slowest and least reliable source of
        # large JSON objects in live mode. We still build a report from the real
        # simulation artifacts, but skip the heavyweight seed request here.
        return self.llm.provider != "ollama"

    def build_report(self, simulation_id: str) -> dict[str, Any]:
        cached = self.store.get_cached_report(simulation_id)
        if cached:
            return cached

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        pre = [float(a["opinion_pre"]) for a in agents]
        post = [float(a["opinion_post"]) for a in agents]

        by_area_pre: dict[str, list[float]] = defaultdict(list)
        by_area_post: dict[str, list[float]] = defaultdict(list)
        by_income_post: dict[str, list[float]] = defaultdict(list)
        influence: dict[str, float] = defaultdict(float)
        agent_persona: dict[str, dict[str, Any]] = {}
        for a in agents:
            area = str(a["persona"].get("planning_area", "Unknown"))
            income = str(a["persona"].get("income_bracket", "Unknown"))
            by_area_pre[area].append(float(a["opinion_pre"]))
            by_area_post[area].append(float(a["opinion_post"]))
            by_income_post[income].append(float(a["opinion_post"]))
            agent_persona[a["agent_id"]] = a["persona"]

        for i in interactions:
            if i.get("target_agent_id"):
                influence[i["actor_agent_id"]] += abs(float(i.get("delta", 0)))

        last_reason_by_agent: dict[str, str] = {}
        for i in interactions:
            text = str(i.get("content", "")).strip()
            if text:
                last_reason_by_agent[i["actor_agent_id"]] = text[:240]

        influential_agents: list[dict[str, Any]] = []
        for agent_id, score in sorted(influence.items(), key=lambda x: x[1], reverse=True)[:10]:
            persona = agent_persona.get(agent_id, {})
            influential_agents.append(
                {
                    "agent_id": agent_id,
                    "influence_score": round(score, 4),
                    "planning_area": str(persona.get("planning_area", "Unknown")),
                    "occupation": str(persona.get("occupation", "Unknown")),
                    "income_bracket": str(persona.get("income_bracket", "Unknown")),
                    "latest_argument": last_reason_by_agent.get(agent_id, "No recent argument captured."),
                }
            )

        area_metrics: list[dict[str, Any]] = []
        for area, post_scores in by_area_post.items():
            pre_scores = by_area_pre.get(area, [])
            post_mean = _mean(post_scores)
            pre_mean = _mean(pre_scores)
            approval_post = _approval(post_scores)
            mean_shift = post_mean - pre_mean
            friction = abs(mean_shift) * (1 - approval_post)
            area_metrics.append(
                {
                    "planning_area": area,
                    "avg_pre_opinion": round(pre_mean, 4),
                    "avg_post_opinion": round(post_mean, 4),
                    "approval_post": round(approval_post, 4),
                    "mean_shift": round(mean_shift, 4),
                    "friction_index": round(friction, 4),
                    "cohort_size": len(post_scores),
                }
            )

        top_dissenting = sorted(
            area_metrics,
            key=lambda x: (x["approval_post"], -x["friction_index"]),
        )[:8]

        income_metrics = [
            {
                "income_bracket": income,
                "approval_post": round(_approval(scores), 4),
                "avg_post_opinion": round(_mean(scores), 4),
                "cohort_size": len(scores),
            }
            for income, scores in by_income_post.items()
        ]

        arguments_for = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
                "strength": round(abs(float(i.get("delta", 0))), 4),
            }
            for i in interactions
            if float(i.get("delta", 0)) > 0
        ]
        arguments_for = sorted(arguments_for, key=lambda x: x["strength"], reverse=True)[:12]

        arguments_against = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
                "strength": round(abs(float(i.get("delta", 0))), 4),
            }
            for i in interactions
            if float(i.get("delta", 0)) < 0
        ]
        arguments_against = sorted(arguments_against, key=lambda x: x["strength"], reverse=True)[:12]

        executive_summary = self.llm.complete(
            prompt=(
                f"Generate a concise executive summary for simulation {simulation_id}. "
                f"Pre approval={_approval(pre):.2f}, post approval={_approval(post):.2f}, "
                f"net shift={_mean(post)-_mean(pre):.2f}. "
                f"Top dissent cohorts={top_dissenting[:3]}."
            ),
            system_prompt="You are ReportAgent. Return concise strategic summary.",
        )

        recommendations = self._recommend(
            simulation_id=simulation_id,
            top_dissenting=top_dissenting,
            income_metrics=income_metrics,
            arguments_for=arguments_for,
            arguments_against=arguments_against,
        )

        report = {
            "simulation_id": simulation_id,
            "executive_summary": executive_summary,
            "approval_rates": {
                "stage3a": round(_approval(pre), 4),
                "stage3b": round(_approval(post), 4),
                "delta": round(_approval(post) - _approval(pre), 4),
            },
            "top_dissenting_demographics": top_dissenting,
            "friction_by_planning_area": sorted(area_metrics, key=lambda x: x["friction_index"], reverse=True),
            "income_cohorts": sorted(income_metrics, key=lambda x: x["approval_post"]),
            "influential_agents": influential_agents,
            "key_arguments_for": arguments_for,
            "key_arguments_against": arguments_against,
            "recommendations": recommendations,
        }

        self.store.cache_report(simulation_id, report)
        return report

    def report_chat(self, simulation_id: str, message: str) -> str:
        report = self.build_report(simulation_id)
        prompt = (
            f"Report JSON:\n{report}\n\n"
            f"User asks: {message}\n"
            "Provide a direct, data-grounded answer with concrete cohort references."
        )
        return self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")

    def report_chat_payload(self, simulation_id: str, message: str) -> dict[str, Any]:
        report = self.build_report(simulation_id)
        zep_context = self.memory.search_simulation_context(simulation_id, message, limit=8)
        zep_excerpt = "\n".join(
            f"- {item['content']}"
            for item in zep_context["episodes"][:6]
        )
        prompt = (
            f"Report JSON:\n{report}\n\n"
            f"Relevant Zep Cloud memory search results:\n{zep_excerpt or '- none'}\n\n"
            f"User asks: {message}\n"
            "Provide a direct, data-grounded answer with concrete cohort references."
        )
        response = self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "response": response,
            "model_provider": self.llm.provider,
            "model_name": self.llm.model_name,
            "gemini_model": self.llm.model_name,
            "zep_context_used": zep_context["zep_context_used"],
        }

    def build_v2_report(self, simulation_id: str, use_case: str | None = None) -> dict[str, Any]:
        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        pre_scores = [float(agent.get("opinion_pre", 5.0) or 5.0) for agent in agents]
        post_scores = [float(agent.get("opinion_post", 5.0) or 5.0) for agent in agents]
        round_count = max((int(item.get("round_no", 0) or 0) for item in interactions), default=0)
        metric_label = "Approval Rate"
        initial_metric = round(_approval(pre_scores) * 100.0, 1)
        final_metric = round(_approval(post_scores) * 100.0, 1)

        questions = self._resolve_guiding_questions(use_case)
        evidence_pool = self._extract_evidence(interactions)
        sections: list[dict[str, Any]] = []
        for question in questions:
            answer = self._answer_guiding_question(simulation_id, question, agents, interactions)
            sections.append(
                {
                    "question": question,
                    "answer": answer,
                    "evidence": evidence_pool[:3],
                }
            )

        supporting_views = [
            str(item.get("content", "")).strip()
            for item in sorted(interactions, key=lambda row: float(row.get("delta", 0.0) or 0.0), reverse=True)
            if float(item.get("delta", 0.0) or 0.0) > 0 and str(item.get("content", "")).strip()
        ][:5]
        dissenting_views = [
            str(item.get("content", "")).strip()
            for item in sorted(interactions, key=lambda row: float(row.get("delta", 0.0) or 0.0))
            if float(item.get("delta", 0.0) or 0.0) < 0 and str(item.get("content", "")).strip()
        ][:5]

        demographic_breakdown = self._build_demographic_breakdown(agents)
        recommendations = self._build_v2_recommendations(demographic_breakdown, dissenting_views)
        executive_summary = self._build_v2_executive_summary(
            simulation_id=simulation_id,
            initial_metric=initial_metric,
            final_metric=final_metric,
            round_count=round_count,
            supporting_views=supporting_views,
            dissenting_views=dissenting_views,
        )

        return {
            "session_id": simulation_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "executive_summary": executive_summary,
            "quick_stats": {
                "initial_metric_value": initial_metric,
                "final_metric_value": final_metric,
                "metric_label": metric_label,
                "agent_count": len(agents),
                "round_count": round_count,
            },
            "sections": sections,
            "supporting_views": supporting_views,
            "dissenting_views": dissenting_views,
            "demographic_breakdown": demographic_breakdown,
            "key_recommendations": recommendations,
            "methodology": {
                "agents": len(agents),
                "rounds": round_count,
                "model": self.llm.model_name,
                "provider": self.llm.provider,
                "memory_backend_order": "graphiti->zep->local",
            },
        }

    def export_v2_report_docx(self, simulation_id: str, report: dict[str, Any] | None = None, use_case: str | None = None) -> bytes:
        payload = report or self.build_v2_report(simulation_id, use_case=use_case)
        document = Document()
        document.add_heading("McKAInsey Analysis Report", level=0)
        document.add_paragraph(f"Session: {payload.get('session_id', simulation_id)}")
        document.add_paragraph(f"Generated: {payload.get('generated_at', '')}")

        document.add_heading("Executive Summary", level=1)
        document.add_paragraph(str(payload.get("executive_summary", "")))

        quick_stats = payload.get("quick_stats", {})
        if isinstance(quick_stats, dict):
            document.add_heading("Quick Stats", level=1)
            document.add_paragraph(
                f"{quick_stats.get('metric_label', 'Metric')}: "
                f"{quick_stats.get('initial_metric_value', 0)} -> {quick_stats.get('final_metric_value', 0)}"
            )
            document.add_paragraph(
                f"Agents: {quick_stats.get('agent_count', 0)} | Rounds: {quick_stats.get('round_count', 0)}"
            )

        document.add_heading("Guiding Prompt Sections", level=1)
        for section in payload.get("sections", []):
            if not isinstance(section, dict):
                continue
            document.add_heading(str(section.get("question", "Section")), level=2)
            document.add_paragraph(str(section.get("answer", "")))
            evidence = section.get("evidence", [])
            if isinstance(evidence, list) and evidence:
                document.add_paragraph("Evidence:")
                for item in evidence:
                    if isinstance(item, dict):
                        quote = str(item.get("quote", "")).strip()
                        agent_id = str(item.get("agent_id", ""))
                        post_id = str(item.get("post_id", ""))
                        document.add_paragraph(
                            f"{agent_id} / {post_id}: {quote}",
                            style="List Bullet",
                        )

        document.add_heading("Supporting Views", level=1)
        for text in payload.get("supporting_views", []):
            document.add_paragraph(str(text), style="List Bullet")

        document.add_heading("Dissenting Views", level=1)
        for text in payload.get("dissenting_views", []):
            document.add_paragraph(str(text), style="List Bullet")

        demographic_rows = payload.get("demographic_breakdown", [])
        if isinstance(demographic_rows, list) and demographic_rows:
            document.add_heading("Demographic Breakdown", level=1)
            table = document.add_table(rows=1, cols=4)
            header = table.rows[0].cells
            header[0].text = "Segment"
            header[1].text = "Supporter"
            header[2].text = "Neutral"
            header[3].text = "Dissenter"
            for row in demographic_rows:
                if not isinstance(row, dict):
                    continue
                cells = table.add_row().cells
                cells[0].text = str(row.get("segment", ""))
                cells[1].text = str(row.get("supporter", 0))
                cells[2].text = str(row.get("neutral", 0))
                cells[3].text = str(row.get("dissenter", 0))

        document.add_heading("Key Recommendations", level=1)
        for item in payload.get("key_recommendations", []):
            document.add_paragraph(str(item), style="List Bullet")

        methodology = payload.get("methodology", {})
        if isinstance(methodology, dict):
            document.add_heading("Methodology", level=1)
            for key, value in methodology.items():
                document.add_paragraph(f"{key}: {value}")

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _resolve_guiding_questions(self, use_case: str | None) -> list[str]:
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                checkpoint_questions = config_service.get_checkpoint_questions(use_case)
            except Exception:  # noqa: BLE001
                checkpoint_questions = []
            checkpoint_prompts = [
                str(item.get("question", "")).strip()
                for item in checkpoint_questions
                if isinstance(item, dict) and str(item.get("question", "")).strip()
            ]
            if checkpoint_prompts:
                return checkpoint_prompts
            try:
                sections = config_service.get_report_sections(use_case)
            except Exception:  # noqa: BLE001
                sections = []
            report_prompts = [
                str(item.get("prompt") or item.get("title") or "").strip()
                for item in sections
                if isinstance(item, dict) and str(item.get("prompt") or item.get("title") or "").strip()
            ]
            if report_prompts:
                return report_prompts

        return [
            "What are the major shifts in opinion across rounds?",
            "Which arguments most strongly support the policy?",
            "Which arguments most strongly oppose the policy?",
        ]

    def _extract_evidence(self, interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for row in interactions:
            quote = str(row.get("content", "")).strip()
            if not quote:
                continue
            evidence.append(
                {
                    "agent_id": str(row.get("actor_agent_id", "")),
                    "post_id": str(row.get("post_id") or row.get("id") or ""),
                    "quote": quote[:280],
                }
            )
        return evidence

    def _answer_guiding_question(
        self,
        simulation_id: str,
        question: str,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
    ) -> str:
        prompt = (
            f"Simulation ID: {simulation_id}\n"
            f"Guiding question: {question}\n"
            f"Agent sample size: {len(agents)}\n"
            f"Recent interactions: {json.dumps(interactions[-20:], ensure_ascii=False)[:6000]}\n"
            "Respond in 2-4 sentences and reference evidence from the interactions."
        )
        try:
            return self.llm.complete_required(
                prompt,
                system_prompt="You are McKAInsey ReportAgent. Stay factual and evidence-grounded.",
            )
        except Exception:  # noqa: BLE001
            return "The available interactions indicate this question can be answered from observed cohort arguments and sentiment shifts."

    def _build_demographic_breakdown(self, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"supporter": 0, "neutral": 0, "dissenter": 0})
        for agent in agents:
            segment = str(agent.get("persona", {}).get("planning_area", "Unknown"))
            score = float(agent.get("opinion_post", 5.0) or 5.0)
            if score >= 7:
                grouped[segment]["supporter"] += 1
            elif score >= 5:
                grouped[segment]["neutral"] += 1
            else:
                grouped[segment]["dissenter"] += 1
        rows = [
            {
                "segment": segment,
                "supporter": values["supporter"],
                "neutral": values["neutral"],
                "dissenter": values["dissenter"],
            }
            for segment, values in grouped.items()
        ]
        rows.sort(key=lambda row: row["dissenter"], reverse=True)
        return rows

    def _build_v2_recommendations(self, demographic_breakdown: list[dict[str, Any]], dissenting_views: list[str]) -> list[str]:
        recommendations: list[str] = []
        if demographic_breakdown:
            top = demographic_breakdown[0]
            recommendations.append(
                f"Prioritize communication and safeguards for {top.get('segment', 'top dissent segment')} to reduce concentrated dissent."
            )
        if dissenting_views:
            recommendations.append("Address recurring affordability concerns directly with concrete implementation details.")
        if not recommendations:
            recommendations.append("Maintain transparent rollout updates and monitor stance movement each round.")
        return recommendations[:5]

    def _build_v2_executive_summary(
        self,
        *,
        simulation_id: str,
        initial_metric: float,
        final_metric: float,
        round_count: int,
        supporting_views: list[str],
        dissenting_views: list[str],
    ) -> str:
        prompt = (
            f"Simulation {simulation_id}. Approval moved from {initial_metric} to {final_metric} "
            f"over {round_count} rounds.\n"
            f"Supporting themes: {supporting_views[:3]}\n"
            f"Dissenting themes: {dissenting_views[:3]}\n"
            "Write a concise executive summary in 3-4 sentences."
        )
        try:
            return self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")
        except Exception:  # noqa: BLE001
            direction = "declined" if final_metric < initial_metric else "improved"
            return (
                f"Across {round_count} rounds, overall approval {direction} from {initial_metric} to {final_metric}. "
                "Observed interactions show concentrated disagreement around affordability and rollout fairness."
            )

    def _recommend(
        self,
        simulation_id: str,
        top_dissenting: list[dict[str, Any]],
        income_metrics: list[dict[str, Any]],
        arguments_for: list[dict[str, Any]],
        arguments_against: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not top_dissenting:
            return [
                {
                    "title": "Maintain broad-based communication cadence",
                    "rationale": "No major friction clusters detected in planning-area analysis.",
                    "target_demographic": "All cohorts",
                    "expected_impact": "Medium",
                    "execution_plan": [
                        "Keep monthly policy updates with simple impact examples.",
                        "Run sentiment pulse checks by demographic cohorts.",
                    ],
                    "confidence": 0.62,
                }
            ]

        prompt = (
            "Generate 5 concrete policy communication/mitigation recommendations in JSON. "
            "Use ONLY this schema: "
            "[{\"title\": str, \"rationale\": str, \"target_demographic\": str, "
            "\"expected_impact\": str, \"execution_plan\": [str, str, str], \"confidence\": number}]\n"
            f"simulation_id={simulation_id}\n"
            f"top_dissenting={top_dissenting[:6]}\n"
            f"income_metrics={sorted(income_metrics, key=lambda x: x['approval_post'])[:6]}\n"
            f"arguments_for={arguments_for[:6]}\n"
            f"arguments_against={arguments_against[:6]}\n"
            "Rules: recommendations must be specific, non-generic, and tied to at least one planning area or cohort. "
            "confidence must be between 0 and 1."
        )

        raw = self.llm.complete_required(
            prompt=prompt,
            system_prompt="You are McKAInsey ReportAgent. Return valid JSON only.",
        )
        parsed = self._parse_recommendations(raw)
        if parsed:
            return parsed
        raise RuntimeError("Report recommendation generation failed because the model did not return valid JSON.")

    def _parse_recommendations(self, raw: str) -> list[dict[str, Any]]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        out: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            rationale = str(item.get("rationale", "")).strip()
            target = str(item.get("target_demographic", "")).strip()
            impact = str(item.get("expected_impact", "")).strip()
            plan = item.get("execution_plan", [])
            try:
                conf = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5

            if not title or not rationale or not target:
                continue

            plan_list = [str(x).strip() for x in plan if str(x).strip()]
            if len(plan_list) < 2:
                plan_list = [
                    "Run targeted messaging sessions with affected households.",
                    "Track sentiment changes weekly and refine intervention messaging.",
                ]

            out.append(
                {
                    "title": title,
                    "rationale": rationale,
                    "target_demographic": target,
                    "expected_impact": impact or "Medium",
                    "execution_plan": plan_list[:4],
                    "confidence": max(0.0, min(1.0, round(conf, 2))),
                }
            )

        return out[:6]

    def _algorithmic_recommendations(
        self,
        top_dissenting: list[dict[str, Any]],
        income_metrics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        low_income = sorted(income_metrics, key=lambda x: x["approval_post"])[:2]

        for item in top_dissenting[:4]:
            area = item["planning_area"]
            friction = float(item.get("friction_index", 0.0))
            target_income = low_income[0]["income_bracket"] if low_income else "Lower-income households"
            confidence = 0.55 + min(0.35, friction)
            recommendations.append(
                {
                    "title": f"Targeted affordability mitigation for {area}",
                    "rationale": (
                        f"{area} shows elevated friction ({friction:.2f}) with below-target post approval "
                        f"({item.get('approval_post', 0):.2f})."
                    ),
                    "target_demographic": f"{area} residents, especially {target_income}",
                    "expected_impact": "High" if friction >= 0.3 else "Medium",
                    "execution_plan": [
                        f"Deploy area-specific budget explainers in {area} community channels.",
                        "Add concrete household cashflow examples for affected segments.",
                        "Collect 2-week feedback pulse and adjust subsidy messaging.",
                    ],
                    "confidence": round(min(0.95, confidence), 2),
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "title": "Cross-cohort message calibration",
                    "rationale": "No sharply concentrated friction cluster was detected.",
                    "target_demographic": "Multi-cohort",
                    "expected_impact": "Medium",
                    "execution_plan": [
                        "Segment messages by age and income before public rollout.",
                        "Prioritize FAQs around transport and cost-of-living concerns.",
                    ],
                    "confidence": 0.6,
                }
            )

        return recommendations[:6]

    def _build_structured_report_prompt(
        self,
        *,
        simulation_id: str,
        use_case: str | None,
        knowledge: dict[str, Any],
        population: dict[str, Any],
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> str:
        config_lines: list[str] = []
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                use_case_payload = config_service.get_use_case(use_case)
            except Exception:  # noqa: BLE001
                use_case_payload = {}
            guiding_prompt = str(use_case_payload.get("guiding_prompt") or "").strip()
            if guiding_prompt:
                config_lines.append("Use-case guiding prompt:")
                config_lines.append(guiding_prompt)
            report_sections = [
                item
                for item in use_case_payload.get("report_sections", [])
                if isinstance(item, dict)
            ]
            if report_sections:
                config_lines.append("Report sections from config:")
                for index, section in enumerate(report_sections, start=1):
                    title = str(section.get("title") or "").strip()
                    prompt = str(section.get("prompt") or "").strip()
                    if title or prompt:
                        config_lines.append(f"{index}. {title}: {prompt}".strip())
        influential_posts = [
            {
                "agent_id": row.get("actor_agent_id"),
                "content": row.get("content"),
                "delta": row.get("delta"),
            }
            for row in interactions
            if row.get("action_type") == "create_post"
        ][:12]
        checkpoints = {
            "baseline": baseline[:50],
            "final": final[:50],
        }
        prompt_lines = [
            "Generate a fixed-format policy simulation report in JSON.",
            "Return an object with exactly these top-level keys:",
            "{\"generated_at\": str, \"executive_summary\": str, "
            "\"insight_cards\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}], "
            "\"support_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"dissent_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"demographic_breakdown\": [{\"segment\": str, \"approval_rate\": number, \"dissent_rate\": number, \"sample_size\": number}], "
            "\"influential_content\": [{\"content_type\": str, \"author_agent_id\": str, \"summary\": str, \"engagement_score\": number}], "
            "\"recommendations\": [{\"title\": str, \"rationale\": str, \"priority\": \"high|medium|low\"}], "
            "\"risks\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}]}",
            "",
        ]
        if config_lines:
            prompt_lines.extend(config_lines)
            prompt_lines.append("")
        prompt_lines.extend(
            [
                f"Simulation ID: {simulation_id}",
                f"Knowledge summary: {knowledge.get('summary', '')}",
                f"Population artifact: {json.dumps(population, ensure_ascii=False)[:6000]}",
                f"Checkpoint records: {json.dumps(checkpoints, ensure_ascii=False)[:12000]}",
                f"Influential posts: {json.dumps(influential_posts, ensure_ascii=False)[:6000]}",
                f"Recent simulation events: {json.dumps(events[-80:], ensure_ascii=False)[:12000]}",
                f"Agent records: {json.dumps(agents[:80], ensure_ascii=False)[:12000]}",
            ]
        )
        return "\n".join(prompt_lines)

    def _normalize_structured_report_payload(self, simulation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        generated_at = str(payload.get("generated_at") or datetime.now(UTC).isoformat())
        normalized = {
            "session_id": simulation_id,
            "status": "completed",
            "generated_at": generated_at,
            "executive_summary": str(payload.get("executive_summary", "")).strip(),
            "insight_cards": _normalize_dict_list(payload.get("insight_cards"), required_keys=("title", "summary", "severity")),
            "support_themes": _normalize_dict_list(payload.get("support_themes"), required_keys=("theme", "summary", "evidence")),
            "dissent_themes": _normalize_dict_list(payload.get("dissent_themes"), required_keys=("theme", "summary", "evidence")),
            "demographic_breakdown": _normalize_dict_list(payload.get("demographic_breakdown"), required_keys=("segment", "approval_rate", "dissent_rate", "sample_size")),
            "influential_content": _normalize_dict_list(payload.get("influential_content"), required_keys=("content_type", "author_agent_id", "summary", "engagement_score")),
            "recommendations": _normalize_dict_list(payload.get("recommendations"), required_keys=("title", "rationale", "priority")),
            "risks": _normalize_dict_list(payload.get("risks"), required_keys=("title", "summary", "severity")),
        }
        return normalized

    def _enrich_structured_report_payload(
        self,
        simulation_id: str,
        payload: dict[str, Any],
        *,
        use_case: str | None,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
        knowledge: dict[str, Any],
        population: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(payload)
        pre_scores = [float(agent.get("opinion_pre", 5.0) or 5.0) for agent in agents]
        post_scores = [float(agent.get("opinion_post", 5.0) or 5.0) for agent in agents]
        approval_pre = _approval(pre_scores)
        approval_post = _approval(post_scores)

        supportive_rows = self._rank_interactions(interactions, positive=True)
        dissent_rows = self._rank_interactions(interactions, positive=False)
        demographic_breakdown = enriched.get("demographic_breakdown") or self._build_demographic_breakdown(agents)

        if not enriched["executive_summary"]:
            enriched["executive_summary"] = self._build_structured_executive_summary(
                simulation_id=simulation_id,
                use_case=use_case,
                demographic_breakdown=demographic_breakdown,
                supportive_rows=supportive_rows,
                dissent_rows=dissent_rows,
                approval_pre=approval_pre,
                approval_post=approval_post,
            )

        if not enriched["insight_cards"]:
            top_segment = str(demographic_breakdown[0].get("segment", "top cohort")) if demographic_breakdown else "top cohort"
            card_summary = (
                f"{top_segment} carried the strongest signal in the simulation, "
                f"with approval moving from {approval_pre:.2f} to {approval_post:.2f} across the run."
            )
            enriched["insight_cards"] = [
                {
                    "title": f"{top_segment} drove the clearest shift",
                    "summary": card_summary,
                    "severity": "high" if abs(approval_post - approval_pre) >= 0.15 else "medium",
                }
            ]
            if supportive_rows:
                first_support = supportive_rows[0]
                enriched["insight_cards"].append(
                    {
                        "title": "Most persuasive support argument",
                        "summary": str(first_support["content"])[:240],
                        "severity": "medium",
                    }
                )
            if dissent_rows:
                first_dissent = dissent_rows[0]
                enriched["insight_cards"].append(
                    {
                        "title": "Main dissent pressure point",
                        "summary": str(first_dissent["content"])[:240],
                        "severity": "medium",
                    }
                )

        if not enriched["support_themes"]:
            enriched["support_themes"] = self._build_theme_items(
                supportive_rows,
                theme_label="support",
                fallback_summary="Support centered on concrete benefits and targeted help.",
            )

        if not enriched["dissent_themes"]:
            enriched["dissent_themes"] = self._build_theme_items(
                dissent_rows,
                theme_label="dissent",
                fallback_summary="Dissent clustered around affordability, fairness, or implementation risk.",
            )

        if not enriched["demographic_breakdown"]:
            enriched["demographic_breakdown"] = demographic_breakdown

        if not enriched["influential_content"]:
            enriched["influential_content"] = self._build_influential_content(interactions)

        if not enriched["recommendations"]:
            enriched["recommendations"] = self._build_structured_recommendations(
                simulation_id=simulation_id,
                demographic_breakdown=demographic_breakdown,
                dissent_rows=dissent_rows,
                supportive_rows=supportive_rows,
                knowledge=knowledge,
                population=population,
                use_case=use_case,
                baseline=baseline,
                final=final,
                events=events,
            )

        if not enriched["risks"]:
            enriched["risks"] = self._build_structured_risks(
                demographic_breakdown=demographic_breakdown,
                dissent_rows=dissent_rows,
                events=events,
            )

        return enriched

    def _rank_interactions(self, interactions: list[dict[str, Any]], *, positive: bool) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in interactions:
            try:
                delta = float(item.get("delta", 0.0) or 0.0)
            except (TypeError, ValueError):
                delta = 0.0
            if positive and delta <= 0:
                continue
            if not positive and delta >= 0:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            rows.append(
                {
                    "content": content,
                    "agent_id": str(item.get("actor_agent_id", "")),
                    "round_no": int(item.get("round_no", 0) or 0),
                    "delta": delta,
                    "likes": float(item.get("likes", 0) or 0),
                    "dislikes": float(item.get("dislikes", 0) or 0),
                }
            )
        rows.sort(key=lambda row: (abs(row["delta"]), row["likes"] + row["dislikes"]), reverse=True)
        return rows[:6]

    def _build_theme_items(
        self,
        rows: list[dict[str, Any]],
        *,
        theme_label: str,
        fallback_summary: str,
    ) -> list[dict[str, Any]]:
        if not rows:
            return [
                {
                    "theme": theme_label,
                    "summary": fallback_summary,
                    "evidence": [],
                }
            ]
        items: list[dict[str, Any]] = []
        for row in rows[:3]:
            summary = f"{row['content'][:180]}"
            items.append(
                {
                    "theme": theme_label,
                    "summary": summary,
                    "evidence": [row["content"]],
                }
            )
        return items

    def _build_influential_content(self, interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in interactions:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            try:
                delta = abs(float(item.get("delta", 0.0) or 0.0))
            except (TypeError, ValueError):
                delta = 0.0
            try:
                likes = float(item.get("likes", 0) or 0)
            except (TypeError, ValueError):
                likes = 0.0
            try:
                dislikes = float(item.get("dislikes", 0) or 0)
            except (TypeError, ValueError):
                dislikes = 0.0
            engagement_score = round(delta * 10 + likes + dislikes, 2)
            rows.append(
                {
                    "content_type": str(item.get("action_type") or item.get("type") or "post"),
                    "author_agent_id": str(item.get("actor_agent_id", "")),
                    "summary": content[:240],
                    "engagement_score": engagement_score,
                }
            )
        rows.sort(key=lambda row: row["engagement_score"], reverse=True)
        return rows[:6]

    def _build_structured_recommendations(
        self,
        *,
        simulation_id: str,
        demographic_breakdown: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        supportive_rows: list[dict[str, Any]],
        knowledge: dict[str, Any],
        population: dict[str, Any],
        use_case: str | None,
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        top_segment = str(demographic_breakdown[0].get("segment", "All cohorts")) if demographic_breakdown else "All cohorts"
        top_dissent = dissent_rows[0]["content"] if dissent_rows else "review implementation gaps"
        support_context = supportive_rows[0]["content"] if supportive_rows else str(knowledge.get("summary", "")).strip()
        base_label = use_case or str(population.get("use_case") or "simulation")
        return [
            {
                "title": f"Address the main friction in {top_segment}",
                "rationale": f"Dissent in {top_segment} is the clearest signal to act on first.",
                "priority": "high",
            },
            {
                "title": f"Turn the strongest support into a clearer message for {base_label}",
                "rationale": support_context[:240] or "Support needs to be translated into a more concrete narrative.",
                "priority": "medium",
            },
            {
                "title": "Use round-by-round evidence to close credibility gaps",
                "rationale": top_dissent[:240] if top_dissent else "Agents responded to concrete examples more than abstract assurances.",
                "priority": "medium",
            },
        ]

    def _build_structured_risks(
        self,
        *,
        demographic_breakdown: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        if demographic_breakdown:
            top = demographic_breakdown[0]
            risks.append(
                {
                    "title": f"Concentrated dissent in {top.get('segment', 'a key cohort')}",
                    "summary": (
                        f"{top.get('segment', 'A cohort')} has {top.get('dissent_rate', 0)} dissent rate "
                        f"across {top.get('sample_size', 0)} agents."
                    ),
                    "severity": "high" if float(top.get("dissent_rate", 0) or 0) >= 0.3 else "medium",
                }
            )
        if dissent_rows:
            risks.append(
                {
                    "title": "Recurring objection pattern",
                    "summary": dissent_rows[0]["content"][:240],
                    "severity": "medium",
                }
            )
        if events:
            risks.append(
                {
                    "title": "Conversation may be dominated by the most active agents",
                    "summary": "Event logs show the report is driven by a small set of highly visible posts.",
                    "severity": "low",
                }
            )
        return risks[:4]

    def _build_structured_executive_summary(
        self,
        *,
        simulation_id: str,
        use_case: str | None,
        demographic_breakdown: list[dict[str, Any]],
        supportive_rows: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        approval_pre: float,
        approval_post: float,
    ) -> str:
        top_segment = str(demographic_breakdown[0].get("segment", "the main cohort")) if demographic_breakdown else "the main cohort"
        support_excerpt = supportive_rows[0]["content"][:140] if supportive_rows else "support stayed concentrated in a few concrete arguments"
        dissent_excerpt = dissent_rows[0]["content"][:140] if dissent_rows else "dissent stayed centered on implementation risk"
        direction = "improved" if approval_post >= approval_pre else "softened"
        use_case_label = f"for {use_case}" if use_case else "for the simulation"
        return (
            f"Across {use_case_label}, approval {direction} from {approval_pre:.2f} to {approval_post:.2f}. "
            f"{top_segment} was the clearest cohort signal in the run, with support anchored by '{support_excerpt}' "
            f"and dissent concentrated around '{dissent_excerpt}'. "
            "The report sections point to a need for sharper mitigation and clearer rollout messaging."
        )


def _approval(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return len([s for s in scores if s >= 7]) / len(scores)


def _mean(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _parse_json_object(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def _normalize_dict_list(value: Any, *, required_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append({key: item.get(key) for key in required_keys})
    return normalized
===
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import io
import json
from typing import Any

from docx import Document

from mckainsey.config import Settings
from mckainsey.services.config_service import ConfigService
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.memory_service import MemoryService
from mckainsey.services.storage import SimulationStore


class ReportService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        self.memory = MemoryService(settings)

    def generate_structured_report(self, simulation_id: str, use_case: str | None = None) -> dict[str, Any]:
        existing = self.store.get_report_state(simulation_id)
        if existing and existing.get("status") == "completed":
            return existing

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        knowledge = self.store.get_knowledge_artifact(simulation_id) or {}
        population = self.store.get_population_artifact(simulation_id) or {}
        baseline = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="baseline")
        final = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="final")
        events = self.store.list_simulation_events(simulation_id)

        payload: dict[str, Any] = {}
        if self._should_request_structured_report_seed():
            prompt = self._build_structured_report_prompt(
                simulation_id=simulation_id,
                use_case=use_case,
                knowledge=knowledge,
                population=population,
                agents=agents,
                interactions=interactions,
                baseline=baseline,
                final=final,
                events=events,
            )
            try:
                raw = self.llm.complete_required(
                    prompt,
                    system_prompt=(
                        "You are McKAInsey ReportAgent. Return valid JSON only using the requested schema. "
                        "Every claim must be grounded in provided evidence."
                    ),
                )
            except Exception:  # noqa: BLE001
                raw = ""
            try:
                parsed_payload = _parse_json_object(raw) if raw else {}
            except Exception:  # noqa: BLE001
                parsed_payload = {}
            if isinstance(parsed_payload, dict):
                payload = parsed_payload

        normalized = self._normalize_structured_report_payload(simulation_id, payload)
        return self._enrich_structured_report_payload(
            simulation_id,
            normalized,
            use_case=use_case,
            agents=agents,
            interactions=interactions,
            baseline=baseline,
            final=final,
            events=events,
            knowledge=knowledge,
            population=population,
        )

    def _should_request_structured_report_seed(self) -> bool:
        # Local Ollama models have been the slowest and least reliable source of
        # large JSON objects in live mode. We still build a report from the real
        # simulation artifacts, but skip the heavyweight seed request here.
        return self.llm.provider != "ollama"

    def build_report(self, simulation_id: str) -> dict[str, Any]:
        cached = self.store.get_cached_report(simulation_id)
        if cached:
            return cached

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        pre = [float(a["opinion_pre"]) for a in agents]
        post = [float(a["opinion_post"]) for a in agents]

        by_area_pre: dict[str, list[float]] = defaultdict(list)
        by_area_post: dict[str, list[float]] = defaultdict(list)
        by_income_post: dict[str, list[float]] = defaultdict(list)
        influence: dict[str, float] = defaultdict(float)
        agent_persona: dict[str, dict[str, Any]] = {}
        for a in agents:
            area = str(a["persona"].get("planning_area", "Unknown"))
            income = str(a["persona"].get("income_bracket", "Unknown"))
            by_area_pre[area].append(float(a["opinion_pre"]))
            by_area_post[area].append(float(a["opinion_post"]))
            by_income_post[income].append(float(a["opinion_post"]))
            agent_persona[a["agent_id"]] = a["persona"]

        for i in interactions:
            if i.get("target_agent_id"):
                influence[i["actor_agent_id"]] += abs(float(i.get("delta", 0)))

        last_reason_by_agent: dict[str, str] = {}
        for i in interactions:
            text = str(i.get("content", "")).strip()
            if text:
                last_reason_by_agent[i["actor_agent_id"]] = text[:240]

        influential_agents: list[dict[str, Any]] = []
        for agent_id, score in sorted(influence.items(), key=lambda x: x[1], reverse=True)[:10]:
            persona = agent_persona.get(agent_id, {})
            influential_agents.append(
                {
                    "agent_id": agent_id,
                    "influence_score": round(score, 4),
                    "planning_area": str(persona.get("planning_area", "Unknown")),
                    "occupation": str(persona.get("occupation", "Unknown")),
                    "income_bracket": str(persona.get("income_bracket", "Unknown")),
                    "latest_argument": last_reason_by_agent.get(agent_id, "No recent argument captured."),
                }
            )

        area_metrics: list[dict[str, Any]] = []
        for area, post_scores in by_area_post.items():
            pre_scores = by_area_pre.get(area, [])
            post_mean = _mean(post_scores)
            pre_mean = _mean(pre_scores)
            approval_post = _approval(post_scores)
            mean_shift = post_mean - pre_mean
            friction = abs(mean_shift) * (1 - approval_post)
            area_metrics.append(
                {
                    "planning_area": area,
                    "avg_pre_opinion": round(pre_mean, 4),
                    "avg_post_opinion": round(post_mean, 4),
                    "approval_post": round(approval_post, 4),
                    "mean_shift": round(mean_shift, 4),
                    "friction_index": round(friction, 4),
                    "cohort_size": len(post_scores),
                }
            )

        top_dissenting = sorted(
            area_metrics,
            key=lambda x: (x["approval_post"], -x["friction_index"]),
        )[:8]

        income_metrics = [
            {
                "income_bracket": income,
                "approval_post": round(_approval(scores), 4),
                "avg_post_opinion": round(_mean(scores), 4),
                "cohort_size": len(scores),
            }
            for income, scores in by_income_post.items()
        ]

        arguments_for = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
                "strength": round(abs(float(i.get("delta", 0))), 4),
            }
            for i in interactions
            if float(i.get("delta", 0)) > 0
        ]
        arguments_for = sorted(arguments_for, key=lambda x: x["strength"], reverse=True)[:12]

        arguments_against = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
                "strength": round(abs(float(i.get("delta", 0))), 4),
            }
            for i in interactions
            if float(i.get("delta", 0)) < 0
        ]
        arguments_against = sorted(arguments_against, key=lambda x: x["strength"], reverse=True)[:12]

        executive_summary = self.llm.complete(
            prompt=(
                f"Generate a concise executive summary for simulation {simulation_id}. "
                f"Pre approval={_approval(pre):.2f}, post approval={_approval(post):.2f}, "
                f"net shift={_mean(post)-_mean(pre):.2f}. "
                f"Top dissent cohorts={top_dissenting[:3]}."
            ),
            system_prompt="You are ReportAgent. Return concise strategic summary.",
        )

        recommendations = self._recommend(
            simulation_id=simulation_id,
            top_dissenting=top_dissenting,
            income_metrics=income_metrics,
            arguments_for=arguments_for,
            arguments_against=arguments_against,
        )

        report = {
            "simulation_id": simulation_id,
            "executive_summary": executive_summary,
            "approval_rates": {
                "stage3a": round(_approval(pre), 4),
                "stage3b": round(_approval(post), 4),
                "delta": round(_approval(post) - _approval(pre), 4),
            },
            "top_dissenting_demographics": top_dissenting,
            "friction_by_planning_area": sorted(area_metrics, key=lambda x: x["friction_index"], reverse=True),
            "income_cohorts": sorted(income_metrics, key=lambda x: x["approval_post"]),
            "influential_agents": influential_agents,
            "key_arguments_for": arguments_for,
            "key_arguments_against": arguments_against,
            "recommendations": recommendations,
        }

        self.store.cache_report(simulation_id, report)
        return report

    def report_chat(self, simulation_id: str, message: str) -> str:
        report = self.build_report(simulation_id)
        prompt = (
            f"Report JSON:\n{report}\n\n"
            f"User asks: {message}\n"
            "Provide a direct, data-grounded answer with concrete cohort references."
        )
        return self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")

    def report_chat_payload(self, simulation_id: str, message: str) -> dict[str, Any]:
        report = self.build_report(simulation_id)
        zep_context = self.memory.search_simulation_context(simulation_id, message, limit=8)
        zep_excerpt = "\n".join(
            f"- {item['content']}"
            for item in zep_context["episodes"][:6]
        )
        prompt = (
            f"Report JSON:\n{report}\n\n"
            f"Relevant Zep Cloud memory search results:\n{zep_excerpt or '- none'}\n\n"
            f"User asks: {message}\n"
            "Provide a direct, data-grounded answer with concrete cohort references."
        )
        response = self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "response": response,
            "model_provider": self.llm.provider,
            "model_name": self.llm.model_name,
            "gemini_model": self.llm.model_name,
            "zep_context_used": zep_context["zep_context_used"],
        }

    def build_v2_report(self, simulation_id: str, use_case: str | None = None) -> dict[str, Any]:
        from mckainsey.services.metrics_service import MetricsService

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        config_service = ConfigService(self.settings)
        metrics_service = MetricsService(config_service)

        # Resolve analysis questions and metadata
        analysis_questions = self._resolve_analysis_questions(use_case)
        insight_block_configs = self._resolve_insight_blocks(use_case)
        preset_section_configs = self._resolve_preset_sections(use_case)

        round_count = max((int(item.get("round_no", 0) or 0) for item in interactions), default=0)
        evidence_pool = self._extract_evidence(interactions)

        # ── Metric deltas for quantitative questions ──
        baseline_records = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="baseline")
        final_records = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="final")
        metric_deltas: list[dict[str, Any]] = []
        for q in analysis_questions:
            if q.get("type") == "open-ended":
                continue
            name = q.get("metric_name", "")
            if not name:
                continue
            field = f"checkpoint_{name}"
            # Compute R1 and final values
            r1_agents = self._agents_from_checkpoint(baseline_records) or agents
            final_agents = self._agents_from_checkpoint(final_records) or agents
            r1_val = self._compute_metric_value(q, r1_agents)
            final_val = self._compute_metric_value(q, final_agents)
            metric_deltas.append({
                "metric_name": name,
                "metric_label": q.get("metric_label", name),
                "metric_unit": q.get("metric_unit", "/10"),
                "initial_value": r1_val,
                "final_value": final_val,
                "delta": round(final_val - r1_val, 2),
                "direction": "up" if final_val > r1_val else ("down" if final_val < r1_val else "flat"),
                "report_title": q.get("report_title", name),
            })

        # ── Build report sections from analysis questions ──
        sections: list[dict[str, Any]] = []
        for q in analysis_questions:
            question_text = q.get("question", "")
            q_type = q.get("type", "scale")
            answer = self._answer_guiding_question(simulation_id, question_text, agents, interactions)

            section: dict[str, Any] = {
                "question": question_text,
                "report_title": q.get("report_title", question_text[:60]),
                "type": q_type,
                "answer": answer,
                "evidence": evidence_pool[:3],
            }

            # Add metric spotlight for quantitative questions
            if q_type != "open-ended":
                delta_entry = next((d for d in metric_deltas if d["metric_name"] == q.get("metric_name")), None)
                if delta_entry:
                    section["metric"] = delta_entry

            sections.append(section)

        # ── Compute insight blocks ──
        insight_blocks: list[dict[str, Any]] = []
        for block_cfg in insight_block_configs:
            block_type = block_cfg.get("type", "")
            result = metrics_service.compute_insight_block(
                block_type=block_type,
                agents=agents,
                interactions=interactions,
                analysis_questions=analysis_questions,
                metric_ref=block_cfg.get("metric_ref"),
                count=block_cfg.get("count", 5),
            )
            insight_blocks.append({
                "type": block_type,
                "title": block_cfg.get("title", block_type),
                "description": block_cfg.get("description", ""),
                "data": result,
            })

        # ── Generate preset sections via LLM ──
        preset_sections: list[dict[str, Any]] = []
        for preset in preset_section_configs:
            title = preset.get("title", "")
            prompt = preset.get("prompt", "")
            if prompt:
                answer = self._answer_guiding_question(simulation_id, prompt, agents, interactions)
            else:
                answer = ""
            preset_sections.append({"title": title, "answer": answer})

        # ── Executive summary ──
        executive_summary = self._build_v2_executive_summary_from_metrics(
            simulation_id=simulation_id,
            metric_deltas=metric_deltas,
            round_count=round_count,
            agent_count=len(agents),
        )

        return {
            "session_id": simulation_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "executive_summary": executive_summary,
            "metric_deltas": metric_deltas,
            "quick_stats": {
                "agent_count": len(agents),
                "round_count": round_count,
                "model": self.llm.model_name,
                "provider": self.llm.provider,
            },
            "sections": sections,
            "insight_blocks": insight_blocks,
            "preset_sections": preset_sections,
        }

    def export_v2_report_docx(self, simulation_id: str, report: dict[str, Any] | None = None, use_case: str | None = None) -> bytes:
        payload = report or self.build_v2_report(simulation_id, use_case=use_case)
        document = Document()
        document.add_heading("McKAInsey Analysis Report", level=0)
        document.add_paragraph(f"Session: {payload.get('session_id', simulation_id)}")
        document.add_paragraph(f"Generated: {payload.get('generated_at', '')}")

        document.add_heading("Executive Summary", level=1)
        document.add_paragraph(str(payload.get("executive_summary", "")))

        quick_stats = payload.get("quick_stats", {})
        if isinstance(quick_stats, dict):
            document.add_heading("Quick Stats", level=1)
            document.add_paragraph(
                f"{quick_stats.get('metric_label', 'Metric')}: "
                f"{quick_stats.get('initial_metric_value', 0)} -> {quick_stats.get('final_metric_value', 0)}"
            )
            document.add_paragraph(
                f"Agents: {quick_stats.get('agent_count', 0)} | Rounds: {quick_stats.get('round_count', 0)}"
            )

        document.add_heading("Guiding Prompt Sections", level=1)
        for section in payload.get("sections", []):
            if not isinstance(section, dict):
                continue
            document.add_heading(str(section.get("question", "Section")), level=2)
            document.add_paragraph(str(section.get("answer", "")))
            evidence = section.get("evidence", [])
            if isinstance(evidence, list) and evidence:
                document.add_paragraph("Evidence:")
                for item in evidence:
                    if isinstance(item, dict):
                        quote = str(item.get("quote", "")).strip()
                        agent_id = str(item.get("agent_id", ""))
                        post_id = str(item.get("post_id", ""))
                        document.add_paragraph(
                            f"{agent_id} / {post_id}: {quote}",
                            style="List Bullet",
                        )

        document.add_heading("Supporting Views", level=1)
        for text in payload.get("supporting_views", []):
            document.add_paragraph(str(text), style="List Bullet")

        document.add_heading("Dissenting Views", level=1)
        for text in payload.get("dissenting_views", []):
            document.add_paragraph(str(text), style="List Bullet")

        demographic_rows = payload.get("demographic_breakdown", [])
        if isinstance(demographic_rows, list) and demographic_rows:
            document.add_heading("Demographic Breakdown", level=1)
            table = document.add_table(rows=1, cols=4)
            header = table.rows[0].cells
            header[0].text = "Segment"
            header[1].text = "Supporter"
            header[2].text = "Neutral"
            header[3].text = "Dissenter"
            for row in demographic_rows:
                if not isinstance(row, dict):
                    continue
                cells = table.add_row().cells
                cells[0].text = str(row.get("segment", ""))
                cells[1].text = str(row.get("supporter", 0))
                cells[2].text = str(row.get("neutral", 0))
                cells[3].text = str(row.get("dissenter", 0))

        document.add_heading("Key Recommendations", level=1)
        for item in payload.get("key_recommendations", []):
            document.add_paragraph(str(item), style="List Bullet")

        methodology = payload.get("methodology", {})
        if isinstance(methodology, dict):
            document.add_heading("Methodology", level=1)
            for key, value in methodology.items():
                document.add_paragraph(f"{key}: {value}")

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _resolve_guiding_questions(self, use_case: str | None) -> list[str]:
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                checkpoint_questions = config_service.get_checkpoint_questions(use_case)
            except Exception:  # noqa: BLE001
                checkpoint_questions = []
            checkpoint_prompts = [
                str(item.get("question", "")).strip()
                for item in checkpoint_questions
                if isinstance(item, dict) and str(item.get("question", "")).strip()
            ]
            if checkpoint_prompts:
                return checkpoint_prompts
            try:
                sections = config_service.get_report_sections(use_case)
            except Exception:  # noqa: BLE001
                sections = []
            report_prompts = [
                str(item.get("prompt") or item.get("title") or "").strip()
                for item in sections
                if isinstance(item, dict) and str(item.get("prompt") or item.get("title") or "").strip()
            ]
            if report_prompts:
                return report_prompts

        return [
            "What are the major shifts in opinion across rounds?",
            "Which arguments most strongly support the policy?",
            "Which arguments most strongly oppose the policy?",
        ]

    def _extract_evidence(self, interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for row in interactions:
            quote = str(row.get("content", "")).strip()
            if not quote:
                continue
            evidence.append(
                {
                    "agent_id": str(row.get("actor_agent_id", "")),
                    "post_id": str(row.get("post_id") or row.get("id") or ""),
                    "quote": quote[:280],
                }
            )
        return evidence

    def _answer_guiding_question(
        self,
        simulation_id: str,
        question: str,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
    ) -> str:
        prompt = (
            f"Simulation ID: {simulation_id}\n"
            f"Guiding question: {question}\n"
            f"Agent sample size: {len(agents)}\n"
            f"Recent interactions: {json.dumps(interactions[-20:], ensure_ascii=False)[:6000]}\n"
            "Respond in 2-4 sentences and reference evidence from the interactions."
        )
        try:
            return self.llm.complete_required(
                prompt,
                system_prompt="You are McKAInsey ReportAgent. Stay factual and evidence-grounded.",
            )
        except Exception:  # noqa: BLE001
            return "The available interactions indicate this question can be answered from observed cohort arguments and sentiment shifts."

    def _build_demographic_breakdown(self, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"supporter": 0, "neutral": 0, "dissenter": 0})
        for agent in agents:
            segment = str(agent.get("persona", {}).get("planning_area", "Unknown"))
            score = float(agent.get("opinion_post", 5.0) or 5.0)
            if score >= 7:
                grouped[segment]["supporter"] += 1
            elif score >= 5:
                grouped[segment]["neutral"] += 1
            else:
                grouped[segment]["dissenter"] += 1
        rows = [
            {
                "segment": segment,
                "supporter": values["supporter"],
                "neutral": values["neutral"],
                "dissenter": values["dissenter"],
            }
            for segment, values in grouped.items()
        ]
        rows.sort(key=lambda row: row["dissenter"], reverse=True)
        return rows

    def _build_v2_recommendations(self, demographic_breakdown: list[dict[str, Any]], dissenting_views: list[str]) -> list[str]:
        recommendations: list[str] = []
        if demographic_breakdown:
            top = demographic_breakdown[0]
            recommendations.append(
                f"Prioritize communication and safeguards for {top.get('segment', 'top dissent segment')} to reduce concentrated dissent."
            )
        if dissenting_views:
            recommendations.append("Address recurring affordability concerns directly with concrete implementation details.")
        if not recommendations:
            recommendations.append("Maintain transparent rollout updates and monitor stance movement each round.")
        return recommendations[:5]

    def _build_v2_executive_summary(
        self,
        *,
        simulation_id: str,
        initial_metric: float,
        final_metric: float,
        round_count: int,
        supporting_views: list[str],
        dissenting_views: list[str],
    ) -> str:
        prompt = (
            f"Simulation {simulation_id}. Approval moved from {initial_metric} to {final_metric} "
            f"over {round_count} rounds.\n"
            f"Supporting themes: {supporting_views[:3]}\n"
            f"Dissenting themes: {dissenting_views[:3]}\n"
            "Write a concise executive summary in 3-4 sentences."
        )
        try:
            return self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")
        except Exception:  # noqa: BLE001
            direction = "declined" if final_metric < initial_metric else "improved"
            return (
                f"Across {round_count} rounds, overall approval {direction} from {initial_metric} to {final_metric}. "
                "Observed interactions show concentrated disagreement around affordability and rollout fairness."
            )

    # ── New V2 helper methods ──

    def _resolve_analysis_questions(self, use_case: str | None) -> list[dict[str, Any]]:
        """Resolve analysis questions from the config YAML for the given use case."""
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                questions = config_service.get_analysis_questions(use_case)
                if questions:
                    return questions
            except Exception:  # noqa: BLE001
                pass
        # Fallback to generic questions
        return [
            {
                "question": "What are the major shifts in opinion across rounds?",
                "type": "open-ended",
                "metric_name": "opinion_shifts",
                "report_title": "Opinion Shifts",
                "tooltip": "Qualitative analysis of opinion changes.",
            },
        ]

    def _resolve_insight_blocks(self, use_case: str | None) -> list[dict[str, Any]]:
        """Resolve insight block configs from the use-case YAML."""
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                return config_service.get_insight_blocks(use_case)
            except Exception:  # noqa: BLE001
                pass
        return []

    def _resolve_preset_sections(self, use_case: str | None) -> list[dict[str, Any]]:
        """Resolve preset section configs from the use-case YAML."""
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                return config_service.get_preset_sections(use_case)
            except Exception:  # noqa: BLE001
                pass
        return [{"title": "Recommendations", "prompt": "Provide key recommendations based on the simulation results."}]

    def _agents_from_checkpoint(self, checkpoint_records: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Convert checkpoint records into agent-like dicts for metric computation."""
        if not checkpoint_records:
            return None
        return checkpoint_records

    def _compute_metric_value(self, question: dict[str, Any], agents: list[dict[str, Any]]) -> float:
        """Compute a single metric value for one analysis question across agents."""
        name = question.get("metric_name", "")
        field = f"checkpoint_{name}"
        q_type = question.get("type", "scale")
        total = max(len(agents), 1)

        if q_type == "scale":
            scores = [float(a.get(field, a.get("opinion_post", 5.0)) or 5.0) for a in agents]
            if "threshold" in question:
                threshold = float(question.get("threshold", 7))
                pct = sum(1 for s in scores if s >= threshold) / total * 100
                return round(pct, 1)
            return round(sum(scores) / len(scores) if scores else 0.0, 1)
        elif q_type == "yes-no":
            yes_count = sum(1 for a in agents if str(a.get(field, "")).strip().lower() in {"yes", "y"})
            return round(yes_count / total * 100, 1)
        return 0.0

    def _build_v2_executive_summary_from_metrics(
        self,
        *,
        simulation_id: str,
        metric_deltas: list[dict[str, Any]],
        round_count: int,
        agent_count: int,
    ) -> str:
        """Build executive summary using metric deltas instead of raw scores."""
        if not metric_deltas:
            return f"Simulation {simulation_id} completed with {agent_count} agents over {round_count} rounds."

        metrics_summary = "; ".join(
            f"{d['metric_label']}: {d['initial_value']} → {d['final_value']} ({'+' if d['delta'] > 0 else ''}{d['delta']}{d['metric_unit']})"
            for d in metric_deltas
        )
        prompt = (
            f"Simulation {simulation_id}. {agent_count} agents over {round_count} rounds.\n"
            f"Key metrics: {metrics_summary}\n"
            "Write a concise executive summary in 3-4 sentences highlighting the most important findings."
        )
        try:
            return self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")
        except Exception:  # noqa: BLE001
            return f"Across {round_count} rounds with {agent_count} agents: {metrics_summary}."

    def _recommend(
        self,
        simulation_id: str,
        top_dissenting: list[dict[str, Any]],
        income_metrics: list[dict[str, Any]],
        arguments_for: list[dict[str, Any]],
        arguments_against: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not top_dissenting:
            return [
                {
                    "title": "Maintain broad-based communication cadence",
                    "rationale": "No major friction clusters detected in planning-area analysis.",
                    "target_demographic": "All cohorts",
                    "expected_impact": "Medium",
                    "execution_plan": [
                        "Keep monthly policy updates with simple impact examples.",
                        "Run sentiment pulse checks by demographic cohorts.",
                    ],
                    "confidence": 0.62,
                }
            ]

        prompt = (
            "Generate 5 concrete policy communication/mitigation recommendations in JSON. "
            "Use ONLY this schema: "
            "[{\"title\": str, \"rationale\": str, \"target_demographic\": str, "
            "\"expected_impact\": str, \"execution_plan\": [str, str, str], \"confidence\": number}]\n"
            f"simulation_id={simulation_id}\n"
            f"top_dissenting={top_dissenting[:6]}\n"
            f"income_metrics={sorted(income_metrics, key=lambda x: x['approval_post'])[:6]}\n"
            f"arguments_for={arguments_for[:6]}\n"
            f"arguments_against={arguments_against[:6]}\n"
            "Rules: recommendations must be specific, non-generic, and tied to at least one planning area or cohort. "
            "confidence must be between 0 and 1."
        )

        raw = self.llm.complete_required(
            prompt=prompt,
            system_prompt="You are McKAInsey ReportAgent. Return valid JSON only.",
        )
        parsed = self._parse_recommendations(raw)
        if parsed:
            return parsed
        raise RuntimeError("Report recommendation generation failed because the model did not return valid JSON.")

    def _parse_recommendations(self, raw: str) -> list[dict[str, Any]]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        out: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            rationale = str(item.get("rationale", "")).strip()
            target = str(item.get("target_demographic", "")).strip()
            impact = str(item.get("expected_impact", "")).strip()
            plan = item.get("execution_plan", [])
            try:
                conf = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5

            if not title or not rationale or not target:
                continue

            plan_list = [str(x).strip() for x in plan if str(x).strip()]
            if len(plan_list) < 2:
                plan_list = [
                    "Run targeted messaging sessions with affected households.",
                    "Track sentiment changes weekly and refine intervention messaging.",
                ]

            out.append(
                {
                    "title": title,
                    "rationale": rationale,
                    "target_demographic": target,
                    "expected_impact": impact or "Medium",
                    "execution_plan": plan_list[:4],
                    "confidence": max(0.0, min(1.0, round(conf, 2))),
                }
            )

        return out[:6]

    def _algorithmic_recommendations(
        self,
        top_dissenting: list[dict[str, Any]],
        income_metrics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        low_income = sorted(income_metrics, key=lambda x: x["approval_post"])[:2]

        for item in top_dissenting[:4]:
            area = item["planning_area"]
            friction = float(item.get("friction_index", 0.0))
            target_income = low_income[0]["income_bracket"] if low_income else "Lower-income households"
            confidence = 0.55 + min(0.35, friction)
            recommendations.append(
                {
                    "title": f"Targeted affordability mitigation for {area}",
                    "rationale": (
                        f"{area} shows elevated friction ({friction:.2f}) with below-target post approval "
                        f"({item.get('approval_post', 0):.2f})."
                    ),
                    "target_demographic": f"{area} residents, especially {target_income}",
                    "expected_impact": "High" if friction >= 0.3 else "Medium",
                    "execution_plan": [
                        f"Deploy area-specific budget explainers in {area} community channels.",
                        "Add concrete household cashflow examples for affected segments.",
                        "Collect 2-week feedback pulse and adjust subsidy messaging.",
                    ],
                    "confidence": round(min(0.95, confidence), 2),
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "title": "Cross-cohort message calibration",
                    "rationale": "No sharply concentrated friction cluster was detected.",
                    "target_demographic": "Multi-cohort",
                    "expected_impact": "Medium",
                    "execution_plan": [
                        "Segment messages by age and income before public rollout.",
                        "Prioritize FAQs around transport and cost-of-living concerns.",
                    ],
                    "confidence": 0.6,
                }
            )

        return recommendations[:6]

    def _build_structured_report_prompt(
        self,
        *,
        simulation_id: str,
        use_case: str | None,
        knowledge: dict[str, Any],
        population: dict[str, Any],
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> str:
        config_lines: list[str] = []
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                use_case_payload = config_service.get_use_case(use_case)
            except Exception:  # noqa: BLE001
                use_case_payload = {}
            guiding_prompt = str(use_case_payload.get("guiding_prompt") or "").strip()
            if guiding_prompt:
                config_lines.append("Use-case guiding prompt:")
                config_lines.append(guiding_prompt)
            report_sections = [
                item
                for item in use_case_payload.get("report_sections", [])
                if isinstance(item, dict)
            ]
            if report_sections:
                config_lines.append("Report sections from config:")
                for index, section in enumerate(report_sections, start=1):
                    title = str(section.get("title") or "").strip()
                    prompt = str(section.get("prompt") or "").strip()
                    if title or prompt:
                        config_lines.append(f"{index}. {title}: {prompt}".strip())
        influential_posts = [
            {
                "agent_id": row.get("actor_agent_id"),
                "content": row.get("content"),
                "delta": row.get("delta"),
            }
            for row in interactions
            if row.get("action_type") == "create_post"
        ][:12]
        checkpoints = {
            "baseline": baseline[:50],
            "final": final[:50],
        }
        prompt_lines = [
            "Generate a fixed-format policy simulation report in JSON.",
            "Return an object with exactly these top-level keys:",
            "{\"generated_at\": str, \"executive_summary\": str, "
            "\"insight_cards\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}], "
            "\"support_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"dissent_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"demographic_breakdown\": [{\"segment\": str, \"approval_rate\": number, \"dissent_rate\": number, \"sample_size\": number}], "
            "\"influential_content\": [{\"content_type\": str, \"author_agent_id\": str, \"summary\": str, \"engagement_score\": number}], "
            "\"recommendations\": [{\"title\": str, \"rationale\": str, \"priority\": \"high|medium|low\"}], "
            "\"risks\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}]}",
            "",
        ]
        if config_lines:
            prompt_lines.extend(config_lines)
            prompt_lines.append("")
        prompt_lines.extend(
            [
                f"Simulation ID: {simulation_id}",
                f"Knowledge summary: {knowledge.get('summary', '')}",
                f"Population artifact: {json.dumps(population, ensure_ascii=False)[:6000]}",
                f"Checkpoint records: {json.dumps(checkpoints, ensure_ascii=False)[:12000]}",
                f"Influential posts: {json.dumps(influential_posts, ensure_ascii=False)[:6000]}",
                f"Recent simulation events: {json.dumps(events[-80:], ensure_ascii=False)[:12000]}",
                f"Agent records: {json.dumps(agents[:80], ensure_ascii=False)[:12000]}",
            ]
        )
        return "\n".join(prompt_lines)

    def _normalize_structured_report_payload(self, simulation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        generated_at = str(payload.get("generated_at") or datetime.now(UTC).isoformat())
        normalized = {
            "session_id": simulation_id,
            "status": "completed",
            "generated_at": generated_at,
            "executive_summary": str(payload.get("executive_summary", "")).strip(),
            "insight_cards": _normalize_dict_list(payload.get("insight_cards"), required_keys=("title", "summary", "severity")),
            "support_themes": _normalize_dict_list(payload.get("support_themes"), required_keys=("theme", "summary", "evidence")),
            "dissent_themes": _normalize_dict_list(payload.get("dissent_themes"), required_keys=("theme", "summary", "evidence")),
            "demographic_breakdown": _normalize_dict_list(payload.get("demographic_breakdown"), required_keys=("segment", "approval_rate", "dissent_rate", "sample_size")),
            "influential_content": _normalize_dict_list(payload.get("influential_content"), required_keys=("content_type", "author_agent_id", "summary", "engagement_score")),
            "recommendations": _normalize_dict_list(payload.get("recommendations"), required_keys=("title", "rationale", "priority")),
            "risks": _normalize_dict_list(payload.get("risks"), required_keys=("title", "summary", "severity")),
        }
        return normalized

    def _enrich_structured_report_payload(
        self,
        simulation_id: str,
        payload: dict[str, Any],
        *,
        use_case: str | None,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
        knowledge: dict[str, Any],
        population: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(payload)
        pre_scores = [float(agent.get("opinion_pre", 5.0) or 5.0) for agent in agents]
        post_scores = [float(agent.get("opinion_post", 5.0) or 5.0) for agent in agents]
        approval_pre = _approval(pre_scores)
        approval_post = _approval(post_scores)

        supportive_rows = self._rank_interactions(interactions, positive=True)
        dissent_rows = self._rank_interactions(interactions, positive=False)
        demographic_breakdown = enriched.get("demographic_breakdown") or self._build_demographic_breakdown(agents)

        if not enriched["executive_summary"]:
            enriched["executive_summary"] = self._build_structured_executive_summary(
                simulation_id=simulation_id,
                use_case=use_case,
                demographic_breakdown=demographic_breakdown,
                supportive_rows=supportive_rows,
                dissent_rows=dissent_rows,
                approval_pre=approval_pre,
                approval_post=approval_post,
            )

        if not enriched["insight_cards"]:
            top_segment = str(demographic_breakdown[0].get("segment", "top cohort")) if demographic_breakdown else "top cohort"
            card_summary = (
                f"{top_segment} carried the strongest signal in the simulation, "
                f"with approval moving from {approval_pre:.2f} to {approval_post:.2f} across the run."
            )
            enriched["insight_cards"] = [
                {
                    "title": f"{top_segment} drove the clearest shift",
                    "summary": card_summary,
                    "severity": "high" if abs(approval_post - approval_pre) >= 0.15 else "medium",
                }
            ]
            if supportive_rows:
                first_support = supportive_rows[0]
                enriched["insight_cards"].append(
                    {
                        "title": "Most persuasive support argument",
                        "summary": str(first_support["content"])[:240],
                        "severity": "medium",
                    }
                )
            if dissent_rows:
                first_dissent = dissent_rows[0]
                enriched["insight_cards"].append(
                    {
                        "title": "Main dissent pressure point",
                        "summary": str(first_dissent["content"])[:240],
                        "severity": "medium",
                    }
                )

        if not enriched["support_themes"]:
            enriched["support_themes"] = self._build_theme_items(
                supportive_rows,
                theme_label="support",
                fallback_summary="Support centered on concrete benefits and targeted help.",
            )

        if not enriched["dissent_themes"]:
            enriched["dissent_themes"] = self._build_theme_items(
                dissent_rows,
                theme_label="dissent",
                fallback_summary="Dissent clustered around affordability, fairness, or implementation risk.",
            )

        if not enriched["demographic_breakdown"]:
            enriched["demographic_breakdown"] = demographic_breakdown

        if not enriched["influential_content"]:
            enriched["influential_content"] = self._build_influential_content(interactions)

        if not enriched["recommendations"]:
            enriched["recommendations"] = self._build_structured_recommendations(
                simulation_id=simulation_id,
                demographic_breakdown=demographic_breakdown,
                dissent_rows=dissent_rows,
                supportive_rows=supportive_rows,
                knowledge=knowledge,
                population=population,
                use_case=use_case,
                baseline=baseline,
                final=final,
                events=events,
            )

        if not enriched["risks"]:
            enriched["risks"] = self._build_structured_risks(
                demographic_breakdown=demographic_breakdown,
                dissent_rows=dissent_rows,
                events=events,
            )

        return enriched

    def _rank_interactions(self, interactions: list[dict[str, Any]], *, positive: bool) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in interactions:
            try:
                delta = float(item.get("delta", 0.0) or 0.0)
            except (TypeError, ValueError):
                delta = 0.0
            if positive and delta <= 0:
                continue
            if not positive and delta >= 0:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            rows.append(
                {
                    "content": content,
                    "agent_id": str(item.get("actor_agent_id", "")),
                    "round_no": int(item.get("round_no", 0) or 0),
                    "delta": delta,
                    "likes": float(item.get("likes", 0) or 0),
                    "dislikes": float(item.get("dislikes", 0) or 0),
                }
            )
        rows.sort(key=lambda row: (abs(row["delta"]), row["likes"] + row["dislikes"]), reverse=True)
        return rows[:6]

    def _build_theme_items(
        self,
        rows: list[dict[str, Any]],
        *,
        theme_label: str,
        fallback_summary: str,
    ) -> list[dict[str, Any]]:
        if not rows:
            return [
                {
                    "theme": theme_label,
                    "summary": fallback_summary,
                    "evidence": [],
                }
            ]
        items: list[dict[str, Any]] = []
        for row in rows[:3]:
            summary = f"{row['content'][:180]}"
            items.append(
                {
                    "theme": theme_label,
                    "summary": summary,
                    "evidence": [row["content"]],
                }
            )
        return items

    def _build_influential_content(self, interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in interactions:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            try:
                delta = abs(float(item.get("delta", 0.0) or 0.0))
            except (TypeError, ValueError):
                delta = 0.0
            try:
                likes = float(item.get("likes", 0) or 0)
            except (TypeError, ValueError):
                likes = 0.0
            try:
                dislikes = float(item.get("dislikes", 0) or 0)
            except (TypeError, ValueError):
                dislikes = 0.0
            engagement_score = round(delta * 10 + likes + dislikes, 2)
            rows.append(
                {
                    "content_type": str(item.get("action_type") or item.get("type") or "post"),
                    "author_agent_id": str(item.get("actor_agent_id", "")),
                    "summary": content[:240],
                    "engagement_score": engagement_score,
                }
            )
        rows.sort(key=lambda row: row["engagement_score"], reverse=True)
        return rows[:6]

    def _build_structured_recommendations(
        self,
        *,
        simulation_id: str,
        demographic_breakdown: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        supportive_rows: list[dict[str, Any]],
        knowledge: dict[str, Any],
        population: dict[str, Any],
        use_case: str | None,
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        top_segment = str(demographic_breakdown[0].get("segment", "All cohorts")) if demographic_breakdown else "All cohorts"
        top_dissent = dissent_rows[0]["content"] if dissent_rows else "review implementation gaps"
        support_context = supportive_rows[0]["content"] if supportive_rows else str(knowledge.get("summary", "")).strip()
        base_label = use_case or str(population.get("use_case") or "simulation")
        return [
            {
                "title": f"Address the main friction in {top_segment}",
                "rationale": f"Dissent in {top_segment} is the clearest signal to act on first.",
                "priority": "high",
            },
            {
                "title": f"Turn the strongest support into a clearer message for {base_label}",
                "rationale": support_context[:240] or "Support needs to be translated into a more concrete narrative.",
                "priority": "medium",
            },
            {
                "title": "Use round-by-round evidence to close credibility gaps",
                "rationale": top_dissent[:240] if top_dissent else "Agents responded to concrete examples more than abstract assurances.",
                "priority": "medium",
            },
        ]

    def _build_structured_risks(
        self,
        *,
        demographic_breakdown: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        if demographic_breakdown:
            top = demographic_breakdown[0]
            risks.append(
                {
                    "title": f"Concentrated dissent in {top.get('segment', 'a key cohort')}",
                    "summary": (
                        f"{top.get('segment', 'A cohort')} has {top.get('dissent_rate', 0)} dissent rate "
                        f"across {top.get('sample_size', 0)} agents."
                    ),
                    "severity": "high" if float(top.get("dissent_rate", 0) or 0) >= 0.3 else "medium",
                }
            )
        if dissent_rows:
            risks.append(
                {
                    "title": "Recurring objection pattern",
                    "summary": dissent_rows[0]["content"][:240],
                    "severity": "medium",
                }
            )
        if events:
            risks.append(
                {
                    "title": "Conversation may be dominated by the most active agents",
                    "summary": "Event logs show the report is driven by a small set of highly visible posts.",
                    "severity": "low",
                }
            )
        return risks[:4]

    def _build_structured_executive_summary(
        self,
        *,
        simulation_id: str,
        use_case: str | None,
        demographic_breakdown: list[dict[str, Any]],
        supportive_rows: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        approval_pre: float,
        approval_post: float,
    ) -> str:
        top_segment = str(demographic_breakdown[0].get("segment", "the main cohort")) if demographic_breakdown else "the main cohort"
        support_excerpt = supportive_rows[0]["content"][:140] if supportive_rows else "support stayed concentrated in a few concrete arguments"
        dissent_excerpt = dissent_rows[0]["content"][:140] if dissent_rows else "dissent stayed centered on implementation risk"
        direction = "improved" if approval_post >= approval_pre else "softened"
        use_case_label = f"for {use_case}" if use_case else "for the simulation"
        return (
            f"Across {use_case_label}, approval {direction} from {approval_pre:.2f} to {approval_post:.2f}. "
            f"{top_segment} was the clearest cohort signal in the run, with support anchored by '{support_excerpt}' "
            f"and dissent concentrated around '{dissent_excerpt}'. "
            "The report sections point to a need for sharper mitigation and clearer rollout messaging."
        )


def _approval(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return len([s for s in scores if s >= 7]) / len(scores)


def _mean(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _parse_json_object(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def _normalize_dict_list(value: Any, *, required_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append({key: item.get(key) for key in required_keys})
    return normalized
```

- `build_v2_report()` generates: metric deltas, analysis sections, insight blocks, preset sections, executive summary

### Routes
```diff:routes_console.py
import json
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from mckainsey.config import Settings, get_settings
from mckainsey.models.console import (
    ConsoleAgentChatRequest,
    ConsoleAgentChatResponse,
    ConsoleDynamicFiltersResponse,
    ConsoleKnowledgeProcessRequest,
    ConsoleModelProviderCatalogResponse,
    ConsoleProviderModelsResponse,
    ConsoleReportChatRequest,
    ConsoleReportChatResponse,
    ConsoleScrapeRequest,
    ConsoleScrapeResponse,
    ConsoleSessionModelConfigRequest,
    ConsoleSessionModelConfigResponse,
    ConsoleSessionCreateRequest,
    ConsoleSessionResponse,
    V2AgentChatRequest,
    V2AgentChatResponse,
    V2GroupChatRequest,
    V2GroupChatResponse,
    InteractionHubResponse,
    KnowledgeArtifactResponse,
    PopulationArtifactResponse,
    PopulationPreviewRequest,
    ReportFrictionMapResponse,
    ReportFullResponse,
    ReportOpinionsResponse,
    SimulationStartRequest,
    SimulationQuickStartRequest,
    SimulationStateResponse,
    TokenUsageEstimateResponse,
    TokenUsageRuntimeResponse,
    V2CountryResponse,
    V2ProviderResponse,
    V2ReportResponse,
    V2SessionConfigPatchRequest,
    V2SessionConfigResponse,
    V2SessionCreateRequest,
    V2SessionCreateResponse,
)
from mckainsey.services.config_service import ConfigService
from mckainsey.services.console_service import ConsoleService
from mckainsey.services.demo_service import DemoService
from mckainsey.services.scrape_service import ScrapeService
from mckainsey.services.simulation_stream_service import SimulationStreamService


router = APIRouter(prefix="/api/v2/console", tags=["console"])
compat_router = APIRouter(prefix="/api/v2", tags=["console-compat"])


def _is_demo_session(session_id: str, settings: Settings) -> bool:
    """Check if session is in demo mode."""
    from mckainsey.services.storage import SimulationStore
    store = SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    return session is not None and session.get("mode") == "demo"


def _get_demo_service(settings: Settings) -> DemoService:
    """Get demo service instance."""
    return DemoService(settings)


def _normalize_group_chat_segment(segment: Any) -> str:
    segment_key = str(segment or "").strip().lower()
    alias_map = {
        "supporters": "supporter",
        "dissenters": "dissenter",
    }
    return alias_map.get(segment_key, segment_key)


def _parse_group_chat_request(body: dict[str, Any]) -> V2GroupChatRequest:
    normalized = dict(body or {})
    normalized["segment"] = _normalize_group_chat_segment(normalized.get("segment"))
    try:
        return V2GroupChatRequest(**normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@compat_router.get("/countries", response_model=list[V2CountryResponse])
def v2_countries(settings: Settings = Depends(get_settings)) -> list[V2CountryResponse]:
    service = ConfigService(settings)
    rows = []
    for country in service.list_countries():
        rows.append(
            V2CountryResponse(
                name=str(country.get("name", "")),
                code=str(country.get("code", "")).lower(),
                flag_emoji=str(country.get("flag_emoji", "")),
                dataset_path=str(country.get("dataset_path", "")),
                available=bool(country.get("available", True)),
            )
        )
    return rows


@compat_router.get("/providers", response_model=list[V2ProviderResponse])
def v2_providers(settings: Settings = Depends(get_settings)) -> list[V2ProviderResponse]:
    payload = ConsoleService(settings).v2_provider_catalog()
    return [V2ProviderResponse(**row) for row in payload]


@compat_router.post("/session/create", response_model=V2SessionCreateResponse)
def v2_session_create(
    req: V2SessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> V2SessionCreateResponse:
    provider = "google" if req.provider == "gemini" else req.provider
    try:
        payload = ConsoleService(settings).create_v2_session(
            country=req.country,
            use_case=req.use_case,
            provider=provider,
            model=req.model,
            api_key=req.api_key,
            mode=req.mode,
            session_id=req.session_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return V2SessionCreateResponse(**payload)


@compat_router.patch("/session/{session_id}/config", response_model=V2SessionConfigResponse)
def v2_session_update_config(
    session_id: str,
    req: V2SessionConfigPatchRequest,
    settings: Settings = Depends(get_settings),
) -> V2SessionConfigResponse:
    try:
        payload = ConsoleService(settings).update_v2_session_config(
            session_id,
            country=req.country,
            use_case=req.use_case,
            provider=req.provider,
            model=req.model,
            api_key=req.api_key,
            guiding_prompt=req.guiding_prompt,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return V2SessionConfigResponse(**payload)


@router.post("/session", response_model=ConsoleSessionResponse)
def create_session(
    req: ConsoleSessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionResponse:
    payload = ConsoleService(settings).create_session(
        req.session_id,
        req.mode,
        model_provider=req.model_provider,
        model_name=req.model_name,
        embed_model_name=req.embed_model_name,
        api_key=req.api_key,
        base_url=req.base_url,
    )
    return ConsoleSessionResponse(**payload)


@router.get("/model/providers", response_model=ConsoleModelProviderCatalogResponse)
def model_providers(settings: Settings = Depends(get_settings)) -> ConsoleModelProviderCatalogResponse:
    payload = ConsoleService(settings).model_provider_catalog()
    return ConsoleModelProviderCatalogResponse(**payload)


@router.get("/model/providers/{provider}/models", response_model=ConsoleProviderModelsResponse)
def provider_models(
    provider: str,
    api_key: str | None = Query(default=None),
    base_url: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> ConsoleProviderModelsResponse:
    payload = ConsoleService(settings).list_provider_models(
        provider,
        api_key=api_key,
        base_url=base_url,
    )
    return ConsoleProviderModelsResponse(**payload)


@router.get("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def get_session_model(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).get_session_model_config(session_id)
    return ConsoleSessionModelConfigResponse(**payload)


@router.put("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def update_session_model(
    session_id: str,
    req: ConsoleSessionModelConfigRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).update_session_model_config(
        session_id,
        model_provider=req.model_provider,
        model_name=req.model_name,
        embed_model_name=req.embed_model_name,
        api_key=req.api_key,
        base_url=req.base_url,
    )
    return ConsoleSessionModelConfigResponse(**payload)


@router.post("/session/{session_id}/knowledge/process", response_model=KnowledgeArtifactResponse)
async def process_knowledge(
    session_id: str,
    req: ConsoleKnowledgeProcessRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached knowledge for demo
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id)
        if knowledge:
            return KnowledgeArtifactResponse(**knowledge)
    
    payload = await ConsoleService(settings).process_knowledge(
        session_id,
        document_text=req.document_text,
        source_path=req.source_path,
        documents=req.documents,
        guiding_prompt=req.guiding_prompt,
        demographic_focus=req.demographic_focus,
        use_default_demo_document=req.use_default_demo_document,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/knowledge/upload", response_model=KnowledgeArtifactResponse)
async def upload_knowledge(
    session_id: str,
    file: UploadFile = File(...),
    guiding_prompt: str | None = Form(default=None),
    demographic_focus: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached knowledge for demo
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id)
        if knowledge:
            return KnowledgeArtifactResponse(**knowledge)
    
    payload = await ConsoleService(settings).process_uploaded_knowledge(
        session_id,
        upload=file,
        guiding_prompt=guiding_prompt,
        demographic_focus=demographic_focus,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/scrape", response_model=ConsoleScrapeResponse)
def scrape_document(
    session_id: str,
    req: ConsoleScrapeRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleScrapeResponse:
    del session_id
    del settings
    scraper = ScrapeService()
    try:
        payload = scraper.scrape(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to scrape URL: {exc}") from exc
    return ConsoleScrapeResponse(**payload)


@router.get("/session/{session_id}/filters", response_model=ConsoleDynamicFiltersResponse)
def session_filters(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ConsoleDynamicFiltersResponse:
    try:
        payload = ConsoleService(settings).get_dynamic_filters(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConsoleDynamicFiltersResponse(**payload)


@compat_router.get("/token-usage/{session_id}/estimate", response_model=TokenUsageEstimateResponse)
def token_usage_estimate(
    session_id: str,
    agents: int = Query(default=250, ge=1, le=2000),
    rounds: int = Query(default=5, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> TokenUsageEstimateResponse:
    payload = ConsoleService(settings).estimate_token_usage(
        session_id,
        agents=agents,
        rounds=rounds,
    )
    return TokenUsageEstimateResponse(**payload)


@compat_router.get("/token-usage/{session_id}", response_model=TokenUsageRuntimeResponse)
def token_usage_runtime(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> TokenUsageRuntimeResponse:
    payload = ConsoleService(settings).get_runtime_token_usage(session_id)
    return TokenUsageRuntimeResponse(**payload)


@router.post("/session/{session_id}/sampling/preview", response_model=PopulationArtifactResponse)
def preview_population(
    session_id: str,
    req: PopulationPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> PopulationArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached population for demo
        demo_service = _get_demo_service(settings)
        population = demo_service.get_population_artifact(session_id)
        if population:
            return PopulationArtifactResponse(**population)
    
    payload = ConsoleService(settings).preview_population(session_id, req)
    return PopulationArtifactResponse(**payload)


@router.get("/session/{session_id}/simulation/state", response_model=SimulationStateResponse)
def simulation_state(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached simulation state for demo
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)
    
    payload = ConsoleService(settings).get_simulation_state(session_id)
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/metrics", response_model=SimulationStateResponse)
def simulation_metrics(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    payload = ConsoleService(settings).get_simulation_state(session_id)
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulation/start", response_model=SimulationStateResponse)
def simulation_start(
    session_id: str,
    req: SimulationStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached simulation state for demo (already completed)
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)
    
    payload = ConsoleService(settings).start_simulation(
        session_id,
        policy_summary=req.policy_summary,
        rounds=req.rounds,
        controversy_boost=req.controversy_boost,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulate", response_model=SimulationStateResponse)
def simulate(
    session_id: str,
    req: SimulationQuickStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    service = ConsoleService(settings)
    policy_summary = str(req.policy_summary or "").strip()
    if not policy_summary:
        knowledge = service.store.get_knowledge_artifact(session_id)
        if knowledge:
            policy_summary = str(knowledge.get("summary") or "").strip()
    if not policy_summary:
        raise HTTPException(status_code=422, detail="Policy summary is required to start a simulation.")

    payload = service.start_simulation(
        session_id,
        policy_summary=policy_summary,
        rounds=req.rounds,
        controversy_boost=req.controversy_boost,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/stream")
def simulation_stream(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached events from demo cache
        demo_service = _get_demo_service(settings)
        cache = demo_service._load_demo_cache()
        if cache and "simulationState" in cache:
            # Create a stream from cached events
            sim_state = cache["simulationState"]
            recent_events = sim_state.get("recent_events", [])
            
            def demo_sse_iter():
                # Send all cached events
                for event in recent_events:
                    event_type = event.get("event_type", "event")
                    data = json.dumps(event)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                # Send completion
                yield f"event: completed\ndata: {json.dumps({'session_id': session_id, 'status': 'completed'})}\n\n"
            
            return StreamingResponse(demo_sse_iter(), media_type="text/event-stream")
    
    stream = SimulationStreamService(settings).sse_iter(session_id)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/session/{session_id}/report", response_model=ReportFullResponse)
def v2_report(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    try:
        payload = ConsoleService(settings).get_report_full(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReportFullResponse(**payload)


@router.get("/session/{session_id}/report/export")
def v2_report_export(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    try:
        filename, payload = ConsoleService(settings).export_v2_report_docx(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.post("/session/{session_id}/chat/group", response_model=V2GroupChatResponse)
def v2_group_chat(
    session_id: str,
    req: dict[str, Any] = Body(...),
    settings: Settings = Depends(get_settings),
) -> V2GroupChatResponse:
    try:
        parsed = _parse_group_chat_request(req)
        payload = ConsoleService(settings).group_chat(
            session_id,
            segment=parsed.segment,
            message=parsed.message,
            top_n=parsed.top_n,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2GroupChatResponse(**payload)


@router.post("/session/{session_id}/chat/agent/{agent_id}", response_model=V2AgentChatResponse)
def v2_agent_chat(
    session_id: str,
    agent_id: str,
    req: V2AgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> V2AgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat_v2(session_id, agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2AgentChatResponse(**payload)


@router.get("/session/{session_id}/report/full", response_model=ReportFullResponse)
def report_full(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return ReportFullResponse(**report)
    
    return ReportFullResponse(**ConsoleService(settings).get_report_full(session_id))


@router.post("/session/{session_id}/report/generate", response_model=ReportFullResponse)
def report_generate(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return ReportFullResponse(**report)
    
    return ReportFullResponse(**ConsoleService(settings).generate_report(session_id))


@router.get("/session/{session_id}/report/opinions", response_model=ReportOpinionsResponse)
def report_opinions(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportOpinionsResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        opinions = demo_service.get_report_opinions(session_id)
        return ReportOpinionsResponse(**opinions)
    
    return ReportOpinionsResponse(**ConsoleService(settings).get_report_opinions(session_id))


@router.get("/session/{session_id}/report/friction-map", response_model=ReportFrictionMapResponse)
def report_friction_map(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFrictionMapResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        friction = demo_service.get_friction_map(session_id)
        return ReportFrictionMapResponse(**friction)
    
    return ReportFrictionMapResponse(**ConsoleService(settings).get_report_friction_map(session_id))


@router.get("/session/{session_id}/interaction-hub", response_model=InteractionHubResponse)
def interaction_hub(
    session_id: str,
    agent_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> InteractionHubResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        hub = demo_service.get_interaction_hub(session_id, agent_id)
        return InteractionHubResponse(**hub)
    
    return InteractionHubResponse(**ConsoleService(settings).get_interaction_hub(session_id, agent_id=agent_id))


@router.post("/session/{session_id}/interaction-hub/report-chat", response_model=ConsoleReportChatResponse)
def interaction_hub_report_chat(
    session_id: str,
    req: ConsoleReportChatRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleReportChatResponse:
    try:
        payload = ConsoleService(settings).report_chat(session_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsoleReportChatResponse(**payload)


@router.post("/session/{session_id}/interaction-hub/agent-chat", response_model=ConsoleAgentChatResponse)
def interaction_hub_agent_chat(
    session_id: str,
    req: ConsoleAgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleAgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat(session_id, req.agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsoleAgentChatResponse(**payload)
===
import json
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from mckainsey.config import Settings, get_settings
from mckainsey.models.console import (
    ConsoleAgentChatRequest,
    ConsoleAgentChatResponse,
    ConsoleDynamicFiltersResponse,
    ConsoleKnowledgeProcessRequest,
    ConsoleModelProviderCatalogResponse,
    ConsoleProviderModelsResponse,
    ConsoleReportChatRequest,
    ConsoleReportChatResponse,
    ConsoleScrapeRequest,
    ConsoleScrapeResponse,
    ConsoleSessionModelConfigRequest,
    ConsoleSessionModelConfigResponse,
    ConsoleSessionCreateRequest,
    ConsoleSessionResponse,
    V2AgentChatRequest,
    V2AgentChatResponse,
    V2GroupChatRequest,
    V2GroupChatResponse,
    InteractionHubResponse,
    KnowledgeArtifactResponse,
    PopulationArtifactResponse,
    PopulationPreviewRequest,
    ReportFrictionMapResponse,
    ReportFullResponse,
    ReportOpinionsResponse,
    SimulationStartRequest,
    SimulationQuickStartRequest,
    SimulationStateResponse,
    TokenUsageEstimateResponse,
    TokenUsageRuntimeResponse,
    V2CountryResponse,
    V2ProviderResponse,
    V2ReportResponse,
    V2SessionConfigPatchRequest,
    V2SessionConfigResponse,
    V2SessionCreateRequest,
    V2SessionCreateResponse,
)
from mckainsey.services.config_service import ConfigService
from mckainsey.services.console_service import ConsoleService
from mckainsey.services.demo_service import DemoService
from mckainsey.services.scrape_service import ScrapeService
from mckainsey.services.simulation_stream_service import SimulationStreamService


router = APIRouter(prefix="/api/v2/console", tags=["console"])
compat_router = APIRouter(prefix="/api/v2", tags=["console-compat"])


def _is_demo_session(session_id: str, settings: Settings) -> bool:
    """Check if session is in demo mode."""
    from mckainsey.services.storage import SimulationStore
    store = SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    return session is not None and session.get("mode") == "demo"


def _get_demo_service(settings: Settings) -> DemoService:
    """Get demo service instance."""
    return DemoService(settings)


def _normalize_group_chat_segment(segment: Any) -> str:
    segment_key = str(segment or "").strip().lower()
    alias_map = {
        "supporters": "supporter",
        "dissenters": "dissenter",
    }
    return alias_map.get(segment_key, segment_key)


def _parse_group_chat_request(body: dict[str, Any]) -> V2GroupChatRequest:
    normalized = dict(body or {})
    normalized["segment"] = _normalize_group_chat_segment(normalized.get("segment"))
    try:
        return V2GroupChatRequest(**normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@compat_router.get("/countries", response_model=list[V2CountryResponse])
def v2_countries(settings: Settings = Depends(get_settings)) -> list[V2CountryResponse]:
    service = ConfigService(settings)
    rows = []
    for country in service.list_countries():
        rows.append(
            V2CountryResponse(
                name=str(country.get("name", "")),
                code=str(country.get("code", "")).lower(),
                flag_emoji=str(country.get("flag_emoji", "")),
                dataset_path=str(country.get("dataset_path", "")),
                available=bool(country.get("available", True)),
            )
        )
    return rows


@compat_router.get("/providers", response_model=list[V2ProviderResponse])
def v2_providers(settings: Settings = Depends(get_settings)) -> list[V2ProviderResponse]:
    payload = ConsoleService(settings).v2_provider_catalog()
    return [V2ProviderResponse(**row) for row in payload]


@compat_router.post("/session/create", response_model=V2SessionCreateResponse)
def v2_session_create(
    req: V2SessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> V2SessionCreateResponse:
    provider = "google" if req.provider == "gemini" else req.provider
    try:
        payload = ConsoleService(settings).create_v2_session(
            country=req.country,
            use_case=req.use_case,
            provider=provider,
            model=req.model,
            api_key=req.api_key,
            mode=req.mode,
            session_id=req.session_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return V2SessionCreateResponse(**payload)


@compat_router.patch("/session/{session_id}/config", response_model=V2SessionConfigResponse)
def v2_session_update_config(
    session_id: str,
    req: V2SessionConfigPatchRequest,
    settings: Settings = Depends(get_settings),
) -> V2SessionConfigResponse:
    try:
        payload = ConsoleService(settings).update_v2_session_config(
            session_id,
            country=req.country,
            use_case=req.use_case,
            provider=req.provider,
            model=req.model,
            api_key=req.api_key,
            guiding_prompt=req.guiding_prompt,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return V2SessionConfigResponse(**payload)


@router.post("/session", response_model=ConsoleSessionResponse)
def create_session(
    req: ConsoleSessionCreateRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionResponse:
    payload = ConsoleService(settings).create_session(
        req.session_id,
        req.mode,
        model_provider=req.model_provider,
        model_name=req.model_name,
        embed_model_name=req.embed_model_name,
        api_key=req.api_key,
        base_url=req.base_url,
    )
    return ConsoleSessionResponse(**payload)


@router.get("/model/providers", response_model=ConsoleModelProviderCatalogResponse)
def model_providers(settings: Settings = Depends(get_settings)) -> ConsoleModelProviderCatalogResponse:
    payload = ConsoleService(settings).model_provider_catalog()
    return ConsoleModelProviderCatalogResponse(**payload)


@router.get("/model/providers/{provider}/models", response_model=ConsoleProviderModelsResponse)
def provider_models(
    provider: str,
    api_key: str | None = Query(default=None),
    base_url: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> ConsoleProviderModelsResponse:
    payload = ConsoleService(settings).list_provider_models(
        provider,
        api_key=api_key,
        base_url=base_url,
    )
    return ConsoleProviderModelsResponse(**payload)


@router.get("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def get_session_model(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).get_session_model_config(session_id)
    return ConsoleSessionModelConfigResponse(**payload)


@router.put("/session/{session_id}/model", response_model=ConsoleSessionModelConfigResponse)
def update_session_model(
    session_id: str,
    req: ConsoleSessionModelConfigRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleSessionModelConfigResponse:
    payload = ConsoleService(settings).update_session_model_config(
        session_id,
        model_provider=req.model_provider,
        model_name=req.model_name,
        embed_model_name=req.embed_model_name,
        api_key=req.api_key,
        base_url=req.base_url,
    )
    return ConsoleSessionModelConfigResponse(**payload)


@router.post("/session/{session_id}/knowledge/process", response_model=KnowledgeArtifactResponse)
async def process_knowledge(
    session_id: str,
    req: ConsoleKnowledgeProcessRequest,
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached knowledge for demo
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id)
        if knowledge:
            return KnowledgeArtifactResponse(**knowledge)
    
    payload = await ConsoleService(settings).process_knowledge(
        session_id,
        document_text=req.document_text,
        source_path=req.source_path,
        documents=req.documents,
        guiding_prompt=req.guiding_prompt,
        demographic_focus=req.demographic_focus,
        use_default_demo_document=req.use_default_demo_document,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/knowledge/upload", response_model=KnowledgeArtifactResponse)
async def upload_knowledge(
    session_id: str,
    file: UploadFile = File(...),
    guiding_prompt: str | None = Form(default=None),
    demographic_focus: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
) -> KnowledgeArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached knowledge for demo
        demo_service = _get_demo_service(settings)
        knowledge = demo_service.get_knowledge_artifact(session_id)
        if knowledge:
            return KnowledgeArtifactResponse(**knowledge)
    
    payload = await ConsoleService(settings).process_uploaded_knowledge(
        session_id,
        upload=file,
        guiding_prompt=guiding_prompt,
        demographic_focus=demographic_focus,
    )
    return KnowledgeArtifactResponse(**payload)


@router.post("/session/{session_id}/scrape", response_model=ConsoleScrapeResponse)
def scrape_document(
    session_id: str,
    req: ConsoleScrapeRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleScrapeResponse:
    del session_id
    del settings
    scraper = ScrapeService()
    try:
        payload = scraper.scrape(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to scrape URL: {exc}") from exc
    return ConsoleScrapeResponse(**payload)


@router.get("/session/{session_id}/filters", response_model=ConsoleDynamicFiltersResponse)
def session_filters(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ConsoleDynamicFiltersResponse:
    try:
        payload = ConsoleService(settings).get_dynamic_filters(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConsoleDynamicFiltersResponse(**payload)


@compat_router.get("/token-usage/{session_id}/estimate", response_model=TokenUsageEstimateResponse)
def token_usage_estimate(
    session_id: str,
    agents: int = Query(default=250, ge=1, le=2000),
    rounds: int = Query(default=5, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> TokenUsageEstimateResponse:
    payload = ConsoleService(settings).estimate_token_usage(
        session_id,
        agents=agents,
        rounds=rounds,
    )
    return TokenUsageEstimateResponse(**payload)


@compat_router.get("/token-usage/{session_id}", response_model=TokenUsageRuntimeResponse)
def token_usage_runtime(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> TokenUsageRuntimeResponse:
    payload = ConsoleService(settings).get_runtime_token_usage(session_id)
    return TokenUsageRuntimeResponse(**payload)


@router.post("/session/{session_id}/sampling/preview", response_model=PopulationArtifactResponse)
def preview_population(
    session_id: str,
    req: PopulationPreviewRequest,
    settings: Settings = Depends(get_settings),
) -> PopulationArtifactResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached population for demo
        demo_service = _get_demo_service(settings)
        population = demo_service.get_population_artifact(session_id)
        if population:
            return PopulationArtifactResponse(**population)
    
    payload = ConsoleService(settings).preview_population(session_id, req)
    return PopulationArtifactResponse(**payload)


@router.get("/session/{session_id}/simulation/state", response_model=SimulationStateResponse)
def simulation_state(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached simulation state for demo
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)
    
    payload = ConsoleService(settings).get_simulation_state(session_id)
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/metrics", response_model=SimulationStateResponse)
def simulation_metrics(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    payload = ConsoleService(settings).get_simulation_state(session_id)
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulation/start", response_model=SimulationStateResponse)
def simulation_start(
    session_id: str,
    req: SimulationStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached simulation state for demo (already completed)
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)
    
    payload = ConsoleService(settings).start_simulation(
        session_id,
        policy_summary=req.policy_summary,
        rounds=req.rounds,
        controversy_boost=req.controversy_boost,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.post("/session/{session_id}/simulate", response_model=SimulationStateResponse)
def simulate(
    session_id: str,
    req: SimulationQuickStartRequest,
    settings: Settings = Depends(get_settings),
) -> SimulationStateResponse:
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        state = demo_service.get_simulation_state(session_id)
        if state:
            return SimulationStateResponse(**state)

    service = ConsoleService(settings)
    policy_summary = str(req.policy_summary or "").strip()
    if not policy_summary:
        knowledge = service.store.get_knowledge_artifact(session_id)
        if knowledge:
            policy_summary = str(knowledge.get("summary") or "").strip()
    if not policy_summary:
        raise HTTPException(status_code=422, detail="Policy summary is required to start a simulation.")

    payload = service.start_simulation(
        session_id,
        policy_summary=policy_summary,
        rounds=req.rounds,
        controversy_boost=req.controversy_boost,
        mode=req.mode,
    )
    return SimulationStateResponse(**payload)


@router.get("/session/{session_id}/simulation/stream")
def simulation_stream(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        # Return cached events from demo cache
        demo_service = _get_demo_service(settings)
        cache = demo_service._load_demo_cache()
        if cache and "simulationState" in cache:
            # Create a stream from cached events
            sim_state = cache["simulationState"]
            recent_events = sim_state.get("recent_events", [])
            
            def demo_sse_iter():
                # Send all cached events
                for event in recent_events:
                    event_type = event.get("event_type", "event")
                    data = json.dumps(event)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                # Send completion
                yield f"event: completed\ndata: {json.dumps({'session_id': session_id, 'status': 'completed'})}\n\n"
            
            return StreamingResponse(demo_sse_iter(), media_type="text/event-stream")
    
    stream = SimulationStreamService(settings).sse_iter(session_id)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/session/{session_id}/report", response_model=ReportFullResponse)
def v2_report(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    try:
        payload = ConsoleService(settings).get_report_full(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReportFullResponse(**payload)


@router.get("/session/{session_id}/report/export")
def v2_report_export(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    try:
        filename, payload = ConsoleService(settings).export_v2_report_docx(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.post("/session/{session_id}/chat/group", response_model=V2GroupChatResponse)
def v2_group_chat(
    session_id: str,
    req: dict[str, Any] = Body(...),
    settings: Settings = Depends(get_settings),
) -> V2GroupChatResponse:
    try:
        parsed = _parse_group_chat_request(req)
        payload = ConsoleService(settings).group_chat(
            session_id,
            segment=parsed.segment,
            message=parsed.message,
            top_n=parsed.top_n,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2GroupChatResponse(**payload)


@router.post("/session/{session_id}/chat/agent/{agent_id}", response_model=V2AgentChatResponse)
def v2_agent_chat(
    session_id: str,
    agent_id: str,
    req: V2AgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> V2AgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat_v2(session_id, agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return V2AgentChatResponse(**payload)


@router.get("/session/{session_id}/report/full", response_model=ReportFullResponse)
def report_full(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return ReportFullResponse(**report)
    
    return ReportFullResponse(**ConsoleService(settings).get_report_full(session_id))


@router.post("/session/{session_id}/report/generate", response_model=ReportFullResponse)
def report_generate(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFullResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        report = demo_service.get_report(session_id)
        if report:
            return ReportFullResponse(**report)
    
    return ReportFullResponse(**ConsoleService(settings).generate_report(session_id))


@router.get("/session/{session_id}/report/opinions", response_model=ReportOpinionsResponse)
def report_opinions(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportOpinionsResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        opinions = demo_service.get_report_opinions(session_id)
        return ReportOpinionsResponse(**opinions)
    
    return ReportOpinionsResponse(**ConsoleService(settings).get_report_opinions(session_id))


@router.get("/session/{session_id}/report/friction-map", response_model=ReportFrictionMapResponse)
def report_friction_map(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> ReportFrictionMapResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        friction = demo_service.get_friction_map(session_id)
        return ReportFrictionMapResponse(**friction)
    
    return ReportFrictionMapResponse(**ConsoleService(settings).get_report_friction_map(session_id))


@router.get("/session/{session_id}/interaction-hub", response_model=InteractionHubResponse)
def interaction_hub(
    session_id: str,
    agent_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> InteractionHubResponse:
    # Check if demo mode with cached data
    if _is_demo_session(session_id, settings) and _get_demo_service(settings).is_demo_available():
        demo_service = _get_demo_service(settings)
        hub = demo_service.get_interaction_hub(session_id, agent_id)
        return InteractionHubResponse(**hub)
    
    return InteractionHubResponse(**ConsoleService(settings).get_interaction_hub(session_id, agent_id=agent_id))


@router.post("/session/{session_id}/interaction-hub/report-chat", response_model=ConsoleReportChatResponse)
def interaction_hub_report_chat(
    session_id: str,
    req: ConsoleReportChatRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleReportChatResponse:
    try:
        payload = ConsoleService(settings).report_chat(session_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsoleReportChatResponse(**payload)


@router.post("/session/{session_id}/interaction-hub/agent-chat", response_model=ConsoleAgentChatResponse)
def interaction_hub_agent_chat(
    session_id: str,
    req: ConsoleAgentChatRequest,
    settings: Settings = Depends(get_settings),
) -> ConsoleAgentChatResponse:
    try:
        payload = ConsoleService(settings).agent_chat(session_id, req.agent_id, req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConsoleAgentChatResponse(**payload)


@compat_router.post("/questions/generate-metadata")
def generate_question_metadata(
    req: dict[str, Any] = Body(...),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Generate metric metadata for a custom analysis question using LLM."""
    question = str(req.get("question", "")).strip()
    use_case = str(req.get("use_case", "")).strip() or None
    if not question:
        raise HTTPException(status_code=422, detail="'question' field is required.")
    try:
        from mckainsey.services.question_metadata_service import QuestionMetadataService
        service = QuestionMetadataService(settings)
        metadata = service.generate_metadata(question, use_case=use_case)
        return metadata
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@compat_router.get("/session/{session_id}/analysis-questions")
def get_analysis_questions(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get the analysis questions configured for a session's use case."""
    config_service = ConfigService(settings)
    store_module = __import__("mckainsey.services.storage", fromlist=["SimulationStore"])
    store = store_module.SimulationStore(settings.simulation_db_path)
    session = store.get_console_session(session_id)
    use_case = session.get("use_case", "") if session else ""
    try:
        questions = config_service.get_analysis_questions(use_case)
    except Exception:  # noqa: BLE001
        questions = []
    return {"session_id": session_id, "use_case": use_case, "questions": questions}
```

- `POST /api/v2/questions/generate-metadata` — LLM metadata for custom questions
- `GET /api/v2/session/{id}/analysis-questions` — config questions for a session

---

## 3. Frontend Changes

### AppContext
```diff:AppContext.tsx
import React, { createContext, useCallback, useContext, useMemo, useState, ReactNode } from 'react';
import { Agent, SimPost } from '@/data/mockData';
import { KnowledgeArtifact, ModelProviderId, PopulationArtifact } from '@/lib/console-api';

type ChatHistoryEntry = {
  role: 'user' | 'agent';
  content: string;
  agentId?: string;
};

interface AppState {
  currentStep: number;
  completedSteps: number[];
  sessionId: string | null;
  country: string;
  useCase: string;
  modelProvider: ModelProviderId;
  modelName: string;
  embedModelName: string;
  modelApiKey: string;
  modelBaseUrl: string;
  uploadedFiles: File[];
  guidingPrompts: string[];
  knowledgeGraphReady: boolean;
  knowledgeArtifact: KnowledgeArtifact | null;
  knowledgeLoading: boolean;
  knowledgeError: string | null;
  agentCount: number;
  sampleMode: 'affected_groups' | 'population_baseline';
  samplingInstructions: string;
  sampleSeed: number | null;
  populationArtifact: PopulationArtifact | null;
  populationLoading: boolean;
  populationError: string | null;
  agents: Agent[];
  agentsGenerated: boolean;
  simulationRounds: number;
  simulationComplete: boolean;
  simPosts: SimPost[];
  chatHistory: Record<string, ChatHistoryEntry[]>;
}

interface AppContextType extends AppState {
  setCurrentStep: (step: number) => void;
  completeStep: (step: number) => void;
  setSessionId: (sessionId: string | null) => void;
  setCountry: (country: string) => void;
  setUseCase: (useCase: string) => void;
  setModelProvider: (provider: ModelProviderId) => void;
  setModelName: (modelName: string) => void;
  setEmbedModelName: (embedModelName: string) => void;
  setModelApiKey: (modelApiKey: string) => void;
  setModelBaseUrl: (modelBaseUrl: string) => void;
  setUploadedFiles: (files: File[]) => void;
  addUploadedFile: (file: File) => void;
  removeUploadedFile: (index: number) => void;
  setGuidingPrompts: (prompts: string[]) => void;
  addGuidingPrompt: () => void;
  updateGuidingPrompt: (index: number, value: string) => void;
  removeGuidingPrompt: (index: number) => void;
  setKnowledgeGraphReady: (ready: boolean) => void;
  setKnowledgeArtifact: (artifact: KnowledgeArtifact | null) => void;
  setKnowledgeLoading: (loading: boolean) => void;
  setKnowledgeError: (error: string | null) => void;
  setAgentCount: (count: number) => void;
  setSampleMode: (mode: 'affected_groups' | 'population_baseline') => void;
  setSamplingInstructions: (value: string) => void;
  setSampleSeed: (seed: number | null) => void;
  setPopulationArtifact: (artifact: PopulationArtifact | null) => void;
  setPopulationLoading: (loading: boolean) => void;
  setPopulationError: (error: string | null) => void;
  setAgents: (agents: Agent[]) => void;
  setAgentsGenerated: (gen: boolean) => void;
  setSimulationRounds: (rounds: number) => void;
  setSimulationComplete: (complete: boolean) => void;
  setSimPosts: (posts: SimPost[]) => void;
  addChatMessage: (threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>({
    currentStep: 1,
    completedSteps: [],
    sessionId: null,
    country: 'singapore',
    useCase: 'policy-review',
    modelProvider: 'ollama',
    modelName: 'qwen3:4b-instruct-2507-q4_K_M',
    embedModelName: 'nomic-embed-text',
    modelApiKey: '',
    modelBaseUrl: 'http://127.0.0.1:11434/v1/',
    uploadedFiles: [],
    guidingPrompts: [''],
    knowledgeGraphReady: false,
    knowledgeArtifact: null,
    knowledgeLoading: false,
    knowledgeError: null,
    agentCount: 0,
    sampleMode: 'affected_groups',
    samplingInstructions: '',
    sampleSeed: null,
    populationArtifact: null,
    populationLoading: false,
    populationError: null,
    agents: [],
    agentsGenerated: false,
    simulationRounds: 3,
    simulationComplete: false,
    simPosts: [],
    chatHistory: {},
  });

  const setCurrentStep = useCallback((step: number) => setState(s => ({ ...s, currentStep: step })), []);
  const completeStep = useCallback((step: number) => setState(s => ({
    ...s,
    completedSteps: s.completedSteps.includes(step) ? s.completedSteps : [...s.completedSteps, step],
  })), []);
  const setSessionId = useCallback((sessionId: string | null) => setState(s => ({ ...s, sessionId })), []);
  const setCountry = useCallback((country: string) => setState(s => ({ ...s, country })), []);
  const setUseCase = useCallback((useCase: string) => setState(s => ({ ...s, useCase })), []);
  const setModelProvider = useCallback((modelProvider: ModelProviderId) => setState(s => ({ ...s, modelProvider })), []);
  const setModelName = useCallback((modelName: string) => setState(s => ({ ...s, modelName })), []);
  const setEmbedModelName = useCallback((embedModelName: string) => setState(s => ({ ...s, embedModelName })), []);
  const setModelApiKey = useCallback((modelApiKey: string) => setState(s => ({ ...s, modelApiKey })), []);
  const setModelBaseUrl = useCallback((modelBaseUrl: string) => setState(s => ({ ...s, modelBaseUrl })), []);
  const setUploadedFiles = useCallback((files: File[]) => setState(s => ({ ...s, uploadedFiles: files })), []);
  const addUploadedFile = useCallback((file: File) => setState(s => ({ ...s, uploadedFiles: [...s.uploadedFiles, file] })), []);
  const removeUploadedFile = useCallback((index: number) => setState(s => ({ ...s, uploadedFiles: s.uploadedFiles.filter((_, i) => i !== index) })), []);
  const setGuidingPrompts = useCallback((prompts: string[]) => setState(s => ({ ...s, guidingPrompts: prompts })), []);
  const addGuidingPrompt = useCallback(() => setState(s => ({ ...s, guidingPrompts: [...s.guidingPrompts, ''] })), []);
  const updateGuidingPrompt = useCallback((index: number, value: string) => setState(s => ({
    ...s,
    guidingPrompts: s.guidingPrompts.map((p, i) => i === index ? value : p),
  })), []);
  const removeGuidingPrompt = useCallback((index: number) => setState(s => ({
    ...s,
    guidingPrompts: s.guidingPrompts.filter((_, i) => i !== index),
  })), []);
  const setKnowledgeGraphReady = useCallback((ready: boolean) => setState(s => ({ ...s, knowledgeGraphReady: ready })), []);
  const setKnowledgeArtifact = useCallback((knowledgeArtifact: KnowledgeArtifact | null) => setState(s => ({ ...s, knowledgeArtifact })), []);
  const setKnowledgeLoading = useCallback((knowledgeLoading: boolean) => setState(s => ({ ...s, knowledgeLoading })), []);
  const setKnowledgeError = useCallback((knowledgeError: string | null) => setState(s => ({ ...s, knowledgeError })), []);
  const setAgentCount = useCallback((count: number) => setState(s => ({ ...s, agentCount: count })), []);
  const setSampleMode = useCallback((sampleMode: 'affected_groups' | 'population_baseline') => setState(s => ({ ...s, sampleMode })), []);
  const setSamplingInstructions = useCallback((samplingInstructions: string) => setState(s => ({ ...s, samplingInstructions })), []);
  const setSampleSeed = useCallback((sampleSeed: number | null) => setState(s => ({ ...s, sampleSeed })), []);
  const setPopulationArtifact = useCallback((populationArtifact: PopulationArtifact | null) => setState(s => ({ ...s, populationArtifact })), []);
  const setPopulationLoading = useCallback((populationLoading: boolean) => setState(s => ({ ...s, populationLoading })), []);
  const setPopulationError = useCallback((populationError: string | null) => setState(s => ({ ...s, populationError })), []);
  const setAgents = useCallback((agents: Agent[]) => setState(s => ({ ...s, agents })), []);
  const setAgentsGenerated = useCallback((gen: boolean) => setState(s => ({ ...s, agentsGenerated: gen })), []);
  const setSimulationRounds = useCallback((rounds: number) => setState(s => ({ ...s, simulationRounds: rounds })), []);
  const setSimulationComplete = useCallback((complete: boolean) => setState(s => ({ ...s, simulationComplete: complete })), []);
  const setSimPosts = useCallback((posts: SimPost[]) => setState(s => ({ ...s, simPosts: posts })), []);
  const addChatMessage = useCallback((threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => {
    setState(s => ({
      ...s,
      chatHistory: {
        ...s.chatHistory,
        [threadId]: [...(s.chatHistory[threadId] || []), { role, content, agentId: sourceAgentId }],
      },
    }));
  }, []);

  const value = useMemo(() => ({
    ...state,
    setCurrentStep,
    completeStep,
    setSessionId,
    setCountry,
    setUseCase,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
    setUploadedFiles,
    addUploadedFile,
    removeUploadedFile,
    setGuidingPrompts,
    addGuidingPrompt,
    updateGuidingPrompt,
    removeGuidingPrompt,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationComplete,
    setSimPosts,
    addChatMessage,
  }), [
    state,
    setCurrentStep,
    completeStep,
    setSessionId,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
    setUploadedFiles,
    addUploadedFile,
    removeUploadedFile,
    setGuidingPrompts,
    addGuidingPrompt,
    updateGuidingPrompt,
    removeGuidingPrompt,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationComplete,
    setSimPosts,
    addChatMessage,
  ]);

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
===
import React, { createContext, useCallback, useContext, useMemo, useState, ReactNode } from 'react';
import { Agent, SimPost } from '@/data/mockData';
import { KnowledgeArtifact, ModelProviderId, PopulationArtifact } from '@/lib/console-api';

export type AnalysisQuestion = {
  question: string;
  type: 'scale' | 'yes-no' | 'open-ended';
  metric_name: string;
  metric_label?: string;
  metric_unit?: string;
  threshold?: number;
  threshold_direction?: string;
  report_title: string;
  tooltip?: string;
  /** 'preset' = from config YAML, 'custom' = user-created */
  source?: 'preset' | 'custom';
  /** metadata generation status for custom questions */
  metadataStatus?: 'pending' | 'loading' | 'ready' | 'error';
};
type ChatHistoryEntry = {
  role: 'user' | 'agent';
  content: string;
  agentId?: string;
};

interface AppState {
  currentStep: number;
  completedSteps: number[];
  sessionId: string | null;
  country: string;
  useCase: string;
  modelProvider: ModelProviderId;
  modelName: string;
  embedModelName: string;
  modelApiKey: string;
  modelBaseUrl: string;
  uploadedFiles: File[];
  analysisQuestions: AnalysisQuestion[];
  knowledgeGraphReady: boolean;
  knowledgeArtifact: KnowledgeArtifact | null;
  knowledgeLoading: boolean;
  knowledgeError: string | null;
  agentCount: number;
  sampleMode: 'affected_groups' | 'population_baseline';
  samplingInstructions: string;
  sampleSeed: number | null;
  populationArtifact: PopulationArtifact | null;
  populationLoading: boolean;
  populationError: string | null;
  agents: Agent[];
  agentsGenerated: boolean;
  simulationRounds: number;
  simulationComplete: boolean;
  simPosts: SimPost[];
  chatHistory: Record<string, ChatHistoryEntry[]>;
}

interface AppContextType extends AppState {
  setCurrentStep: (step: number) => void;
  completeStep: (step: number) => void;
  setSessionId: (sessionId: string | null) => void;
  setCountry: (country: string) => void;
  setUseCase: (useCase: string) => void;
  setModelProvider: (provider: ModelProviderId) => void;
  setModelName: (modelName: string) => void;
  setEmbedModelName: (embedModelName: string) => void;
  setModelApiKey: (modelApiKey: string) => void;
  setModelBaseUrl: (modelBaseUrl: string) => void;
  setUploadedFiles: (files: File[]) => void;
  addUploadedFile: (file: File) => void;
  removeUploadedFile: (index: number) => void;
  setAnalysisQuestions: (questions: AnalysisQuestion[]) => void;
  addAnalysisQuestion: (question: AnalysisQuestion) => void;
  updateAnalysisQuestion: (index: number, question: AnalysisQuestion) => void;
  removeAnalysisQuestion: (index: number) => void;
  setKnowledgeGraphReady: (ready: boolean) => void;
  setKnowledgeArtifact: (artifact: KnowledgeArtifact | null) => void;
  setKnowledgeLoading: (loading: boolean) => void;
  setKnowledgeError: (error: string | null) => void;
  setAgentCount: (count: number) => void;
  setSampleMode: (mode: 'affected_groups' | 'population_baseline') => void;
  setSamplingInstructions: (value: string) => void;
  setSampleSeed: (seed: number | null) => void;
  setPopulationArtifact: (artifact: PopulationArtifact | null) => void;
  setPopulationLoading: (loading: boolean) => void;
  setPopulationError: (error: string | null) => void;
  setAgents: (agents: Agent[]) => void;
  setAgentsGenerated: (gen: boolean) => void;
  setSimulationRounds: (rounds: number) => void;
  setSimulationComplete: (complete: boolean) => void;
  setSimPosts: (posts: SimPost[]) => void;
  addChatMessage: (threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>({
    currentStep: 1,
    completedSteps: [],
    sessionId: null,
    country: 'singapore',
    useCase: 'public-policy-testing',
    modelProvider: 'ollama',
    modelName: 'qwen3:4b-instruct-2507-q4_K_M',
    embedModelName: 'nomic-embed-text',
    modelApiKey: '',
    modelBaseUrl: 'http://127.0.0.1:11434/v1/',
    uploadedFiles: [],
    analysisQuestions: [],
    knowledgeGraphReady: false,
    knowledgeArtifact: null,
    knowledgeLoading: false,
    knowledgeError: null,
    agentCount: 0,
    sampleMode: 'affected_groups',
    samplingInstructions: '',
    sampleSeed: null,
    populationArtifact: null,
    populationLoading: false,
    populationError: null,
    agents: [],
    agentsGenerated: false,
    simulationRounds: 3,
    simulationComplete: false,
    simPosts: [],
    chatHistory: {},
  });

  const setCurrentStep = useCallback((step: number) => setState(s => ({ ...s, currentStep: step })), []);
  const completeStep = useCallback((step: number) => setState(s => ({
    ...s,
    completedSteps: s.completedSteps.includes(step) ? s.completedSteps : [...s.completedSteps, step],
  })), []);
  const setSessionId = useCallback((sessionId: string | null) => setState(s => ({ ...s, sessionId })), []);
  const setCountry = useCallback((country: string) => setState(s => ({ ...s, country })), []);
  const setUseCase = useCallback((useCase: string) => setState(s => ({ ...s, useCase })), []);
  const setModelProvider = useCallback((modelProvider: ModelProviderId) => setState(s => ({ ...s, modelProvider })), []);
  const setModelName = useCallback((modelName: string) => setState(s => ({ ...s, modelName })), []);
  const setEmbedModelName = useCallback((embedModelName: string) => setState(s => ({ ...s, embedModelName })), []);
  const setModelApiKey = useCallback((modelApiKey: string) => setState(s => ({ ...s, modelApiKey })), []);
  const setModelBaseUrl = useCallback((modelBaseUrl: string) => setState(s => ({ ...s, modelBaseUrl })), []);
  const setUploadedFiles = useCallback((files: File[]) => setState(s => ({ ...s, uploadedFiles: files })), []);
  const addUploadedFile = useCallback((file: File) => setState(s => ({ ...s, uploadedFiles: [...s.uploadedFiles, file] })), []);
  const removeUploadedFile = useCallback((index: number) => setState(s => ({ ...s, uploadedFiles: s.uploadedFiles.filter((_, i) => i !== index) })), []);
  const setAnalysisQuestions = useCallback((questions: AnalysisQuestion[]) => setState(s => ({ ...s, analysisQuestions: questions })), []);
  const addAnalysisQuestion = useCallback((question: AnalysisQuestion) => setState(s => ({ ...s, analysisQuestions: [...s.analysisQuestions, question] })), []);
  const updateAnalysisQuestion = useCallback((index: number, question: AnalysisQuestion) => setState(s => ({
    ...s,
    analysisQuestions: s.analysisQuestions.map((q, i) => i === index ? question : q),
  })), []);
  const removeAnalysisQuestion = useCallback((index: number) => setState(s => ({
    ...s,
    analysisQuestions: s.analysisQuestions.filter((_, i) => i !== index),
  })), []);
  const setKnowledgeGraphReady = useCallback((ready: boolean) => setState(s => ({ ...s, knowledgeGraphReady: ready })), []);
  const setKnowledgeArtifact = useCallback((knowledgeArtifact: KnowledgeArtifact | null) => setState(s => ({ ...s, knowledgeArtifact })), []);
  const setKnowledgeLoading = useCallback((knowledgeLoading: boolean) => setState(s => ({ ...s, knowledgeLoading })), []);
  const setKnowledgeError = useCallback((knowledgeError: string | null) => setState(s => ({ ...s, knowledgeError })), []);
  const setAgentCount = useCallback((count: number) => setState(s => ({ ...s, agentCount: count })), []);
  const setSampleMode = useCallback((sampleMode: 'affected_groups' | 'population_baseline') => setState(s => ({ ...s, sampleMode })), []);
  const setSamplingInstructions = useCallback((samplingInstructions: string) => setState(s => ({ ...s, samplingInstructions })), []);
  const setSampleSeed = useCallback((sampleSeed: number | null) => setState(s => ({ ...s, sampleSeed })), []);
  const setPopulationArtifact = useCallback((populationArtifact: PopulationArtifact | null) => setState(s => ({ ...s, populationArtifact })), []);
  const setPopulationLoading = useCallback((populationLoading: boolean) => setState(s => ({ ...s, populationLoading })), []);
  const setPopulationError = useCallback((populationError: string | null) => setState(s => ({ ...s, populationError })), []);
  const setAgents = useCallback((agents: Agent[]) => setState(s => ({ ...s, agents })), []);
  const setAgentsGenerated = useCallback((gen: boolean) => setState(s => ({ ...s, agentsGenerated: gen })), []);
  const setSimulationRounds = useCallback((rounds: number) => setState(s => ({ ...s, simulationRounds: rounds })), []);
  const setSimulationComplete = useCallback((complete: boolean) => setState(s => ({ ...s, simulationComplete: complete })), []);
  const setSimPosts = useCallback((posts: SimPost[]) => setState(s => ({ ...s, simPosts: posts })), []);
  const addChatMessage = useCallback((threadId: string, role: 'user' | 'agent', content: string, sourceAgentId?: string) => {
    setState(s => ({
      ...s,
      chatHistory: {
        ...s.chatHistory,
        [threadId]: [...(s.chatHistory[threadId] || []), { role, content, agentId: sourceAgentId }],
      },
    }));
  }, []);

  const value = useMemo(() => ({
    ...state,
    setCurrentStep,
    completeStep,
    setSessionId,
    setCountry,
    setUseCase,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
    setUploadedFiles,
    addUploadedFile,
    removeUploadedFile,
    setAnalysisQuestions,
    addAnalysisQuestion,
    updateAnalysisQuestion,
    removeAnalysisQuestion,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationComplete,
    setSimPosts,
    addChatMessage,
  }), [
    state,
    setCurrentStep,
    completeStep,
    setSessionId,
    setModelProvider,
    setModelName,
    setEmbedModelName,
    setModelApiKey,
    setModelBaseUrl,
    setUploadedFiles,
    addUploadedFile,
    removeUploadedFile,
    setAnalysisQuestions,
    addAnalysisQuestion,
    updateAnalysisQuestion,
    removeAnalysisQuestion,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationComplete,
    setSimPosts,
    addChatMessage,
  ]);

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
```

- `AnalysisQuestion` type exported
- `guidingPrompts: string[]` → `analysisQuestions: AnalysisQuestion[]`
- Default use case: `public-policy-testing`

### OnboardingModal
```diff:OnboardingModal.tsx
import { useEffect, useState } from 'react';
import { ArrowRight, Cpu, Globe, Key, Target } from 'lucide-react';

import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  createV2Session,
  displayProviderId,
  displayUseCaseId,
  getV2Countries,
  getV2Providers,
  isLiveBootMode,
  normalizeProviderId,
  normalizeUseCaseId,
} from '@/lib/console-api';

type CountryCard = {
  id: string;
  name: string;
  emoji: string;
  available: boolean;
};

type ProviderCard = {
  label: string;
  models: string[];
  requiresKey: boolean;
};

const FALLBACK_COUNTRIES: CountryCard[] = [
  { id: 'singapore', name: 'Singapore', emoji: '🇸🇬', available: true },
  { id: 'usa', name: 'USA', emoji: '🇺🇸', available: true },
  { id: 'india', name: 'India', emoji: '🇮🇳', available: false },
  { id: 'japan', name: 'Japan', emoji: '🇯🇵', available: false },
];

const FALLBACK_PROVIDERS: Record<string, ProviderCard> = {
  gemini: {
    label: 'Google Gemini',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro'],
    requiresKey: true,
  },
  openai: {
    label: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    requiresKey: true,
  },
  ollama: {
    label: 'Ollama (Local)',
    models: ['qwen3:4b-instruct-2507-q4_K_M', 'llama3:8b'],
    requiresKey: false,
  },
};

const USE_CASES = [
  { id: 'policy-review', label: 'Policy Review' },
  { id: 'ad-testing', label: 'Ad Testing' },
  { id: 'pmf-discovery', label: 'PMF Discovery' },
  { id: 'reviews', label: 'Reviews' },
];

function toCountryId(code: string, name: string) {
  const normalizedCode = String(code || '').trim().toLowerCase();
  const normalizedName = String(name || '').trim().toLowerCase();
  if (normalizedCode === 'sg' || normalizedName === 'singapore') {
    return 'singapore';
  }
  if (normalizedCode === 'us' || normalizedName === 'usa') {
    return 'usa';
  }
  return normalizedCode || normalizedName;
}

function toDisplayCountry(country: string) {
  return toCountryId(country, country);
}

function toDisplayUseCase(useCase: string) {
  return displayUseCaseId(useCase) || 'policy-review';
}

function buildCountryCatalog(countries: Array<{ code: string; name: string; flag_emoji: string; available: boolean }>) {
  const catalogById = new Map<string, CountryCard>();

  for (const country of countries) {
    const id = toCountryId(country.code, country.name);
    if (!id) {
      continue;
    }

    catalogById.set(id, {
      id,
      name: country.name,
      emoji: country.flag_emoji,
      available: country.available,
    });
  }

  const merged = FALLBACK_COUNTRIES.map((fallback) => catalogById.get(fallback.id) ?? fallback);
  for (const [id, country] of catalogById.entries()) {
    if (!merged.some((item) => item.id === id)) {
      merged.push(country);
    }
  }

  return merged;
}

function buildProviderCatalog(providers: Array<{ name: string; models: string[]; requires_api_key: boolean }>) {
  const catalog: Record<string, ProviderCard> = {};
  for (const provider of providers) {
    const id = String(provider.name || '').trim().toLowerCase();
    if (!id) {
      continue;
    }
    catalog[id] = {
      label:
        id === 'gemini'
          ? 'Google Gemini'
          : id === 'openai'
            ? 'OpenAI'
            : id === 'ollama'
              ? 'Ollama (Local)'
              : provider.name,
      models: provider.models.length > 0 ? provider.models : FALLBACK_PROVIDERS[id]?.models ?? [],
      requiresKey: Boolean(provider.requires_api_key),
    };
  }
  return Object.keys(catalog).length > 0 ? catalog : FALLBACK_PROVIDERS;
}

export function OnboardingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const app = useApp();
  const liveMode = isLiveBootMode();

  const [countries, setCountries] = useState<CountryCard[]>(FALLBACK_COUNTRIES);
  const [providers, setProviders] = useState<Record<string, ProviderCard>>(liveMode ? {} : FALLBACK_PROVIDERS);
  const [country, setCountry] = useState(() => toDisplayCountry(app.country || 'singapore'));
  const [provider, setProvider] = useState(() => displayProviderId(app.modelProvider) || 'gemini');
  const [model, setModel] = useState(() => app.modelName || FALLBACK_PROVIDERS.gemini.models[0]);
  const [apiKey, setApiKey] = useState(() => app.modelApiKey || '');
  const [useCase, setUseCase] = useState(() => toDisplayUseCase(app.useCase || 'policy-review'));
  const [launchError, setLaunchError] = useState('');

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setCountry(toDisplayCountry(app.country || 'singapore'));
    setProvider(displayProviderId(app.modelProvider) || 'gemini');
    setModel(app.modelName || FALLBACK_PROVIDERS[displayProviderId(app.modelProvider) || 'gemini']?.models[0] || FALLBACK_PROVIDERS.gemini.models[0]);
    setApiKey(app.modelApiKey || '');
    setUseCase(toDisplayUseCase(app.useCase || 'policy-review'));
  }, [app.country, app.modelApiKey, app.modelName, app.modelProvider, app.useCase, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let cancelled = false;
    const loadCatalogs = async () => {
      try {
        const payload = await getV2Countries();
        if (!cancelled && payload.length > 0) {
          setCountries(buildCountryCatalog(payload));
        } else if (!cancelled && !liveMode) {
          setCountries(FALLBACK_COUNTRIES);
        }
      } catch {
        if (!cancelled && !liveMode) {
          setCountries(FALLBACK_COUNTRIES);
        }
      }

      try {
        const payload = await getV2Providers();
        if (!cancelled && payload.length > 0) {
          setProviders(buildProviderCatalog(payload));
        } else if (!cancelled && liveMode) {
          setProviders({});
          setLaunchError('Live provider catalog returned no options.');
        }
      } catch {
        if (liveMode) {
          setProviders({});
          setLaunchError('Live provider catalog is unavailable.');
        }
      }
    };

    void loadCatalogs();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    const providerCard = providers[provider];
    if (!providerCard || providerCard.models.length === 0) {
      return;
    }

    if (!providerCard.models.includes(model)) {
      setModel(providerCard.models[0]);
    }
  }, [model, provider, providers]);

  if (!isOpen) return null;

  const handleLaunch = async () => {
    const resolvedProvider = normalizeProviderId(provider);
    const resolvedUseCase = normalizeUseCaseId(useCase);
    const providerCard = providers[provider] ?? (liveMode ? undefined : FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini);
    const resolvedCountry = country || 'singapore';

    if (!providerCard || providerCard.models.length === 0) {
      setLaunchError('Select a provider and model before launching.');
      return;
    }
    const resolvedModel = model || providerCard.models[0];
    const resolvedApiKey = providerCard.requiresKey ? apiKey : '';
    if (providerCard.requiresKey && !resolvedApiKey.trim()) {
      setLaunchError('API key is required for this provider.');
      return;
    }
    if (!resolvedCountry || !resolvedModel) {
      setLaunchError('Country and model are required.');
      return;
    }

    try {
      const payload = await createV2Session({
        country: resolvedCountry,
        provider: resolvedProvider,
        model: resolvedModel,
        api_key: resolvedApiKey || undefined,
        use_case: resolvedUseCase,
      });

      app.setCountry(resolvedCountry);
      app.setModelProvider(resolvedProvider as any);
      app.setModelName(resolvedModel);
      app.setModelApiKey(resolvedApiKey);
      app.setUseCase(resolvedUseCase);
      app.setSessionId(payload.session_id);
      setLaunchError('');
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to launch simulation environment.';
      setLaunchError(message);
    }
  };

  const selectedProvider = providers[provider] ?? (!liveMode ? FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini : undefined);

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="surface-card w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="p-6 border-b border-border text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-white/5 border border-white/10 mb-4">
            <Globe className="w-6 h-6 text-foreground" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground tracking-tight">Configure Simulation</h2>
          <p className="text-sm text-muted-foreground mt-1">Select your environment parameters to spin up a new OASIS instance.</p>
        </div>

        <div className="p-6 overflow-y-auto scrollbar-thin space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Region & Dataset</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {countries.map((c) => {
                const isSelected = country === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      if (!c.available) {
                        setLaunchError('Coming soon');
                        return;
                      }

                      setLaunchError('');
                      setCountry(c.id);
                    }}
                    title={!c.available ? 'Coming soon' : undefined}
                    className={`
                      relative p-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all
                      ${c.available ? 'cursor-pointer hover:bg-white/5' : 'cursor-not-allowed opacity-40 hover:bg-white/5'}
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10' : 'border-white/10 bg-transparent'}
                    `}
                  >
                    {!c.available && (
                      <span className="absolute -top-2 text-[8px] uppercase tracking-wider font-mono bg-white/10 text-white/60 px-1.5 py-0.5 rounded">
                        Coming Soon
                      </span>
                    )}
                    <span className="text-2xl">{c.emoji}</span>
                    <span className={`text-xs font-medium ${isSelected ? 'text-[hsl(var(--data-blue))]' : 'text-foreground'}`}>
                      {c.name}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Engine</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {Object.entries(providers).map(([key, data]) => (
                    <option key={key} value={key}>
                      {data.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={!selectedProvider || selectedProvider.models.length === 0}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {(selectedProvider?.models ?? []).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {selectedProvider?.requiresKey && (
              <div className="mt-4 space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5" /> API Key
                </label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="bg-background border-border text-sm font-mono"
                />
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Use Case Template</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {USE_CASES.map((uc) => {
                const isSelected = useCase === uc.id;
                return (
                  <button
                    key={uc.id}
                    onClick={() => setUseCase(uc.id)}
                    className={`
                      px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all border
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10 text-[hsl(var(--data-blue))]' : 'border-white/10 hover:bg-white/5 text-muted-foreground'}
                    `}
                  >
                    {uc.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-border bg-[#050505]">
          <Button
            onClick={() => void handleLaunch()}
            className="w-full bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white font-medium h-12 text-sm border-0"
          >
            Launch Simulation Environment <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          {launchError && <p className="mt-2 text-xs text-destructive">{launchError}</p>}
        </div>
      </div>
    </div>
  );
}
===
import { useEffect, useState } from 'react';
import { ArrowRight, Cpu, Globe, Key, Target } from 'lucide-react';

import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  createV2Session,
  displayProviderId,
  displayUseCaseId,
  getV2Countries,
  getV2Providers,
  isLiveBootMode,
  normalizeProviderId,
  normalizeUseCaseId,
} from '@/lib/console-api';

type CountryCard = {
  id: string;
  name: string;
  emoji: string;
  available: boolean;
};

type ProviderCard = {
  label: string;
  models: string[];
  requiresKey: boolean;
};

const FALLBACK_COUNTRIES: CountryCard[] = [
  { id: 'singapore', name: 'Singapore', emoji: '🇸🇬', available: true },
  { id: 'usa', name: 'USA', emoji: '🇺🇸', available: true },
  { id: 'india', name: 'India', emoji: '🇮🇳', available: false },
  { id: 'japan', name: 'Japan', emoji: '🇯🇵', available: false },
];

const FALLBACK_PROVIDERS: Record<string, ProviderCard> = {
  gemini: {
    label: 'Google Gemini',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro'],
    requiresKey: true,
  },
  openai: {
    label: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    requiresKey: true,
  },
  ollama: {
    label: 'Ollama (Local)',
    models: ['qwen3:4b-instruct-2507-q4_K_M', 'llama3:8b'],
    requiresKey: false,
  },
};

const USE_CASES = [
  { id: 'public-policy-testing', label: 'Public Policy Testing', icon: '🏛️' },
  { id: 'product-market-research', label: 'Product & Market Research', icon: '📦' },
  { id: 'campaign-content-testing', label: 'Campaign & Content Testing', icon: '📢' },
];

function toCountryId(code: string, name: string) {
  const normalizedCode = String(code || '').trim().toLowerCase();
  const normalizedName = String(name || '').trim().toLowerCase();
  if (normalizedCode === 'sg' || normalizedName === 'singapore') {
    return 'singapore';
  }
  if (normalizedCode === 'us' || normalizedName === 'usa') {
    return 'usa';
  }
  return normalizedCode || normalizedName;
}

function toDisplayCountry(country: string) {
  return toCountryId(country, country);
}

function toDisplayUseCase(useCase: string) {
  return displayUseCaseId(useCase) || 'public-policy-testing';
}

function buildCountryCatalog(countries: Array<{ code: string; name: string; flag_emoji: string; available: boolean }>) {
  const catalogById = new Map<string, CountryCard>();

  for (const country of countries) {
    const id = toCountryId(country.code, country.name);
    if (!id) {
      continue;
    }

    catalogById.set(id, {
      id,
      name: country.name,
      emoji: country.flag_emoji,
      available: country.available,
    });
  }

  const merged = FALLBACK_COUNTRIES.map((fallback) => catalogById.get(fallback.id) ?? fallback);
  for (const [id, country] of catalogById.entries()) {
    if (!merged.some((item) => item.id === id)) {
      merged.push(country);
    }
  }

  return merged;
}

function buildProviderCatalog(providers: Array<{ name: string; models: string[]; requires_api_key: boolean }>) {
  const catalog: Record<string, ProviderCard> = {};
  for (const provider of providers) {
    const id = String(provider.name || '').trim().toLowerCase();
    if (!id) {
      continue;
    }
    catalog[id] = {
      label:
        id === 'gemini'
          ? 'Google Gemini'
          : id === 'openai'
            ? 'OpenAI'
            : id === 'ollama'
              ? 'Ollama (Local)'
              : provider.name,
      models: provider.models.length > 0 ? provider.models : FALLBACK_PROVIDERS[id]?.models ?? [],
      requiresKey: Boolean(provider.requires_api_key),
    };
  }
  return Object.keys(catalog).length > 0 ? catalog : FALLBACK_PROVIDERS;
}

export function OnboardingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const app = useApp();
  const liveMode = isLiveBootMode();

  const [countries, setCountries] = useState<CountryCard[]>(FALLBACK_COUNTRIES);
  const [providers, setProviders] = useState<Record<string, ProviderCard>>(liveMode ? {} : FALLBACK_PROVIDERS);
  const [country, setCountry] = useState(() => toDisplayCountry(app.country || 'singapore'));
  const [provider, setProvider] = useState(() => displayProviderId(app.modelProvider) || 'gemini');
  const [model, setModel] = useState(() => app.modelName || FALLBACK_PROVIDERS.gemini.models[0]);
  const [apiKey, setApiKey] = useState(() => app.modelApiKey || '');
  const [useCase, setUseCase] = useState(() => toDisplayUseCase(app.useCase || 'public-policy-testing'));
  const [launchError, setLaunchError] = useState('');

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setCountry(toDisplayCountry(app.country || 'singapore'));
    setProvider(displayProviderId(app.modelProvider) || 'gemini');
    setModel(app.modelName || FALLBACK_PROVIDERS[displayProviderId(app.modelProvider) || 'gemini']?.models[0] || FALLBACK_PROVIDERS.gemini.models[0]);
    setApiKey(app.modelApiKey || '');
    setUseCase(toDisplayUseCase(app.useCase || 'public-policy-testing'));
  }, [app.country, app.modelApiKey, app.modelName, app.modelProvider, app.useCase, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let cancelled = false;
    const loadCatalogs = async () => {
      try {
        const payload = await getV2Countries();
        if (!cancelled && payload.length > 0) {
          setCountries(buildCountryCatalog(payload));
        } else if (!cancelled && !liveMode) {
          setCountries(FALLBACK_COUNTRIES);
        }
      } catch {
        if (!cancelled && !liveMode) {
          setCountries(FALLBACK_COUNTRIES);
        }
      }

      try {
        const payload = await getV2Providers();
        if (!cancelled && payload.length > 0) {
          setProviders(buildProviderCatalog(payload));
        } else if (!cancelled && liveMode) {
          setProviders({});
          setLaunchError('Live provider catalog returned no options.');
        }
      } catch {
        if (liveMode) {
          setProviders({});
          setLaunchError('Live provider catalog is unavailable.');
        }
      }
    };

    void loadCatalogs();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    const providerCard = providers[provider];
    if (!providerCard || providerCard.models.length === 0) {
      return;
    }

    if (!providerCard.models.includes(model)) {
      setModel(providerCard.models[0]);
    }
  }, [model, provider, providers]);

  if (!isOpen) return null;

  const handleLaunch = async () => {
    const resolvedProvider = normalizeProviderId(provider);
    const resolvedUseCase = normalizeUseCaseId(useCase);
    const providerCard = providers[provider] ?? (liveMode ? undefined : FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini);
    const resolvedCountry = country || 'singapore';

    if (!providerCard || providerCard.models.length === 0) {
      setLaunchError('Select a provider and model before launching.');
      return;
    }
    const resolvedModel = model || providerCard.models[0];
    const resolvedApiKey = providerCard.requiresKey ? apiKey : '';
    if (providerCard.requiresKey && !resolvedApiKey.trim()) {
      setLaunchError('API key is required for this provider.');
      return;
    }
    if (!resolvedCountry || !resolvedModel) {
      setLaunchError('Country and model are required.');
      return;
    }

    try {
      const payload = await createV2Session({
        country: resolvedCountry,
        provider: resolvedProvider,
        model: resolvedModel,
        api_key: resolvedApiKey || undefined,
        use_case: resolvedUseCase,
      });

      app.setCountry(resolvedCountry);
      app.setModelProvider(resolvedProvider as any);
      app.setModelName(resolvedModel);
      app.setModelApiKey(resolvedApiKey);
      app.setUseCase(resolvedUseCase);
      app.setSessionId(payload.session_id);
      setLaunchError('');
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to launch simulation environment.';
      setLaunchError(message);
    }
  };

  const selectedProvider = providers[provider] ?? (!liveMode ? FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini : undefined);

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="surface-card w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="p-6 border-b border-border text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-white/5 border border-white/10 mb-4">
            <Globe className="w-6 h-6 text-foreground" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground tracking-tight">Configure Simulation</h2>
          <p className="text-sm text-muted-foreground mt-1">Select your environment parameters to spin up a new OASIS instance.</p>
        </div>

        <div className="p-6 overflow-y-auto scrollbar-thin space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Region & Dataset</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {countries.map((c) => {
                const isSelected = country === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      if (!c.available) {
                        setLaunchError('Coming soon');
                        return;
                      }

                      setLaunchError('');
                      setCountry(c.id);
                    }}
                    title={!c.available ? 'Coming soon' : undefined}
                    className={`
                      relative p-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all
                      ${c.available ? 'cursor-pointer hover:bg-white/5' : 'cursor-not-allowed opacity-40 hover:bg-white/5'}
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10' : 'border-white/10 bg-transparent'}
                    `}
                  >
                    {!c.available && (
                      <span className="absolute -top-2 text-[8px] uppercase tracking-wider font-mono bg-white/10 text-white/60 px-1.5 py-0.5 rounded">
                        Coming Soon
                      </span>
                    )}
                    <span className="text-2xl">{c.emoji}</span>
                    <span className={`text-xs font-medium ${isSelected ? 'text-[hsl(var(--data-blue))]' : 'text-foreground'}`}>
                      {c.name}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Engine</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {Object.entries(providers).map(([key, data]) => (
                    <option key={key} value={key}>
                      {data.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={!selectedProvider || selectedProvider.models.length === 0}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {(selectedProvider?.models ?? []).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {selectedProvider?.requiresKey && (
              <div className="mt-4 space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5" /> API Key
                </label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="bg-background border-border text-sm font-mono"
                />
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Use Case Template</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {USE_CASES.map((uc) => {
                const isSelected = useCase === uc.id;
                return (
                  <button
                    key={uc.id}
                    onClick={() => setUseCase(uc.id)}
                    className={`
                      px-4 py-2 rounded-full text-xs font-semibold tracking-wider transition-all border flex items-center gap-1.5
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10 text-[hsl(var(--data-blue))]' : 'border-white/10 hover:bg-white/5 text-muted-foreground'}
                    `}
                  >
                    <span>{uc.icon}</span>
                    {uc.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-border bg-[#050505]">
          <Button
            onClick={() => void handleLaunch()}
            className="w-full bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white font-medium h-12 text-sm border-0"
          >
            Launch Simulation Environment <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          {launchError && <p className="mt-2 text-xs text-destructive">{launchError}</p>}
        </div>
      </div>
    </div>
  );
}
```

- 3 V2 use cases with emoji icons

### PolicyUpload (Screen 1)
```diff:PolicyUpload.tsx
import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight, Eye, EyeOff, X, Plus, Link, Type, ChevronDown, ChevronUp } from 'lucide-react';
import { forceCollide, forceManyBody } from 'd3-force-3d';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  createConsoleSession,
  isLiveBootMode,
  processKnowledgeDocuments,
  uploadKnowledgeFile,
  scrapeKnowledgeUrl,
  KnowledgeArtifact,
} from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';

/* ─── Graph Display Constants ─── */

const DISPLAY_BUCKET_STYLES: Record<string, { label: string; color: string }> = {
  organization: { label: 'Organization', color: 'hsl(0, 0%, 62%)' },
  persons:      { label: 'Persons',      color: 'hsl(142, 50%, 50%)' },
  location:     { label: 'Location',     color: 'hsl(38, 72%, 54%)' },
  age_group:    { label: 'Age Group',    color: 'hsl(142, 48%, 50%)' },
  event:        { label: 'Event',        color: 'hsl(0, 58%, 55%)' },
  concept:      { label: 'Concept',      color: 'hsl(200, 50%, 56%)' },
  industry:     { label: 'Industry',     color: 'hsl(266, 40%, 60%)' },
  other:        { label: 'Other',        color: 'hsl(0, 0%, 47%)' },
};

const DISPLAY_BUCKET_ORDER = ['organization', 'persons', 'location', 'age_group', 'event', 'concept', 'industry', 'other'] as const;
const MIN_NODE_RADIUS = 4;
const MAX_NODE_RADIUS = 12;
const NODE_LABEL_GAP = 8;
const RELATIONSHIP_LABEL_STORAGE_KEY = 'screen1-relationship-labels';

type FamilyFilter = 'all' | 'nemotron' | 'other';
type DisplayBucket = typeof DISPLAY_BUCKET_ORDER[number];
type GraphNodeDatum = {
  id: string;
  name: string;
  type: string;
  displayBucket: string;
  facetKind?: string | null;
  families: string[];
  description?: string | null;
  summary?: string | null;
  val: number;
  renderRadius: number;
  x?: number;
  y?: number;
};
type GraphLinkDatum = {
  source: string | GraphNodeDatum;
  target: string | GraphNodeDatum;
  label: string;
  type: string;
  summary?: string | null;
};

function resolveKnowledgeExtractionError(
  error: unknown,
  context: { provider: string; model: string },
): string {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (message && message.toLowerCase() !== 'failed to fetch') {
      return message;
    }
  }

  return (
    `Could not reach the backend during extraction while using ` +
    `${context.provider}/${context.model}. ` +
    `Check that the backend is running and that the selected provider runtime is reachable.`
  );
}

function buildSafeDocumentName(rawName: string, fallback: string) {
  const trimmed = rawName.trim();
  if (!trimmed) return fallback;
  return trimmed.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-").toLowerCase();
}

function getDefaultGuidingPrompt(useCase: string) {
  const normalized = String(useCase || '').trim().toLowerCase();
  if (normalized === 'ad-testing') {
    return 'Extract key product features, target demographics, and brand positioning statements. Highlight emotional triggers and pricing constraints.';
  }
  if (normalized === 'pmf-discovery') {
    return 'Analyze this product feedback for core pain points, requested features, and user satisfaction signals. Group by user persona.';
  }
  return 'Identify all entities, locations, organizations, and the specific impact mechanisms described in this policy document. Focus strongly on sentiment and demographic effects.';
}

async function readFileText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }

  if (typeof file.arrayBuffer === "function") {
    const bytes = await file.arrayBuffer();
    return new TextDecoder().decode(bytes);
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file contents."));
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.readAsText(file);
  });
}

function isServerParsedDocument(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith('.pdf') || name.endsWith('.doc') || name.endsWith('.docx');
}

function mergeKnowledgeArtifacts(
  sessionId: string,
  artifacts: KnowledgeArtifact[],
  guidingPrompt: string | null,
): KnowledgeArtifact {
  if (artifacts.length === 0) {
    throw new Error("No knowledge artifacts were returned from extraction.");
  }
  if (artifacts.length === 1) {
    return {
      ...artifacts[0],
      session_id: sessionId,
      guiding_prompt: guidingPrompt,
    };
  }

  const nodes: KnowledgeArtifact["entity_nodes"] = [];
  const edges: KnowledgeArtifact["relationship_edges"] = [];
  const logs: string[] = [];
  const summaries: string[] = [];
  const sourceDocuments = artifacts.map((artifact) => artifact.document);
  const seenNodes = new Set<string>();
  const seenEdges = new Set<string>();

  for (const artifact of artifacts) {
    const summary = String(artifact.summary || "").trim();
    if (summary) summaries.push(summary);

    for (const node of artifact.entity_nodes || []) {
      const key = String(node.id || node.label || "").trim().toLowerCase();
      if (!key || seenNodes.has(key)) continue;
      seenNodes.add(key);
      nodes.push(node);
    }

    for (const edge of artifact.relationship_edges || []) {
      const key = [
        String(edge.source || "").trim().toLowerCase(),
        String(edge.target || "").trim().toLowerCase(),
        String(edge.type || "").trim().toLowerCase(),
        String(edge.label || "").trim().toLowerCase(),
      ].join("|");
      if (!key || seenEdges.has(key)) continue;
      seenEdges.add(key);
      edges.push(edge);
    }

    for (const logLine of artifact.processing_logs || []) {
      const line = String(logLine || "").trim();
      if (line) logs.push(line);
    }
  }

  return {
    session_id: sessionId,
    document: {
      document_id: `merged-${artifacts.length}-documents`,
      source_path: "merged://knowledge-documents",
      file_name: "merged-documents",
      text_length: sourceDocuments.reduce((total, doc) => total + Number(doc?.text_length ?? 0), 0),
      paragraph_count: sourceDocuments.reduce((total, doc) => total + Number(doc?.paragraph_count ?? 0), 0),
    },
    summary: summaries.join("\n\n"),
    guiding_prompt: guidingPrompt,
    entity_nodes: nodes,
    relationship_edges: edges,
    entity_type_counts: nodes.reduce<Record<string, number>>((counts, node) => {
      const type = String(node.type || "unknown");
      counts[type] = (counts[type] || 0) + 1;
      return counts;
    }, {}),
    processing_logs: logs,
    demographic_focus_summary: artifacts[0]?.demographic_focus_summary ?? null,
  };
}

/* ─── Main Component ─── */

export default function PolicyUpload() {
  const {
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    useCase,
    uploadedFiles,
    guidingPrompts,
    knowledgeGraphReady,
    knowledgeArtifact,
    knowledgeLoading,
    knowledgeError,
    setSessionId,
    addUploadedFile,
    removeUploadedFile,
    setUploadedFiles,
    setGuidingPrompts,
    updateGuidingPrompt,
    addGuidingPrompt,
    removeGuidingPrompt,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    completeStep,
    setCurrentStep,
  } = useApp();

  const [dragOver, setDragOver] = useState(false);
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 400 });
  const [familyFilter, setFamilyFilter] = useState<FamilyFilter>('all');
  const [activeBuckets, setActiveBuckets] = useState<DisplayBucket[]>([]);
  const [showRelationshipLabels, setShowRelationshipLabels] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.sessionStorage.getItem(RELATIONSHIP_LABEL_STORAGE_KEY) === 'on';
  });
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlValue, setUrlValue] = useState('');
  const [showPasteArea, setShowPasteArea] = useState(false);
  const [pasteValue, setPasteValue] = useState('');
  const [showTopEntities, setShowTopEntities] = useState(true);

  const graphReady = knowledgeGraphReady && knowledgeArtifact !== null;

  useEffect(() => {
    if (guidingPrompts.length === 1 && guidingPrompts[0].trim() === '') {
      setGuidingPrompts([getDefaultGuidingPrompt(useCase)]);
    }
  }, [guidingPrompts, setGuidingPrompts, useCase]);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(RELATIONSHIP_LABEL_STORAGE_KEY, showRelationshipLabels ? 'on' : 'off');
    }
  }, [showRelationshipLabels]);

  const familyScopedNodes = graphReady
    ? knowledgeArtifact.entity_nodes.filter(
        (node) => !node.ui_default_hidden && matchesFamilyFilter(node.facet_kind, familyFilter),
      )
    : [];

  const availableBuckets: DisplayBucket[] = graphReady
    ? DISPLAY_BUCKET_ORDER.filter((bucket) => familyScopedNodes.some((node) => resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket) === bucket))
    : [];

  useEffect(() => {
    if (!graphReady) {
      setFamilyFilter((current) => (current === 'all' ? current : 'all'));
      setActiveBuckets((current) => (current.length === 0 ? current : []));
      return;
    }

    setActiveBuckets((current) => {
      const next = current.filter((bucket) => availableBuckets.includes(bucket));
      const resolved = next.length > 0 ? next : availableBuckets;
      return sameStringArray(current, resolved) ? current : resolved;
    });
  }, [availableBuckets, graphReady]);

  const resetKnowledgeState = useCallback(() => {
    setKnowledgeGraphReady(false);
    setKnowledgeArtifact(null);
    setKnowledgeError(null);
  }, [setKnowledgeArtifact, setKnowledgeError, setKnowledgeGraphReady]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach((f) => addUploadedFile(f));
    resetKnowledgeState();
  }, [resetKnowledgeState, addUploadedFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach((f) => addUploadedFile(f));
    resetKnowledgeState();
  }, [resetKnowledgeState, addUploadedFile]);

  const ensureSession = useCallback(async () => {
    if (sessionId) {
      return sessionId;
    }

    const created = await createConsoleSession(undefined, {
      model_provider: modelProvider,
      model_name: modelName,
      embed_model_name: embedModelName,
      api_key: modelApiKey.trim() || undefined,
      base_url: modelBaseUrl.trim() || undefined,
    });
    setSessionId(created.session_id);
    return created.session_id;
  }, [
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    modelName,
    modelProvider,
    sessionId,
    setSessionId,
  ]);

  const handleExtract = useCallback(async () => {
    if (uploadedFiles.length === 0) return;

    try {
      setKnowledgeLoading(true);
      setKnowledgeError(null);

      const resolvedSessionId = await ensureSession();
      const combinedPrompt = guidingPrompts.map((prompt) => prompt.trim()).filter(Boolean).join('\n\n');
      const serverParsedFiles = uploadedFiles.filter(isServerParsedDocument);
      const textFiles = uploadedFiles.filter((file) => !isServerParsedDocument(file));
      const artifacts: KnowledgeArtifact[] = [];

      if (textFiles.length > 0) {
        const documents = await Promise.all(
          textFiles.map(async (file) => ({
            document_text: await readFileText(file),
            source_path: file.name,
          })),
        );
        artifacts.push(
          await processKnowledgeDocuments(resolvedSessionId, {
            documents,
            guiding_prompt: combinedPrompt || undefined,
          }),
        );
      }

      for (const file of serverParsedFiles) {
        artifacts.push(
          await uploadKnowledgeFile(
            resolvedSessionId,
            file,
            combinedPrompt || undefined,
          ),
        );
      }

      const artifact = mergeKnowledgeArtifacts(resolvedSessionId, artifacts, combinedPrompt || null);
      setKnowledgeArtifact(artifact);
      setKnowledgeGraphReady(true);
    } catch (error) {
      if (!isLiveBootMode()) {
        try {
          // Demo mode can still hydrate from the bundled demo artifact.
          const demoRes = await fetch('/demo-output.json');
          if (demoRes.ok) {
            const demo = await demoRes.json();
            const knowledgeData = demo.knowledge;
            if (knowledgeData?.entity_nodes) {
              const artifact = {
                session_id: knowledgeData.simulation_id || 'demo-session',
                document: knowledgeData.document || { document_id: 'demo', paragraph_count: 0 },
                summary: knowledgeData.summary || '',
                guiding_prompt: knowledgeData.guiding_prompt || null,
                entity_nodes: knowledgeData.entity_nodes,
                relationship_edges: knowledgeData.relationship_edges || [],
                entity_type_counts: knowledgeData.entity_type_counts || {},
                processing_logs: [],
                demographic_focus_summary: knowledgeData.demographic_focus_summary || null,
              } as KnowledgeArtifact;
              setKnowledgeArtifact(artifact);
              setKnowledgeGraphReady(true);
              setSessionId(artifact.session_id);
              toast({ title: 'Demo mode', description: 'Loaded cached knowledge graph (backend unavailable)' });
              return;
            }
          }
        } catch { /* ignore demo fallback errors */ }
      }

      const message = resolveKnowledgeExtractionError(error, {
        provider: modelProvider,
        model: modelName,
      });
      setKnowledgeGraphReady(false);
      setKnowledgeArtifact(null);
      setKnowledgeError(message);
      toast({
        title: 'Knowledge extraction failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setKnowledgeLoading(false);
    }
  }, [
    uploadedFiles,
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    guidingPrompts,
    setKnowledgeLoading,
    setKnowledgeError,
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    ensureSession,
  ]);

  const handleProceed = () => {
    completeStep(1);
    setCurrentStep(2);
  };

  const handleUrlScrape = useCallback(async () => {
    const url = urlValue.trim();
    if (!url) return;

    try {
      const resolvedSessionId = await ensureSession();
      const scraped = await scrapeKnowledgeUrl(resolvedSessionId, url);
      const fileName = `${buildSafeDocumentName(scraped.title || 'scraped-document', 'scraped-document')}.txt`;
      const scrapedFile = new File([scraped.text || url], fileName, { type: 'text/plain' });
      addUploadedFile(scrapedFile);
      resetKnowledgeState();
      toast({ title: 'URL scraped', description: scraped.title ? scraped.title : `Fetched content from ${url}` });
    } catch (error) {
      resetKnowledgeState();
      const message = error instanceof Error ? error.message : 'Backend scrape failed.';
      if (!isLiveBootMode()) {
        const fallbackName = `${buildSafeDocumentName(url, 'scraped-document')}.txt`;
        const fallbackFile = new File([url], fallbackName, { type: 'text/plain' });
        addUploadedFile(fallbackFile);
        toast({
          title: 'URL scrape fallback',
          description: `${message} Queued URL as text.`,
        });
        return;
      }

      setKnowledgeError(message);
      toast({
        title: 'URL scrape failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setUrlValue('');
      setShowUrlInput(false);
    }
  }, [addUploadedFile, ensureSession, resetKnowledgeState, setKnowledgeError, setShowUrlInput, setUrlValue, urlValue]);

  const handlePasteSubmit = useCallback(() => {
    const text = pasteValue.trim();
    if (!text) return;

    const blob = new Blob([text], { type: 'text/plain' });
    const mockFile = new File([blob], 'pasted-text.txt', { type: 'text/plain' });
    addUploadedFile(mockFile);
    resetKnowledgeState();
    setPasteValue('');
    setShowPasteArea(false);
    toast({ title: 'Text added', description: 'Pasted content queued for backend extraction' });
  }, [addUploadedFile, pasteValue, resetKnowledgeState, setPasteValue, setShowPasteArea]);

  /* ─── Graph Data ─── */

  const filteredSourceNodes = graphReady
    ? familyScopedNodes.filter((node) => {
        const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
        return activeBuckets.length === 0 ? true : activeBuckets.includes(bucket);
      })
    : [];

  const filteredNodeIds = new Set(filteredSourceNodes.map((node) => node.id));

  const graphData = graphReady ? {
    nodes: filteredSourceNodes.map((node) => ({
      id: node.id,
      name: node.label,
      type: normalizeNodeType(node.type),
      displayBucket: resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket),
      facetKind: node.facet_kind,
      families: node.families ?? ['document'],
      description: node.summary || node.description,
      summary: node.summary || node.description,
      val: normalizeImportance(node.importance_score, node.weight),
      renderRadius: radiusFromImportance(node.importance_score, node.weight),
    })),
    links: knowledgeArtifact.relationship_edges
      .filter((edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target))
      .map((edge) => ({
        ...edge,
        label: edge.label || edge.raw_relation_text || edge.type,
        summary: edge.summary || edge.raw_relation_text || edge.label || edge.type,
      })),
  } : { nodes: [], links: [] };

  useEffect(() => {
    if (!graphReady || graphData.nodes.length === 0 || !graphRef.current?.d3Force) return;

    const maxRadius = Math.max(...graphData.nodes.map((node) => node.renderRadius), MIN_NODE_RADIUS);
    graphRef.current.d3Force('charge', forceManyBody().strength(-(150 + maxRadius * 18)));
    graphRef.current.d3Force('collide', forceCollide((node: GraphNodeDatum) => node.renderRadius + 30).iterations(2));

    const linkForce = graphRef.current.d3Force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
      linkForce.distance((link: { source: GraphNodeDatum; target: GraphNodeDatum }) => {
        const sourceRadius = link.source?.renderRadius ?? MIN_NODE_RADIUS;
        const targetRadius = link.target?.renderRadius ?? MIN_NODE_RADIUS;
        return Math.max(110, (sourceRadius + targetRadius) * 8);
      });
    }
    graphRef.current.d3ReheatSimulation?.();
  }, [graphData.links, graphData.nodes, graphReady]);

  const legendEntries = graphReady
    ? Array.from(
        new Map(
          graphData.nodes.map((node: GraphNodeDatum) => {
            const style = DISPLAY_BUCKET_STYLES[node.displayBucket] ?? DISPLAY_BUCKET_STYLES.other;
            return [`${style.label}:${style.color}`, style] as const;
          }),
        ).values(),
      )
    : [];

  const topEntities = graphReady
    ? [...knowledgeArtifact.entity_nodes]
      .filter((node) => !node.ui_default_hidden)
      .sort((left, right) => {
        const rightImportance = normalizeImportance(right.importance_score, right.weight);
        const leftImportance = normalizeImportance(left.importance_score, left.weight);
        if (rightImportance !== leftImportance) return rightImportance - leftImportance;
        return (right.support_count ?? 0) - (left.support_count ?? 0);
      })
      .slice(0, 3)
    : [];

  const nodeColor = (node: { type?: string; displayBucket?: string; facetKind?: string }) => {
    return (DISPLAY_BUCKET_STYLES[node.displayBucket || resolveDisplayBucket(node.type, node.facetKind)] ?? DISPLAY_BUCKET_STYLES.other).color;
  };

  /* ─── Render ─── */

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-0 h-full">
      {/* ───── LEFT PANEL ───── */}
      <div className="flex flex-col border-r border-border overflow-y-auto scrollbar-thin bg-background">
        {/* Header */}
        <div className="p-5 pb-4 border-b border-border">
          <h2 className="text-lg font-bold text-foreground font-mono uppercase tracking-wider">NEW SIMULATION RUN</h2>
          <p className="text-xs text-muted-foreground mt-1">Upload unstructured documents to build the context graph</p>
          {/* Use-case badge */}
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-border bg-transparent text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
              {modelProvider === 'gemini' ? 'Gemini 2.0' : modelProvider} · Document Processing
            </span>
          </div>
        </div>

        {/* Upload Zone */}
        <div className="p-5 border-b border-border">
          <label
            className={`flex flex-col items-center justify-center p-6 cursor-pointer transition-colors border border-dashed rounded-lg bg-transparent ${
              dragOver ? 'border-white/40 bg-white/[0.03]' : uploadedFiles.length > 0 ? 'border-border' : 'border-border hover:border-white/25'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input type="file" className="hidden" accept=".pdf,.docx,.doc,.txt,.md,.markdown,.html,.htm,.json,.csv,.yaml,.yml" multiple onChange={handleFileSelect} />
            <Upload className="w-6 h-6 text-muted-foreground mb-2" />
            <span className="text-sm text-foreground">Drop documents here</span>
            <span className="text-[10px] text-muted-foreground mt-1 font-mono uppercase tracking-wider">
              PDF · DOCX · TXT · MD · HTML · CSV · YAML
            </span>
          </label>

          {/* File list */}
          {uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-1">
              {uploadedFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="rounded bg-card border border-border group px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                      <span className="text-sm text-foreground truncate">{file.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-muted-foreground">{formatFileSize(file.size)}</span>
                      <button
                        type="button"
                        onClick={() => { removeUploadedFile(index); resetKnowledgeState(); }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  {knowledgeLoading && (
                    <div className="mt-2">
                      <Progress
                        value={50}
                        aria-label={`${file.name} upload progress`}
                        className="h-1.5 bg-white/5"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Alt input methods */}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setShowUrlInput(!showUrlInput)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showUrlInput ? 'border-white/20 bg-white/5 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-white/15'
              }`}
            >
              <Link className="w-3 h-3" /> URL
            </button>
            <button
              type="button"
              onClick={() => setShowPasteArea(!showPasteArea)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showPasteArea ? 'border-white/20 bg-white/5 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-white/15'
              }`}
            >
              <Type className="w-3 h-3" /> Paste
            </button>
          </div>

          {/* URL scraper */}
          {showUrlInput && (
            <div className="mt-2 flex gap-2 animate-slide-up">
              <Input
                value={urlValue}
                onChange={(e) => setUrlValue(e.target.value)}
                placeholder="https://example.com/policy-doc"
                className="text-sm bg-card border-border"
              />
              <Button onClick={handleUrlScrape} size="sm" variant="outline" className="shrink-0 border-border text-foreground">
                Scrape
              </Button>
            </div>
          )}

          {/* Paste text */}
          {showPasteArea && (
            <div className="mt-2 space-y-2 animate-slide-up">
              <Textarea
                value={pasteValue}
                onChange={(e) => setPasteValue(e.target.value)}
                placeholder="Paste document text here..."
                className="text-sm bg-card border-border min-h-[80px] resize-none"
              />
              <Button onClick={handlePasteSubmit} size="sm" variant="outline" className="border-border text-foreground">
                Add as Document
              </Button>
            </div>
          )}
        </div>

        {/* Guiding Prompts */}
        <div className="p-5 border-b border-border">
          <div className="flex items-center justify-between mb-3">
            <span className="label-meta">Guiding Prompts</span>
            <div className="flex items-center gap-3">
              <select
                className="bg-transparent border border-border text-[10px] text-muted-foreground uppercase tracking-widest px-2 py-1 rounded cursor-pointer hover:text-foreground"
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'policy') updateGuidingPrompt(0, "Identify all entities, locations, organizations, and the specific impact mechanisms described in this policy document. Focus strongly on sentiment and demographic effects.");
                  if (val === 'ad') updateGuidingPrompt(0, "Extract key product features, target demographics, and brand positioning statements. Highlight emotional triggers and pricing constraints.");
                  if (val === 'pmf') updateGuidingPrompt(0, "Analyze this product feedback for core pain points, requested features, and user satisfaction signals. Group by user persona.");
                }}
              >
                <option value="policy">Policy Review</option>
                <option value="ad">Ad Testing</option>
                <option value="pmf">PMF Discovery</option>
              </select>
              <button
                type="button"
                onClick={addGuidingPrompt}
                className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
              >
                <Plus className="w-3 h-3" /> Add Prompt
              </button>
            </div>
          </div>
          <div className="space-y-3">
            {guidingPrompts.map((prompt, index) => (
              <div key={index} className="relative group">
                <Textarea
                  value={prompt}
                  onChange={(e) => updateGuidingPrompt(index, e.target.value)}
                  placeholder={index === 0 ? 'What should the system extract from this document?' : 'Additional extraction guidance...'}
                  className={`text-sm bg-card border-border ${index === 0 ? 'min-h-[132px]' : 'min-h-[104px]'} resize-y pr-8`}
                />
                {guidingPrompts.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeGuidingPrompt(index)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="p-5 border-b border-border">
          <div className="flex gap-2">
            <Button
              onClick={handleExtract}
              disabled={uploadedFiles.length === 0 || knowledgeLoading}
              className="flex-1 bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white border-0 font-medium font-mono uppercase tracking-wider text-xs h-10"
            >
              {knowledgeLoading ? (
                "Processing..."
              ) : (
                <><Sparkles className="w-3.5 h-3.5 mr-2" /> Start Extraction</>
              )}
            </Button>
            {graphReady && (
              <Button
                onClick={handleProceed}
                variant="outline"
                className="h-10 border border-success/30 bg-success/20 px-4 font-mono text-xs uppercase tracking-wider text-success hover:bg-success/30"
              >
                Proceed <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>
          {knowledgeError && (
            <p className="text-xs text-destructive mt-2 font-mono uppercase">{knowledgeError}</p>
          )}

          {/* Fake Loading Log */}
          {knowledgeLoading && (
            <div className="mt-4 p-3 border border-border bg-black rounded font-mono text-[10px] text-muted-foreground w-full space-y-1">
              <div className="animate-pulse-subtle flex justify-between">
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Initializing graph builder...</span>
                <span className="text-success">OK</span>
              </div>
              <div className="animate-pulse-subtle flex justify-between" style={{ animationDelay: '0.4s' }}>
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Parsing uploaded documents...</span>
                <span className="text-success">OK</span>
              </div>
              <div className="animate-pulse-subtle flex justify-between" style={{ animationDelay: '0.8s' }}>
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Chunking & computing embeddings...</span>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        {graphReady && (
          <div className="p-5 border-b border-border">
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Entities" value={knowledgeArtifact.entity_nodes.length} />
              <Stat label="Relations" value={knowledgeArtifact.relationship_edges.length} />
              <Stat label="Paragraphs" value={knowledgeArtifact.document.paragraph_count ?? 0} />
            </div>
          </div>
        )}

        {/* Top Entities — collapsible */}
        {graphReady && (
          <div className="p-5">
            <button
              type="button"
              onClick={() => setShowTopEntities(!showTopEntities)}
              className="flex items-center justify-between w-full mb-3"
            >
              <span className="label-meta">Top Entities</span>
              {showTopEntities ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
            </button>
            {showTopEntities && (
              <div className="space-y-3 animate-slide-up">
                {topEntities.map((node) => {
                  const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
                  const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                  return (
                    <div key={node.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: style.color }} />
                          <span className="truncate text-sm text-foreground">{node.label}</span>
                        </div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground ml-4">{style.label}</div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-mono text-foreground">{normalizeImportance(node.importance_score, node.weight).toFixed(2)}</div>
                        <div className="text-[10px] font-mono text-muted-foreground">×{node.support_count ?? 0}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ───── RIGHT PANEL — KNOWLEDGE GRAPH ───── */}
      <div className="flex flex-col bg-background">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h3 className="text-sm font-medium text-foreground">Knowledge Graph</h3>
        </div>

        {graphReady && (
          <div className="px-5 py-2.5 border-b border-border space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SegmentedControl
                value={familyFilter}
                options={[
                  { value: 'all', label: 'All' },
                  { value: 'nemotron', label: 'Nemotron' },
                  { value: 'other', label: 'Other' },
                ]}
                onChange={(nextValue) => setFamilyFilter(nextValue as FamilyFilter)}
              />
              <button
                type="button"
                onClick={() => setShowRelationshipLabels((current) => !current)}
                className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                  showRelationshipLabels
                    ? 'border-white/20 bg-white/5 text-foreground'
                    : 'border-border text-muted-foreground hover:border-white/15 hover:text-foreground'
                }`}
              >
                {showRelationshipLabels ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                Labels
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {availableBuckets.map((bucket) => {
                const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                const isActive = activeBuckets.includes(bucket);
                return (
                  <FilterChip
                    key={bucket}
                    active={isActive}
                    label={style.label}
                    accent={style.color}
                    onClick={() => {
                      setActiveBuckets((current) => (
                        current.length === availableBuckets.length
                          ? [bucket]
                          : current.includes(bucket)
                            ? (current.filter((value) => value !== bucket).length > 0
                              ? current.filter((value) => value !== bucket)
                              : availableBuckets)
                            : [...current, bucket]
                      ));
                    }}
                  />
                );
              })}
            </div>
          </div>
        )}

        <div ref={containerRef} className="flex-1 min-h-[300px] overflow-hidden">
          {graphReady && graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              enableNodeDrag
              nodeLabel={(node: GraphNodeDatum) => `${node.name || ''}${node.summary ? `: ${node.summary}` : ''}`}
              linkLabel={(link: GraphLinkDatum) => {
                const summary = link.summary?.trim();
                if (!summary) return link.label || '';
                return `${link.label}: ${summary}`;
              }}
              nodeColor={nodeColor}
              nodeRelSize={1}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={(node: GraphNodeDatum, ctx, globalScale) => {
                if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

                const radius = node.renderRadius || radiusFromNormalizedValue(node.val);
                const label = node.name || '';
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px "Space Grotesk", sans-serif`;
                const labelX = node.x + radius + NODE_LABEL_GAP;
                const labelY = node.y;
                const labelWidth = ctx.measureText(label).width;
                const backgroundX = labelX - 4;
                const backgroundY = labelY - fontSize / 2 - 3;
                const backgroundWidth = labelWidth + 8;
                const backgroundHeight = fontSize + 6;

                ctx.save();
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = nodeColor(node);
                ctx.fill();

                ctx.lineWidth = 1;
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                ctx.stroke();

                ctx.fillStyle = 'rgba(10, 10, 10, 0.85)';
                ctx.fillRect(backgroundX, backgroundY, backgroundWidth, backgroundHeight);

                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                ctx.fillText(label, labelX, labelY);
                ctx.restore();
              }}
              linkCanvasObjectMode={() => 'after'}
              linkCanvasObject={(link: GraphLinkDatum, ctx, globalScale) => {
                if (!showRelationshipLabels) return;
                const label = (link.label || link.type || '').trim();
                const source = typeof link.source === 'string' ? undefined : link.source;
                const target = typeof link.target === 'string' ? undefined : link.target;
                if (!label || typeof source?.x !== 'number' || typeof source?.y !== 'number' || typeof target?.x !== 'number' || typeof target?.y !== 'number') return;

                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const length = Math.hypot(dx, dy) || 1;
                const normalX = -dy / length;
                const normalY = dx / length;
                const readableLabel = shortenLabel(label, Math.max(12, Math.floor(length / 8)));
                const fontSize = Math.max(8.5, 10.5 / globalScale);
                ctx.font = `${fontSize}px "Space Mono", monospace`;
                const textWidth = ctx.measureText(readableLabel).width;
                const boxWidth = textWidth + 12;
                const boxHeight = fontSize + 8;
                const offset = Math.min(22, Math.max(10, length * 0.08));

                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(10, 10, 10, 0.88)';
                ctx.fillRect(
                  midX + normalX * offset - boxWidth / 2,
                  midY + normalY * offset - boxHeight / 2,
                  boxWidth,
                  boxHeight,
                );
                ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                ctx.fillText(readableLabel, midX + normalX * offset, midY + normalY * offset);
                ctx.restore();
              }}
              linkColor={() => 'rgba(255, 255, 255, 0.08)'}
              linkWidth={1}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              backgroundColor="transparent"
              cooldownTicks={80}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {knowledgeLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                  <span className="font-mono text-xs uppercase tracking-wider">Building graph...</span>
                </div>
              ) : graphReady ? (
                'No nodes match the current filters'
              ) : (
                <div className="text-center max-w-xs">
                  <div className="text-muted-foreground/40 mb-2">
                    <Upload className="w-8 h-8 mx-auto" />
                  </div>
                  <p className="text-sm text-muted-foreground">Upload a document to generate the knowledge graph</p>
                  <p className="text-[10px] font-mono text-muted-foreground/50 mt-1 uppercase tracking-wider">Interactive Force Graph · Drag nodes to explore</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-mono font-medium text-foreground tracking-tight">{value}</div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.18em]">{label}</div>
    </div>
  );
}

function FilterChip({ active, label, onClick, accent }: { active: boolean; label: string; onClick: () => void; accent?: string; }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
        active
          ? 'border-white/20 bg-white/8 text-foreground'
          : 'border-border text-muted-foreground hover:border-white/15 hover:text-foreground'
      }`}
    >
      <span className="flex items-center gap-1.5">
        {accent && <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accent, opacity: active ? 1 : 0.5 }} />}
        {label}
      </span>
    </button>
  );
}

function SegmentedControl({ value, options, onChange }: { value: string; options: Array<{ value: string; label: string }>; onChange: (value: string) => void; }) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded border border-border bg-card p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded px-3 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            option.value === value
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ─── Utilities ─── */

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function normalizeNodeType(type?: string) {
  const normalized = (type || 'other').trim().toLowerCase();
  if (normalized === 'institution' || normalized === 'org') return 'organization';
  if (normalized === 'demographic') return 'population';
  if (normalized === 'planning_area') return 'location';
  return normalized || 'other';
}

function normalizeImportance(importanceScore?: number | null, weight?: number | null) {
  const base = importanceScore ?? weight ?? 0.35;
  return Math.max(0, Math.min(1, Number.isFinite(base) ? Number(base) : 0.35));
}

function radiusFromImportance(importanceScore?: number | null, weight?: number | null) {
  const importance = normalizeImportance(importanceScore, weight);
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * importance));
}

function radiusFromNormalizedValue(value?: number | null) {
  const importance = Math.max(0, Math.min(1, Number.isFinite(value) ? Number(value) : 0));
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * importance));
}

function matchesFamilyFilter(facetKind?: string | null, familyFilter: FamilyFilter = 'all') {
  if (familyFilter === 'all') return true;
  const isNemotronEntity = Boolean((facetKind || '').trim());
  return familyFilter === 'nemotron' ? isNemotronEntity : !isNemotronEntity;
}

function resolveDisplayBucket(type?: string, facetKind?: string | null, explicitBucket?: string | null): DisplayBucket {
  const normalizedExplicit = (explicitBucket || '').trim().toLowerCase();
  if (normalizedExplicit && normalizedExplicit in DISPLAY_BUCKET_STYLES) return normalizedExplicit as DisplayBucket;

  const normalizedFacet = (facetKind || '').trim().toLowerCase();
  if (normalizedFacet === 'age_cohort') return 'age_group';
  if (normalizedFacet === 'industry') return 'industry';

  const normalizedType = normalizeNodeType(type);
  if (['organization', 'institution'].includes(normalizedType)) return 'organization';
  if (['person', 'population', 'stakeholder', 'demographic', 'group'].includes(normalizedType)) return 'persons';
  if (['location', 'planning_area'].includes(normalizedType)) return 'location';
  if (normalizedType === 'event') return 'event';
  if (['concept', 'policy', 'program', 'topic', 'law', 'service', 'funding'].includes(normalizedType)) return 'concept';
  if (normalizedType === 'industry') return 'industry';
  return 'other';
}

function shortenLabel(label: string, maxLength: number) {
  if (label.length <= maxLength) return label;
  return `${label.slice(0, Math.max(6, maxLength - 1))}…`;
}

function sameStringArray(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}
===
import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight, Eye, EyeOff, X, Plus, Link, Type, ChevronDown, ChevronUp } from 'lucide-react';
import { forceCollide, forceManyBody } from 'd3-force-3d';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp, AnalysisQuestion } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  createConsoleSession,
  isLiveBootMode,
  processKnowledgeDocuments,
  uploadKnowledgeFile,
  scrapeKnowledgeUrl,
  KnowledgeArtifact,
} from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';

/* ─── Graph Display Constants ─── */

const DISPLAY_BUCKET_STYLES: Record<string, { label: string; color: string }> = {
  organization: { label: 'Organization', color: 'hsl(0, 0%, 62%)' },
  persons:      { label: 'Persons',      color: 'hsl(142, 50%, 50%)' },
  location:     { label: 'Location',     color: 'hsl(38, 72%, 54%)' },
  age_group:    { label: 'Age Group',    color: 'hsl(142, 48%, 50%)' },
  event:        { label: 'Event',        color: 'hsl(0, 58%, 55%)' },
  concept:      { label: 'Concept',      color: 'hsl(200, 50%, 56%)' },
  industry:     { label: 'Industry',     color: 'hsl(266, 40%, 60%)' },
  other:        { label: 'Other',        color: 'hsl(0, 0%, 47%)' },
};

const DISPLAY_BUCKET_ORDER = ['organization', 'persons', 'location', 'age_group', 'event', 'concept', 'industry', 'other'] as const;
const MIN_NODE_RADIUS = 4;
const MAX_NODE_RADIUS = 12;
const NODE_LABEL_GAP = 8;
const RELATIONSHIP_LABEL_STORAGE_KEY = 'screen1-relationship-labels';

type FamilyFilter = 'all' | 'nemotron' | 'other';
type DisplayBucket = typeof DISPLAY_BUCKET_ORDER[number];
type GraphNodeDatum = {
  id: string;
  name: string;
  type: string;
  displayBucket: string;
  facetKind?: string | null;
  families: string[];
  description?: string | null;
  summary?: string | null;
  val: number;
  renderRadius: number;
  x?: number;
  y?: number;
};
type GraphLinkDatum = {
  source: string | GraphNodeDatum;
  target: string | GraphNodeDatum;
  label: string;
  type: string;
  summary?: string | null;
};

function resolveKnowledgeExtractionError(
  error: unknown,
  context: { provider: string; model: string },
): string {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (message && message.toLowerCase() !== 'failed to fetch') {
      return message;
    }
  }

  return (
    `Could not reach the backend during extraction while using ` +
    `${context.provider}/${context.model}. ` +
    `Check that the backend is running and that the selected provider runtime is reachable.`
  );
}

function buildSafeDocumentName(rawName: string, fallback: string) {
  const trimmed = rawName.trim();
  if (!trimmed) return fallback;
  return trimmed.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-").toLowerCase();
}

function getDefaultSystemPrompt(useCase: string) {
  const normalized = String(useCase || '').trim().toLowerCase();
  if (normalized === 'campaign-content-testing') {
    return 'Extract key product features, target demographics, and brand positioning statements. Highlight emotional triggers and pricing constraints.';
  }
  if (normalized === 'product-market-research') {
    return 'Analyze this product feedback for core pain points, requested features, and user satisfaction signals. Group by user persona.';
  }
  return 'Identify all entities, locations, organizations, and the specific impact mechanisms described in this policy document. Focus strongly on sentiment and demographic effects.';
}

async function readFileText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }

  if (typeof file.arrayBuffer === "function") {
    const bytes = await file.arrayBuffer();
    return new TextDecoder().decode(bytes);
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file contents."));
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.readAsText(file);
  });
}

function isServerParsedDocument(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith('.pdf') || name.endsWith('.doc') || name.endsWith('.docx');
}

function mergeKnowledgeArtifacts(
  sessionId: string,
  artifacts: KnowledgeArtifact[],
  guidingPrompt: string | null,
): KnowledgeArtifact {
  if (artifacts.length === 0) {
    throw new Error("No knowledge artifacts were returned from extraction.");
  }
  if (artifacts.length === 1) {
    return {
      ...artifacts[0],
      session_id: sessionId,
      guiding_prompt: guidingPrompt,
    };
  }

  const nodes: KnowledgeArtifact["entity_nodes"] = [];
  const edges: KnowledgeArtifact["relationship_edges"] = [];
  const logs: string[] = [];
  const summaries: string[] = [];
  const sourceDocuments = artifacts.map((artifact) => artifact.document);
  const seenNodes = new Set<string>();
  const seenEdges = new Set<string>();

  for (const artifact of artifacts) {
    const summary = String(artifact.summary || "").trim();
    if (summary) summaries.push(summary);

    for (const node of artifact.entity_nodes || []) {
      const key = String(node.id || node.label || "").trim().toLowerCase();
      if (!key || seenNodes.has(key)) continue;
      seenNodes.add(key);
      nodes.push(node);
    }

    for (const edge of artifact.relationship_edges || []) {
      const key = [
        String(edge.source || "").trim().toLowerCase(),
        String(edge.target || "").trim().toLowerCase(),
        String(edge.type || "").trim().toLowerCase(),
        String(edge.label || "").trim().toLowerCase(),
      ].join("|");
      if (!key || seenEdges.has(key)) continue;
      seenEdges.add(key);
      edges.push(edge);
    }

    for (const logLine of artifact.processing_logs || []) {
      const line = String(logLine || "").trim();
      if (line) logs.push(line);
    }
  }

  return {
    session_id: sessionId,
    document: {
      document_id: `merged-${artifacts.length}-documents`,
      source_path: "merged://knowledge-documents",
      file_name: "merged-documents",
      text_length: sourceDocuments.reduce((total, doc) => total + Number(doc?.text_length ?? 0), 0),
      paragraph_count: sourceDocuments.reduce((total, doc) => total + Number(doc?.paragraph_count ?? 0), 0),
    },
    summary: summaries.join("\n\n"),
    guiding_prompt: guidingPrompt,
    entity_nodes: nodes,
    relationship_edges: edges,
    entity_type_counts: nodes.reduce<Record<string, number>>((counts, node) => {
      const type = String(node.type || "unknown");
      counts[type] = (counts[type] || 0) + 1;
      return counts;
    }, {}),
    processing_logs: logs,
    demographic_focus_summary: artifacts[0]?.demographic_focus_summary ?? null,
  };
}

/* ─── Main Component ─── */

export default function PolicyUpload() {
  const {
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    useCase,
    uploadedFiles,
    analysisQuestions,
    knowledgeGraphReady,
    knowledgeArtifact,
    knowledgeLoading,
    knowledgeError,
    setSessionId,
    addUploadedFile,
    removeUploadedFile,
    setUploadedFiles,
    setAnalysisQuestions,
    addAnalysisQuestion,
    updateAnalysisQuestion,
    removeAnalysisQuestion,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    completeStep,
    setCurrentStep,
  } = useApp();

  const [dragOver, setDragOver] = useState(false);
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 400 });
  const [familyFilter, setFamilyFilter] = useState<FamilyFilter>('all');
  const [activeBuckets, setActiveBuckets] = useState<DisplayBucket[]>([]);
  const [showRelationshipLabels, setShowRelationshipLabels] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.sessionStorage.getItem(RELATIONSHIP_LABEL_STORAGE_KEY) === 'on';
  });
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlValue, setUrlValue] = useState('');
  const [showPasteArea, setShowPasteArea] = useState(false);
  const [pasteValue, setPasteValue] = useState('');
  const [showTopEntities, setShowTopEntities] = useState(true);

  const graphReady = knowledgeGraphReady && knowledgeArtifact !== null;

  // No longer need default guiding prompt initialization — 
  // analysis questions are loaded from config on session creation

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(RELATIONSHIP_LABEL_STORAGE_KEY, showRelationshipLabels ? 'on' : 'off');
    }
  }, [showRelationshipLabels]);

  const familyScopedNodes = graphReady
    ? knowledgeArtifact.entity_nodes.filter(
        (node) => !node.ui_default_hidden && matchesFamilyFilter(node.facet_kind, familyFilter),
      )
    : [];

  const availableBuckets: DisplayBucket[] = graphReady
    ? DISPLAY_BUCKET_ORDER.filter((bucket) => familyScopedNodes.some((node) => resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket) === bucket))
    : [];

  useEffect(() => {
    if (!graphReady) {
      setFamilyFilter((current) => (current === 'all' ? current : 'all'));
      setActiveBuckets((current) => (current.length === 0 ? current : []));
      return;
    }

    setActiveBuckets((current) => {
      const next = current.filter((bucket) => availableBuckets.includes(bucket));
      const resolved = next.length > 0 ? next : availableBuckets;
      return sameStringArray(current, resolved) ? current : resolved;
    });
  }, [availableBuckets, graphReady]);

  const resetKnowledgeState = useCallback(() => {
    setKnowledgeGraphReady(false);
    setKnowledgeArtifact(null);
    setKnowledgeError(null);
  }, [setKnowledgeArtifact, setKnowledgeError, setKnowledgeGraphReady]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach((f) => addUploadedFile(f));
    resetKnowledgeState();
  }, [resetKnowledgeState, addUploadedFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach((f) => addUploadedFile(f));
    resetKnowledgeState();
  }, [resetKnowledgeState, addUploadedFile]);

  const ensureSession = useCallback(async () => {
    if (sessionId) {
      return sessionId;
    }

    const created = await createConsoleSession(undefined, {
      model_provider: modelProvider,
      model_name: modelName,
      embed_model_name: embedModelName,
      api_key: modelApiKey.trim() || undefined,
      base_url: modelBaseUrl.trim() || undefined,
    });
    setSessionId(created.session_id);
    return created.session_id;
  }, [
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    modelName,
    modelProvider,
    sessionId,
    setSessionId,
  ]);

  const handleExtract = useCallback(async () => {
    if (uploadedFiles.length === 0) return;

    try {
      setKnowledgeLoading(true);
      setKnowledgeError(null);

      const resolvedSessionId = await ensureSession();
      const combinedPrompt = analysisQuestions.map((q) => q.question.trim()).filter(Boolean).join('\n\n') || getDefaultSystemPrompt(useCase);
      const serverParsedFiles = uploadedFiles.filter(isServerParsedDocument);
      const textFiles = uploadedFiles.filter((file) => !isServerParsedDocument(file));
      const artifacts: KnowledgeArtifact[] = [];

      if (textFiles.length > 0) {
        const documents = await Promise.all(
          textFiles.map(async (file) => ({
            document_text: await readFileText(file),
            source_path: file.name,
          })),
        );
        artifacts.push(
          await processKnowledgeDocuments(resolvedSessionId, {
            documents,
            guiding_prompt: combinedPrompt || undefined,
          }),
        );
      }

      for (const file of serverParsedFiles) {
        artifacts.push(
          await uploadKnowledgeFile(
            resolvedSessionId,
            file,
            combinedPrompt || undefined,
          ),
        );
      }

      const artifact = mergeKnowledgeArtifacts(resolvedSessionId, artifacts, combinedPrompt || null);
      setKnowledgeArtifact(artifact);
      setKnowledgeGraphReady(true);
    } catch (error) {
      if (!isLiveBootMode()) {
        try {
          // Demo mode can still hydrate from the bundled demo artifact.
          const demoRes = await fetch('/demo-output.json');
          if (demoRes.ok) {
            const demo = await demoRes.json();
            const knowledgeData = demo.knowledge;
            if (knowledgeData?.entity_nodes) {
              const artifact = {
                session_id: knowledgeData.simulation_id || 'demo-session',
                document: knowledgeData.document || { document_id: 'demo', paragraph_count: 0 },
                summary: knowledgeData.summary || '',
                guiding_prompt: knowledgeData.guiding_prompt || null,
                entity_nodes: knowledgeData.entity_nodes,
                relationship_edges: knowledgeData.relationship_edges || [],
                entity_type_counts: knowledgeData.entity_type_counts || {},
                processing_logs: [],
                demographic_focus_summary: knowledgeData.demographic_focus_summary || null,
              } as KnowledgeArtifact;
              setKnowledgeArtifact(artifact);
              setKnowledgeGraphReady(true);
              setSessionId(artifact.session_id);
              toast({ title: 'Demo mode', description: 'Loaded cached knowledge graph (backend unavailable)' });
              return;
            }
          }
        } catch { /* ignore demo fallback errors */ }
      }

      const message = resolveKnowledgeExtractionError(error, {
        provider: modelProvider,
        model: modelName,
      });
      setKnowledgeGraphReady(false);
      setKnowledgeArtifact(null);
      setKnowledgeError(message);
      toast({
        title: 'Knowledge extraction failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setKnowledgeLoading(false);
    }
  }, [
    uploadedFiles,
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    analysisQuestions,
    setKnowledgeLoading,
    setKnowledgeError,
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    ensureSession,
  ]);

  const handleProceed = () => {
    completeStep(1);
    setCurrentStep(2);
  };

  const handleUrlScrape = useCallback(async () => {
    const url = urlValue.trim();
    if (!url) return;

    try {
      const resolvedSessionId = await ensureSession();
      const scraped = await scrapeKnowledgeUrl(resolvedSessionId, url);
      const fileName = `${buildSafeDocumentName(scraped.title || 'scraped-document', 'scraped-document')}.txt`;
      const scrapedFile = new File([scraped.text || url], fileName, { type: 'text/plain' });
      addUploadedFile(scrapedFile);
      resetKnowledgeState();
      toast({ title: 'URL scraped', description: scraped.title ? scraped.title : `Fetched content from ${url}` });
    } catch (error) {
      resetKnowledgeState();
      const message = error instanceof Error ? error.message : 'Backend scrape failed.';
      if (!isLiveBootMode()) {
        const fallbackName = `${buildSafeDocumentName(url, 'scraped-document')}.txt`;
        const fallbackFile = new File([url], fallbackName, { type: 'text/plain' });
        addUploadedFile(fallbackFile);
        toast({
          title: 'URL scrape fallback',
          description: `${message} Queued URL as text.`,
        });
        return;
      }

      setKnowledgeError(message);
      toast({
        title: 'URL scrape failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setUrlValue('');
      setShowUrlInput(false);
    }
  }, [addUploadedFile, ensureSession, resetKnowledgeState, setKnowledgeError, setShowUrlInput, setUrlValue, urlValue]);

  const handlePasteSubmit = useCallback(() => {
    const text = pasteValue.trim();
    if (!text) return;

    const blob = new Blob([text], { type: 'text/plain' });
    const mockFile = new File([blob], 'pasted-text.txt', { type: 'text/plain' });
    addUploadedFile(mockFile);
    resetKnowledgeState();
    setPasteValue('');
    setShowPasteArea(false);
    toast({ title: 'Text added', description: 'Pasted content queued for backend extraction' });
  }, [addUploadedFile, pasteValue, resetKnowledgeState, setPasteValue, setShowPasteArea]);

  /* ─── Graph Data ─── */

  const filteredSourceNodes = graphReady
    ? familyScopedNodes.filter((node) => {
        const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
        return activeBuckets.length === 0 ? true : activeBuckets.includes(bucket);
      })
    : [];

  const filteredNodeIds = new Set(filteredSourceNodes.map((node) => node.id));

  const graphData = graphReady ? {
    nodes: filteredSourceNodes.map((node) => ({
      id: node.id,
      name: node.label,
      type: normalizeNodeType(node.type),
      displayBucket: resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket),
      facetKind: node.facet_kind,
      families: node.families ?? ['document'],
      description: node.summary || node.description,
      summary: node.summary || node.description,
      val: normalizeImportance(node.importance_score, node.weight),
      renderRadius: radiusFromImportance(node.importance_score, node.weight),
    })),
    links: knowledgeArtifact.relationship_edges
      .filter((edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target))
      .map((edge) => ({
        ...edge,
        label: edge.label || edge.raw_relation_text || edge.type,
        summary: edge.summary || edge.raw_relation_text || edge.label || edge.type,
      })),
  } : { nodes: [], links: [] };

  useEffect(() => {
    if (!graphReady || graphData.nodes.length === 0 || !graphRef.current?.d3Force) return;

    const maxRadius = Math.max(...graphData.nodes.map((node) => node.renderRadius), MIN_NODE_RADIUS);
    graphRef.current.d3Force('charge', forceManyBody().strength(-(150 + maxRadius * 18)));
    graphRef.current.d3Force('collide', forceCollide((node: GraphNodeDatum) => node.renderRadius + 30).iterations(2));

    const linkForce = graphRef.current.d3Force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
      linkForce.distance((link: { source: GraphNodeDatum; target: GraphNodeDatum }) => {
        const sourceRadius = link.source?.renderRadius ?? MIN_NODE_RADIUS;
        const targetRadius = link.target?.renderRadius ?? MIN_NODE_RADIUS;
        return Math.max(110, (sourceRadius + targetRadius) * 8);
      });
    }
    graphRef.current.d3ReheatSimulation?.();
  }, [graphData.links, graphData.nodes, graphReady]);

  const legendEntries = graphReady
    ? Array.from(
        new Map(
          graphData.nodes.map((node: GraphNodeDatum) => {
            const style = DISPLAY_BUCKET_STYLES[node.displayBucket] ?? DISPLAY_BUCKET_STYLES.other;
            return [`${style.label}:${style.color}`, style] as const;
          }),
        ).values(),
      )
    : [];

  const topEntities = graphReady
    ? [...knowledgeArtifact.entity_nodes]
      .filter((node) => !node.ui_default_hidden)
      .sort((left, right) => {
        const rightImportance = normalizeImportance(right.importance_score, right.weight);
        const leftImportance = normalizeImportance(left.importance_score, left.weight);
        if (rightImportance !== leftImportance) return rightImportance - leftImportance;
        return (right.support_count ?? 0) - (left.support_count ?? 0);
      })
      .slice(0, 3)
    : [];

  const nodeColor = (node: { type?: string; displayBucket?: string; facetKind?: string }) => {
    return (DISPLAY_BUCKET_STYLES[node.displayBucket || resolveDisplayBucket(node.type, node.facetKind)] ?? DISPLAY_BUCKET_STYLES.other).color;
  };

  /* ─── Render ─── */

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-0 h-full">
      {/* ───── LEFT PANEL ───── */}
      <div className="flex flex-col border-r border-border overflow-y-auto scrollbar-thin bg-background">
        {/* Header */}
        <div className="p-5 pb-4 border-b border-border">
          <h2 className="text-lg font-bold text-foreground font-mono uppercase tracking-wider">NEW SIMULATION RUN</h2>
          <p className="text-xs text-muted-foreground mt-1">Upload unstructured documents to build the context graph</p>
          {/* Use-case badge */}
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-border bg-transparent text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
              {modelProvider === 'gemini' ? 'Gemini 2.0' : modelProvider} · Document Processing
            </span>
          </div>
        </div>

        {/* Upload Zone */}
        <div className="p-5 border-b border-border">
          <label
            className={`flex flex-col items-center justify-center p-6 cursor-pointer transition-colors border border-dashed rounded-lg bg-transparent ${
              dragOver ? 'border-white/40 bg-white/[0.03]' : uploadedFiles.length > 0 ? 'border-border' : 'border-border hover:border-white/25'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input type="file" className="hidden" accept=".pdf,.docx,.doc,.txt,.md,.markdown,.html,.htm,.json,.csv,.yaml,.yml" multiple onChange={handleFileSelect} />
            <Upload className="w-6 h-6 text-muted-foreground mb-2" />
            <span className="text-sm text-foreground">Drop documents here</span>
            <span className="text-[10px] text-muted-foreground mt-1 font-mono uppercase tracking-wider">
              PDF · DOCX · TXT · MD · HTML · CSV · YAML
            </span>
          </label>

          {/* File list */}
          {uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-1">
              {uploadedFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="rounded bg-card border border-border group px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                      <span className="text-sm text-foreground truncate">{file.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-muted-foreground">{formatFileSize(file.size)}</span>
                      <button
                        type="button"
                        onClick={() => { removeUploadedFile(index); resetKnowledgeState(); }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  {knowledgeLoading && (
                    <div className="mt-2">
                      <Progress
                        value={50}
                        aria-label={`${file.name} upload progress`}
                        className="h-1.5 bg-white/5"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Alt input methods */}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setShowUrlInput(!showUrlInput)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showUrlInput ? 'border-white/20 bg-white/5 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-white/15'
              }`}
            >
              <Link className="w-3 h-3" /> URL
            </button>
            <button
              type="button"
              onClick={() => setShowPasteArea(!showPasteArea)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showPasteArea ? 'border-white/20 bg-white/5 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-white/15'
              }`}
            >
              <Type className="w-3 h-3" /> Paste
            </button>
          </div>

          {/* URL scraper */}
          {showUrlInput && (
            <div className="mt-2 flex gap-2 animate-slide-up">
              <Input
                value={urlValue}
                onChange={(e) => setUrlValue(e.target.value)}
                placeholder="https://example.com/policy-doc"
                className="text-sm bg-card border-border"
              />
              <Button onClick={handleUrlScrape} size="sm" variant="outline" className="shrink-0 border-border text-foreground">
                Scrape
              </Button>
            </div>
          )}

          {/* Paste text */}
          {showPasteArea && (
            <div className="mt-2 space-y-2 animate-slide-up">
              <Textarea
                value={pasteValue}
                onChange={(e) => setPasteValue(e.target.value)}
                placeholder="Paste document text here..."
                className="text-sm bg-card border-border min-h-[80px] resize-none"
              />
              <Button onClick={handlePasteSubmit} size="sm" variant="outline" className="border-border text-foreground">
                Add as Document
              </Button>
            </div>
          )}
        </div>

        {/* Analysis Questions */}
        <div className="p-5 border-b border-border">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="label-meta">Analysis Questions</span>
              <p className="text-[10px] text-muted-foreground mt-0.5">Each question becomes a seed post in the simulation and a section in the report.</p>
            </div>
            <button
              type="button"
              onClick={() => addAnalysisQuestion({
                question: '',
                type: 'open-ended',
                metric_name: 'custom_' + Date.now(),
                report_title: '',
                source: 'custom',
                metadataStatus: 'pending',
              })}
              className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
            >
              <Plus className="w-3 h-3" /> Add Question
            </button>
          </div>
          <div className="space-y-2">
            {analysisQuestions.length === 0 && (
              <p className="text-xs text-muted-foreground italic py-3 text-center">
                Questions will be loaded from the use-case template when the session starts.
              </p>
            )}
            {analysisQuestions.map((q, index) => (
              <div key={index} className="group relative bg-card border border-border rounded-lg p-3 hover:border-white/20 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    {q.source === 'custom' ? (
                      <Textarea
                        value={q.question}
                        onChange={(e) => updateAnalysisQuestion(index, { ...q, question: e.target.value })}
                        placeholder="Type your analysis question..."
                        className="text-sm bg-transparent border-0 p-0 min-h-[40px] resize-none focus-visible:ring-0"
                      />
                    ) : (
                      <p className="text-sm text-foreground">{q.question}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider ${
                        q.type === 'scale' ? 'bg-blue-500/10 text-blue-400' :
                        q.type === 'yes-no' ? 'bg-emerald-500/10 text-emerald-400' :
                        'bg-white/5 text-muted-foreground'
                      }`}>
                        {q.type}
                      </span>
                      {q.metric_label && (
                        <span className="text-[9px] text-muted-foreground">{q.metric_label}</span>
                      )}
                      {q.source === 'preset' && (
                        <span className="text-[9px] text-muted-foreground/50">preset</span>
                      )}
                      {q.metadataStatus === 'loading' && (
                        <Loader2 className="w-3 h-3 text-muted-foreground animate-spin" />
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeAnalysisQuestion(index)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground mt-1"
                    title="Remove question"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="p-5 border-b border-border">
          <div className="flex gap-2">
            <Button
              onClick={handleExtract}
              disabled={uploadedFiles.length === 0 || knowledgeLoading}
              className="flex-1 bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white border-0 font-medium font-mono uppercase tracking-wider text-xs h-10"
            >
              {knowledgeLoading ? (
                "Processing..."
              ) : (
                <><Sparkles className="w-3.5 h-3.5 mr-2" /> Start Extraction</>
              )}
            </Button>
            {graphReady && (
              <Button
                onClick={handleProceed}
                variant="outline"
                className="h-10 border border-success/30 bg-success/20 px-4 font-mono text-xs uppercase tracking-wider text-success hover:bg-success/30"
              >
                Proceed <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>
          {knowledgeError && (
            <p className="text-xs text-destructive mt-2 font-mono uppercase">{knowledgeError}</p>
          )}

          {/* Fake Loading Log */}
          {knowledgeLoading && (
            <div className="mt-4 p-3 border border-border bg-black rounded font-mono text-[10px] text-muted-foreground w-full space-y-1">
              <div className="animate-pulse-subtle flex justify-between">
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Initializing graph builder...</span>
                <span className="text-success">OK</span>
              </div>
              <div className="animate-pulse-subtle flex justify-between" style={{ animationDelay: '0.4s' }}>
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Parsing uploaded documents...</span>
                <span className="text-success">OK</span>
              </div>
              <div className="animate-pulse-subtle flex justify-between" style={{ animationDelay: '0.8s' }}>
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Chunking & computing embeddings...</span>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        {graphReady && (
          <div className="p-5 border-b border-border">
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Entities" value={knowledgeArtifact.entity_nodes.length} />
              <Stat label="Relations" value={knowledgeArtifact.relationship_edges.length} />
              <Stat label="Paragraphs" value={knowledgeArtifact.document.paragraph_count ?? 0} />
            </div>
          </div>
        )}

        {/* Top Entities — collapsible */}
        {graphReady && (
          <div className="p-5">
            <button
              type="button"
              onClick={() => setShowTopEntities(!showTopEntities)}
              className="flex items-center justify-between w-full mb-3"
            >
              <span className="label-meta">Top Entities</span>
              {showTopEntities ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
            </button>
            {showTopEntities && (
              <div className="space-y-3 animate-slide-up">
                {topEntities.map((node) => {
                  const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
                  const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                  return (
                    <div key={node.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: style.color }} />
                          <span className="truncate text-sm text-foreground">{node.label}</span>
                        </div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground ml-4">{style.label}</div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-mono text-foreground">{normalizeImportance(node.importance_score, node.weight).toFixed(2)}</div>
                        <div className="text-[10px] font-mono text-muted-foreground">×{node.support_count ?? 0}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ───── RIGHT PANEL — KNOWLEDGE GRAPH ───── */}
      <div className="flex flex-col bg-background">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h3 className="text-sm font-medium text-foreground">Knowledge Graph</h3>
        </div>

        {graphReady && (
          <div className="px-5 py-2.5 border-b border-border space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SegmentedControl
                value={familyFilter}
                options={[
                  { value: 'all', label: 'All' },
                  { value: 'nemotron', label: 'Nemotron' },
                  { value: 'other', label: 'Other' },
                ]}
                onChange={(nextValue) => setFamilyFilter(nextValue as FamilyFilter)}
              />
              <button
                type="button"
                onClick={() => setShowRelationshipLabels((current) => !current)}
                className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                  showRelationshipLabels
                    ? 'border-white/20 bg-white/5 text-foreground'
                    : 'border-border text-muted-foreground hover:border-white/15 hover:text-foreground'
                }`}
              >
                {showRelationshipLabels ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                Labels
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {availableBuckets.map((bucket) => {
                const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                const isActive = activeBuckets.includes(bucket);
                return (
                  <FilterChip
                    key={bucket}
                    active={isActive}
                    label={style.label}
                    accent={style.color}
                    onClick={() => {
                      setActiveBuckets((current) => (
                        current.length === availableBuckets.length
                          ? [bucket]
                          : current.includes(bucket)
                            ? (current.filter((value) => value !== bucket).length > 0
                              ? current.filter((value) => value !== bucket)
                              : availableBuckets)
                            : [...current, bucket]
                      ));
                    }}
                  />
                );
              })}
            </div>
          </div>
        )}

        <div ref={containerRef} className="flex-1 min-h-[300px] overflow-hidden">
          {graphReady && graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              enableNodeDrag
              nodeLabel={(node: GraphNodeDatum) => `${node.name || ''}${node.summary ? `: ${node.summary}` : ''}`}
              linkLabel={(link: GraphLinkDatum) => {
                const summary = link.summary?.trim();
                if (!summary) return link.label || '';
                return `${link.label}: ${summary}`;
              }}
              nodeColor={nodeColor}
              nodeRelSize={1}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={(node: GraphNodeDatum, ctx, globalScale) => {
                if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

                const radius = node.renderRadius || radiusFromNormalizedValue(node.val);
                const label = node.name || '';
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px "Space Grotesk", sans-serif`;
                const labelX = node.x + radius + NODE_LABEL_GAP;
                const labelY = node.y;
                const labelWidth = ctx.measureText(label).width;
                const backgroundX = labelX - 4;
                const backgroundY = labelY - fontSize / 2 - 3;
                const backgroundWidth = labelWidth + 8;
                const backgroundHeight = fontSize + 6;

                ctx.save();
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = nodeColor(node);
                ctx.fill();

                ctx.lineWidth = 1;
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                ctx.stroke();

                ctx.fillStyle = 'rgba(10, 10, 10, 0.85)';
                ctx.fillRect(backgroundX, backgroundY, backgroundWidth, backgroundHeight);

                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                ctx.fillText(label, labelX, labelY);
                ctx.restore();
              }}
              linkCanvasObjectMode={() => 'after'}
              linkCanvasObject={(link: GraphLinkDatum, ctx, globalScale) => {
                if (!showRelationshipLabels) return;
                const label = (link.label || link.type || '').trim();
                const source = typeof link.source === 'string' ? undefined : link.source;
                const target = typeof link.target === 'string' ? undefined : link.target;
                if (!label || typeof source?.x !== 'number' || typeof source?.y !== 'number' || typeof target?.x !== 'number' || typeof target?.y !== 'number') return;

                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const length = Math.hypot(dx, dy) || 1;
                const normalX = -dy / length;
                const normalY = dx / length;
                const readableLabel = shortenLabel(label, Math.max(12, Math.floor(length / 8)));
                const fontSize = Math.max(8.5, 10.5 / globalScale);
                ctx.font = `${fontSize}px "Space Mono", monospace`;
                const textWidth = ctx.measureText(readableLabel).width;
                const boxWidth = textWidth + 12;
                const boxHeight = fontSize + 8;
                const offset = Math.min(22, Math.max(10, length * 0.08));

                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(10, 10, 10, 0.88)';
                ctx.fillRect(
                  midX + normalX * offset - boxWidth / 2,
                  midY + normalY * offset - boxHeight / 2,
                  boxWidth,
                  boxHeight,
                );
                ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                ctx.fillText(readableLabel, midX + normalX * offset, midY + normalY * offset);
                ctx.restore();
              }}
              linkColor={() => 'rgba(255, 255, 255, 0.08)'}
              linkWidth={1}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              backgroundColor="transparent"
              cooldownTicks={80}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {knowledgeLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                  <span className="font-mono text-xs uppercase tracking-wider">Building graph...</span>
                </div>
              ) : graphReady ? (
                'No nodes match the current filters'
              ) : (
                <div className="text-center max-w-xs">
                  <div className="text-muted-foreground/40 mb-2">
                    <Upload className="w-8 h-8 mx-auto" />
                  </div>
                  <p className="text-sm text-muted-foreground">Upload a document to generate the knowledge graph</p>
                  <p className="text-[10px] font-mono text-muted-foreground/50 mt-1 uppercase tracking-wider">Interactive Force Graph · Drag nodes to explore</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-mono font-medium text-foreground tracking-tight">{value}</div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.18em]">{label}</div>
    </div>
  );
}

function FilterChip({ active, label, onClick, accent }: { active: boolean; label: string; onClick: () => void; accent?: string; }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
        active
          ? 'border-white/20 bg-white/8 text-foreground'
          : 'border-border text-muted-foreground hover:border-white/15 hover:text-foreground'
      }`}
    >
      <span className="flex items-center gap-1.5">
        {accent && <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accent, opacity: active ? 1 : 0.5 }} />}
        {label}
      </span>
    </button>
  );
}

function SegmentedControl({ value, options, onChange }: { value: string; options: Array<{ value: string; label: string }>; onChange: (value: string) => void; }) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded border border-border bg-card p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded px-3 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            option.value === value
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ─── Utilities ─── */

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function normalizeNodeType(type?: string) {
  const normalized = (type || 'other').trim().toLowerCase();
  if (normalized === 'institution' || normalized === 'org') return 'organization';
  if (normalized === 'demographic') return 'population';
  if (normalized === 'planning_area') return 'location';
  return normalized || 'other';
}

function normalizeImportance(importanceScore?: number | null, weight?: number | null) {
  const base = importanceScore ?? weight ?? 0.35;
  return Math.max(0, Math.min(1, Number.isFinite(base) ? Number(base) : 0.35));
}

function radiusFromImportance(importanceScore?: number | null, weight?: number | null) {
  const importance = normalizeImportance(importanceScore, weight);
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * importance));
}

function radiusFromNormalizedValue(value?: number | null) {
  const importance = Math.max(0, Math.min(1, Number.isFinite(value) ? Number(value) : 0));
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * importance));
}

function matchesFamilyFilter(facetKind?: string | null, familyFilter: FamilyFilter = 'all') {
  if (familyFilter === 'all') return true;
  const isNemotronEntity = Boolean((facetKind || '').trim());
  return familyFilter === 'nemotron' ? isNemotronEntity : !isNemotronEntity;
}

function resolveDisplayBucket(type?: string, facetKind?: string | null, explicitBucket?: string | null): DisplayBucket {
  const normalizedExplicit = (explicitBucket || '').trim().toLowerCase();
  if (normalizedExplicit && normalizedExplicit in DISPLAY_BUCKET_STYLES) return normalizedExplicit as DisplayBucket;

  const normalizedFacet = (facetKind || '').trim().toLowerCase();
  if (normalizedFacet === 'age_cohort') return 'age_group';
  if (normalizedFacet === 'industry') return 'industry';

  const normalizedType = normalizeNodeType(type);
  if (['organization', 'institution'].includes(normalizedType)) return 'organization';
  if (['person', 'population', 'stakeholder', 'demographic', 'group'].includes(normalizedType)) return 'persons';
  if (['location', 'planning_area'].includes(normalizedType)) return 'location';
  if (normalizedType === 'event') return 'event';
  if (['concept', 'policy', 'program', 'topic', 'law', 'service', 'funding'].includes(normalizedType)) return 'concept';
  if (normalizedType === 'industry') return 'industry';
  return 'other';
}

function shortenLabel(label: string, maxLength: number) {
  if (label.length <= maxLength) return label;
  return `${label.slice(0, Math.max(6, maxLength - 1))}…`;
}

function sameStringArray(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}
```

- Guiding Prompts textarea → Analysis Questions card list
- Type badges, preset indicators, add/remove support

### ReportChat (Screen 4)
```diff:ReportChat.tsx
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  FileText, Loader2, Download, Send, Search, X,
  MessageSquare, Users, User, TrendingUp, TrendingDown,
  AlertTriangle, ArrowRight, BadgeCheck, BriefcaseBusiness, MapPin, Wallet
} from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  StructuredReportState,
  exportReportDocx,
  generateReport,
  getStructuredReport,
  sendAgentChatMessage,
  sendGroupChatMessage,
  isLiveBootMode,
} from '@/lib/console-api';
import { agentResponses, Agent, type SimPost } from '@/data/mockData';
import { toast } from '@/hooks/use-toast';

const POLL_INTERVAL_MS = 1500;

type ViewMode = 'report' | 'split' | 'chat';
type ChatSegment = 'dissenters' | 'supporters' | 'one-on-one';

const EMPTY_REPORT: StructuredReportState = {
  session_id: '',
  status: 'idle',
  generated_at: null,
  executive_summary: null,
  insight_cards: [],
  support_themes: [],
  dissent_themes: [],
  demographic_breakdown: [],
  influential_content: [],
  recommendations: [],
  risks: [],
  error: null,
};

/* ── Mock report data for demo mode ── */
const DEMO_REPORT: StructuredReportState = {
  session_id: 'demo',
  status: 'complete',
  generated_at: new Date().toISOString(),
  executive_summary:
    'The simulation reveals a deeply divided population regarding Budget 2026 policies. Initial approval of 65% eroded to 34% over 5 rounds of discourse, driven primarily by concerns about cost of living, AI-driven job displacement, and insufficient support for gig workers. The most influential agents were dissenters from lower-income brackets who reframed policy benefits as insufficient relative to rising costs.',
  insight_cards: [
    { title: 'Generational Divide', description: 'Under-35s are 29pp less likely to approve than over-55s. Housing and CPF concerns dominate.', icon: 'trend' },
    { title: 'Income Correlation', description: 'Below $4k income bracket shows 35% approval vs 64% for above $8k. Inequality is the key driver.', icon: 'chart' },
    { title: 'Cascade Effect', description: 'A single viral post about AI job displacement shifted 42 agents from supporter to dissenter.', icon: 'alert' },
  ],
  support_themes: [
    { theme: 'AI investment is forward-thinking and positions Singapore competitively', evidence_count: 23 },
    { theme: 'SkillsFuture enhancements address workforce readiness', evidence_count: 18 },
    { theme: 'Family support measures are practical and well-targeted', evidence_count: 15 },
  ],
  dissent_themes: [
    { theme: 'Cost of living not adequately addressed — wage growth lags inflation', evidence_count: 47 },
    { theme: 'AI benefits accrue to top earners while displacing middle-income jobs', evidence_count: 31 },
    { theme: 'Carbon tax increases will hit transport-dependent workers hardest', evidence_count: 22 },
  ],
  demographic_breakdown: [
    { group: '21–30', approval: 38, count: 62 },
    { group: '31–40', approval: 47, count: 58 },
    { group: '41–55', approval: 58, count: 72 },
    { group: '55+', approval: 67, count: 58 },
  ],
  influential_content: [
    { title: 'Innovation hubs only benefit top earners', author: 'Raj Kumar', engagement: 142, shift: -0.42 },
    { title: 'SkillsFuture is a band-aid on structural inequality', author: 'Siti Ibrahim', engagement: 98, shift: -0.28 },
  ],
  recommendations: [
    { title: 'Address cost-of-living gap', description: 'Introduce targeted wage supplements for income brackets below $4,000 to reduce the approval gap.' },
    { title: 'AI transition support', description: 'Create an AI Displacement Fund with retraining credits specifically for middle-income workers in at-risk sectors.' },
    { title: 'Carbon tax rebates', description: 'Expand U-Save rebates and introduce transport subsidies for workers in non-CBD areas.' },
  ],
  risks: [],
  error: null,
};

export default function ReportChat() {
  const {
    sessionId,
    simulationComplete,
    agents,
    simPosts,
    chatHistory,
    addChatMessage,
    completeStep,
    setCurrentStep,
    country,
    useCase,
    simulationRounds,
  } = useApp();
  const liveMode = isLiveBootMode();

  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [reportState, setReportState] = useState<StructuredReportState>(EMPTY_REPORT);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const startedRef = useRef<string | null>(null);

  // Chat state
  const [chatSegment, setChatSegment] = useState<ChatSegment>('dissenters');
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [profileAgent, setProfileAgent] = useState<Agent | null>(null);
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const topSupporters = useMemo(
    () => agents.filter((agent) => agent.sentiment === 'positive').slice(0, 5),
    [agents],
  );
  const topDissenters = useMemo(
    () => agents.filter((agent) => agent.sentiment === 'negative').slice(0, 5),
    [agents],
  );
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);

  const loadDemoReport = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch('/demo-output.json');
      if (response.ok) {
        const data = await response.json();
        if (data?.report || data?.reportFull) {
          const reportFromDemo = data.reportFull || data.report;
          setReportState({ ...DEMO_REPORT, ...reportFromDemo, status: 'complete' });
          return;
        }
      }
    } catch {
      // Fall through to built-in demo report.
    }
    setReportState(DEMO_REPORT);
  }, []);

  // Load demo data if no backend
  useEffect(() => {
    if (isLiveBootMode()) {
      return;
    }
    if (reportState.status === 'idle' && !loading) {
      void loadDemoReport();
    }
  }, [loadDemoReport, reportState.status, loading]);

  const beginReportGeneration = useCallback(async () => {
    if (!sessionId) {
      setReportError('Complete a simulation before generating a report.');
      return;
    }
    startedRef.current = sessionId;
    setLoading(true);
    setReportError(null);
    try {
      const [, polled] = await Promise.all([
        generateReport(sessionId),
        getStructuredReport(sessionId),
      ]);
      setReportState(polled);
    } catch (error) {
      startedRef.current = null;
      if (!isLiveBootMode()) {
        await loadDemoReport();
        setReportError(null);
        toast({
          title: 'Demo report loaded',
          description: error instanceof Error ? `${error.message}. Showing cached demo report.` : 'Backend unavailable. Showing cached demo report.',
        });
      } else {
        const message = error instanceof Error ? error.message : 'Report generation failed.';
        setReportState(EMPTY_REPORT);
        setReportError(message);
        toast({
          title: 'Report generation failed',
          description: message,
          variant: 'destructive',
        });
      }
    } finally {
      setLoading(false);
    }
  }, [loadDemoReport, sessionId]);

  useLayoutEffect(() => {
    if (!simulationComplete || !sessionId) return;
    if (startedRef.current === sessionId) return;
    void beginReportGeneration();
  }, [beginReportGeneration, sessionId, simulationComplete]);

  useEffect(() => {
    if (!sessionId || reportState.status !== 'running') return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getStructuredReport(sessionId);
        setReportState(next);
      } catch { /* ignore */ }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [sessionId, reportState.status]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [chatHistory, selectedAgent]);

  const enqueueDemoGroupReplies = useCallback((threadId: string, responders: Agent[]) => {
    responders.slice(0, 5).forEach((agent, index) => {
      window.setTimeout(() => {
        const responses = agentResponses[agent.sentiment] || agentResponses.neutral;
        const reply = responses[Math.floor(Math.random() * responses.length)];
        addChatMessage(threadId, 'agent', reply, agent.id);
      }, 420 + index * 220 + Math.random() * 300);
    });
  }, [addChatMessage]);

  const enqueueDemoOneToOneReply = useCallback((threadId: string, selected: Agent) => {
    window.setTimeout(() => {
      const responses = agentResponses[selected.sentiment] || agentResponses.neutral;
      const reply = responses[Math.floor(Math.random() * responses.length)];
      addChatMessage(threadId, 'agent', reply, selected.id);
    }, 520 + Math.random() * 500);
  }, [addChatMessage]);

  const sendMessage = useCallback(async () => {
    const trimmed = message.trim();
    if (!trimmed) return;

    if (chatSegment === 'one-on-one') {
      if (!selectedAgent) return;
      const threadId = selectedAgent.id;
      addChatMessage(threadId, 'user', trimmed, selectedAgent.id);
      setMessage('');
      if (!sessionId) {
        enqueueDemoOneToOneReply(threadId, selectedAgent);
        return;
      }
      try {
        const response = await sendAgentChatMessage(sessionId, {
          agent_id: selectedAgent.id,
          message: trimmed,
        });
        if (response.responses.length > 0) {
          response.responses.forEach((entry) => {
            addChatMessage(threadId, 'agent', entry.content, entry.agent_id ?? selectedAgent.id);
          });
          return;
        }
        if (liveMode) {
          toast({
            title: 'Live chat unavailable',
            description: 'The backend returned no agent response.',
            variant: 'destructive',
          });
          return;
        }
        enqueueDemoOneToOneReply(threadId, selectedAgent);
      } catch (error) {
        if (liveMode) {
          toast({
            title: 'Live chat unavailable',
            description: error instanceof Error ? error.message : 'The backend request failed.',
            variant: 'destructive',
          });
          return;
        }
        enqueueDemoOneToOneReply(threadId, selectedAgent);
      }
      return;
    }

    const threadId = `group-${chatSegment}`;
    const responders = chatSegment === 'supporters' ? topSupporters : topDissenters;
    if (!responders.length) {
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: 'No live agents are available for this chat segment.',
          variant: 'destructive',
        });
      }
      return;
    }

    addChatMessage(threadId, 'user', trimmed);
    setMessage('');
    if (!sessionId) {
      enqueueDemoGroupReplies(threadId, responders);
      return;
    }
    try {
      const response = await sendGroupChatMessage(sessionId, {
        segment: chatSegment,
        message: trimmed,
      });
      if (response.responses.length > 0) {
        response.responses.forEach((entry, index) => {
          addChatMessage(
            threadId,
            'agent',
            entry.content,
            entry.agent_id ?? responders[index]?.id,
          );
        });
        return;
      }
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: 'The backend returned no agent responses.',
          variant: 'destructive',
        });
        return;
      }
      enqueueDemoGroupReplies(threadId, responders);
    } catch (error) {
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: error instanceof Error ? error.message : 'The backend request failed.',
          variant: 'destructive',
        });
        return;
      }
      enqueueDemoGroupReplies(threadId, responders);
    }
  }, [
    addChatMessage,
    chatSegment,
    enqueueDemoGroupReplies,
    enqueueDemoOneToOneReply,
    message,
    selectedAgent,
    sessionId,
    liveMode,
    topDissenters,
    topSupporters,
  ]);

  const handleExport = useCallback(async () => {
    if (!sessionId) {
      toast({ title: 'Export failed', description: 'No active session found.' });
      return;
    }
    try {
      const file = await exportReportDocx(sessionId);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `mckainsey-report-${sessionId}.docx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: 'Export unavailable',
        description: error instanceof Error ? error.message : 'Unable to export DOCX right now.',
      });
    }
  }, [sessionId]);

  const handleProceed = useCallback(() => {
    completeStep(4);
    setCurrentStep(5);
  }, [completeStep, setCurrentStep]);

  const report = reportState;
  const filteredAgents = agents.filter(a => {
    const matchSearch = a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.occupation.toLowerCase().includes(search.toLowerCase());
    return matchSearch;
  }).slice(0, 30);

  const activeThreadId = chatSegment === 'one-on-one'
    ? selectedAgent?.id ?? null
    : `group-${chatSegment}`;
  const history = activeThreadId ? (chatHistory[activeThreadId] || []) : [];

  const showReport = viewMode === 'report' || viewMode === 'split';
  const showChat = viewMode === 'chat' || viewMode === 'split';

  const activeProfilePosts = useMemo(() => {
    if (!profileAgent) return [];
    return simPosts
      .filter((post) => post.agentId === profileAgent.id)
      .sort((left, right) => (right.upvotes + right.commentCount) - (left.upvotes + left.commentCount))
      .slice(0, 3);
  }, [profileAgent, simPosts]);

  const openOneToOneChat = useCallback((agent: Agent) => {
    setSelectedAgent(agent);
    setChatSegment('one-on-one');
    setViewMode('split');
    setProfileAgent(null);
  }, []);

  const headerAgentCount = agents.length > 0 ? String(agents.length) : (liveMode ? '—' : '250');
  const initialApproval = liveMode
    ? getReportMetricDisplay(report, ['initial_approval', 'initial_approval_rate', 'approval_rate'], 'percent')
    : '65%';
  const finalApproval = liveMode
    ? getReportMetricDisplay(report, ['final_approval', 'final_approval_rate'])
    : '34%';
  const agentsSimulated = liveMode
    ? getReportMetricDisplay(report, ['agent_count', 'agents_simulated', 'simulation_agents', 'population_size'], 'count')
    : '250';

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
        <div>
          <h2 className="text-lg font-semibold text-foreground tracking-tight">Analysis Report</h2>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {headerAgentCount} agents · {simulationRounds} rounds
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SegmentedControl
            value={viewMode}
            options={[
              { value: 'report', label: 'Report' },
              { value: 'split', label: 'Report + Chat' },
              { value: 'chat', label: 'Chat' },
            ]}
            onChange={(v) => setViewMode(v as ViewMode)}
          />
          <Button onClick={handleExport} variant="outline" size="sm" className="border-border text-foreground gap-1.5 h-8">
            <Download className="w-3.5 h-3.5" /> Export
          </Button>
          <Button onClick={handleProceed} size="sm" className="bg-success/20 text-success hover:bg-success/30 border border-success/30 h-8 px-4 font-mono uppercase tracking-wider">
            Proceed <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── Report Panel ── */}
        {showReport && (
          <div className={`overflow-y-auto scrollbar-thin p-6 space-y-6 ${showChat ? 'w-[60%] border-r border-border' : 'w-full max-w-4xl mx-auto'}`}>
            {loading ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Generating report...</span>
              </div>
            ) : reportError ? (
              <div className="text-center py-16">
                <AlertTriangle className="w-8 h-8 text-destructive mx-auto mb-3" />
                <p className="text-sm text-destructive">{reportError}</p>
                <Button onClick={beginReportGeneration} variant="outline" className="mt-4 border-border text-foreground">
                  Retry
                </Button>
              </div>
            ) : (
              <>
                {/* Executive Summary */}
                <section className="surface-card p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    <span className="label-meta">Executive Summary</span>
                  </div>
                  <p className="text-sm text-foreground/80 leading-relaxed">
                    {report.executive_summary || 'No summary available.'}
                  </p>
                  {/* Quick stats */}
                  <div className="mt-4 pt-4 border-t border-border flex items-center gap-6">
                    <QuickStat label="Initial Approval" value={initialApproval} color="hsl(var(--data-green))" />
                    <ArrowRight className="w-4 h-4 text-muted-foreground" />
                    <QuickStat label="Final Approval" value={finalApproval} color="hsl(var(--data-red))" />
                    <div className="ml-auto">
                      <QuickStat label="Agents Simulated" value={agentsSimulated} />
                    </div>
                  </div>
                </section>

                {/* Insight Cards */}
                {report.insight_cards && report.insight_cards.length > 0 && (
                  <section>
                    <span className="label-meta block mb-3">Key Insights</span>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {report.insight_cards.map((card: any, i: number) => (
                        <div key={i} className="surface-card p-4">
                          <div className="text-sm font-medium text-foreground mb-1">{card.title || card.headline}</div>
                          <p className="text-xs text-muted-foreground leading-relaxed">{card.description}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Supporting vs Dissenting */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <ThemeCard
                    title="Supporting Views"
                    color="hsl(var(--data-green))"
                    themes={report.support_themes}
                  />
                  <ThemeCard
                    title="Dissenting Views"
                    color="hsl(var(--data-red))"
                    themes={report.dissent_themes}
                  />
                </div>

                {/* Demographic Breakdown */}
                {report.demographic_breakdown && report.demographic_breakdown.length > 0 && (
                  <section className="surface-card p-5">
                    <span className="label-meta block mb-4">Demographic Breakdown</span>
                    <div className="space-y-3">
                      {report.demographic_breakdown.map((row: any, i: number) => (
                        <div key={i} className="flex items-center gap-3">
                          <span className="text-xs font-mono text-muted-foreground w-16">{row.group}</span>
                          <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{
                                width: `${row.approval}%`,
                                backgroundColor: row.approval >= 50 ? 'hsl(var(--data-green))' : 'hsl(var(--data-red))',
                              }}
                            />
                          </div>
                          <span className="text-xs font-mono text-foreground w-10 text-right">{row.approval}%</span>
                          <span className="text-[10px] font-mono text-muted-foreground w-12">n={row.count}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Recommendations */}
                {report.recommendations && report.recommendations.length > 0 && (
                  <section className="surface-card p-5">
                    <span className="label-meta block mb-4">Recommendations</span>
                    <div className="space-y-4">
                      {report.recommendations.map((rec: any, i: number) => (
                        <div key={i} className="flex gap-3">
                          <div className="w-5 h-5 rounded flex items-center justify-center bg-white/5 text-[9px] font-mono text-muted-foreground flex-shrink-0 mt-0.5">
                            {i + 1}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">{rec.title}</div>
                            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{rec.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Chat Panel ── */}
        {showChat && (
          <div className={`flex flex-col ${showReport ? 'w-[40%]' : 'w-full'}`}>
            {/* Chat Header */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Agent Chat</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[hsl(210,100%,56%)]/15 text-[hsl(210,100%,56%)] uppercase tracking-wider">
                  {chatSegment === 'one-on-one' ? '1:1' : 'Group'}
                </span>
              </div>
              {viewMode === 'split' && (
                <button
                  onClick={() => setViewMode('report')}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Segment Tabs */}
            <div className="px-4 py-2.5 border-b border-border flex gap-1.5 flex-shrink-0">
              {(['dissenters', 'supporters', 'one-on-one'] as ChatSegment[]).map(seg => (
                <button
                  key={seg}
                  onClick={() => setChatSegment(seg)}
                  className={`px-3 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    chatSegment === seg
                      ? 'bg-white/10 text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {seg === 'one-on-one' ? '1:1 Chat' : `Top ${seg}`}
                </button>
              ))}
            </div>

            {/* Agent selector for 1:1 */}
            {chatSegment === 'one-on-one' && (
              <div className="px-4 py-2.5 border-b border-border flex-shrink-0">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search agents..."
                    className="pl-9 h-8 text-sm bg-card border-border"
                  />
                </div>
                {search && filteredAgents.length > 0 && (
                  <div className="mt-1.5 max-h-36 overflow-y-auto space-y-0.5 scrollbar-thin">
                    {filteredAgents.map(agent => (
                      <button
                        key={agent.id}
                        onClick={() => { setSelectedAgent(agent); setSearch(''); }}
                        onDoubleClick={() => setProfileAgent(agent)}
                        className={`w-full text-left px-3 py-2 rounded text-xs transition-colors ${
                          selectedAgent?.id === agent.id
                            ? 'bg-white/10 text-foreground'
                            : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'
                        }`}
                      >
                        <span className="font-medium">{agent.name}</span>
                        <span className="text-muted-foreground ml-1.5">{agent.occupation}</span>
                      </button>
                    ))}
                  </div>
                )}
                {selectedAgent && (
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded bg-card border border-border">
                    <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[9px] font-mono text-foreground">
                      {selectedAgent.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                    </div>
                    <button
                      type="button"
                      onClick={() => setProfileAgent(selectedAgent)}
                      className="text-xs text-foreground hover:text-white underline-offset-2 hover:underline"
                    >
                      {selectedAgent.name}
                    </button>
                    <StanceDot sentiment={selectedAgent.sentiment} />
                    <button
                      onClick={() => setSelectedAgent(null)}
                      className="ml-auto text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scrollbar-thin">
              {chatSegment !== 'one-on-one' ? (
                /* Group chat: show a welcome prompt */
                history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                    <Users className="w-8 h-8 opacity-30" />
                    <p className="text-sm">Ask a question to the {chatSegment}</p>
                    <p className="text-[10px] font-mono uppercase tracking-wider opacity-50">
                      Top 5 most influential agents will respond
                    </p>
                  </div>
                ) : (
                  history.map((msg, i) => {
                    const sourceAgent = msg.agentId ? agentsById.get(msg.agentId) : null;
                    return (
                      <ChatBubble
                        key={i}
                        msg={msg}
                        isUser={msg.role === 'user'}
                        agent={sourceAgent}
                        onAgentClick={setProfileAgent}
                      />
                    );
                  })
                )
              ) : selectedAgent ? (
                history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                    <User className="w-8 h-8 opacity-30" />
                    <p className="text-sm">Chat with {selectedAgent.name.split(' ')[0]}</p>
                  </div>
                ) : (
                  history.map((msg, i) => (
                    <ChatBubble
                      key={i}
                      msg={msg}
                      isUser={msg.role === 'user'}
                      agent={selectedAgent}
                      onAgentClick={setProfileAgent}
                    />
                  ))
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                  <Search className="w-8 h-8 opacity-30" />
                  <p className="text-sm">Select an agent above</p>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border flex gap-2 flex-shrink-0">
              <Input
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    void sendMessage();
                  }
                }}
                placeholder={
                  chatSegment === 'one-on-one' && selectedAgent
                    ? `Ask ${selectedAgent.name.split(' ')[0]}...`
                    : 'Ask the group a question...'
                }
                className="bg-card border-border text-sm h-10"
              />
              <Button
                onClick={() => void sendMessage()}
                size="icon"
                className="h-10 w-10 shrink-0 bg-[hsl(210,100%,56%)] hover:bg-[hsl(210,100%,50%)] text-white border-0"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {profileAgent && (
          <AgentProfileDrawer
            agent={profileAgent}
            posts={activeProfilePosts}
            onClose={() => setProfileAgent(null)}
            onOpenOneToOne={() => openOneToOneChat(profileAgent)}
          />
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function SegmentedControl({ value, options, onChange }: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded border border-border bg-card p-0.5">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded px-3 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            opt.value === value
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function QuickStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-lg font-mono font-medium" style={color ? { color } : { color: 'hsl(var(--foreground))' }}>
        {value}
      </div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.16em]">{label}</div>
    </div>
  );
}

function ThemeCard({ title, color, themes }: { title: string; color: string; themes: any[] }) {
  if (!themes || themes.length === 0) return null;
  return (
    <div className="surface-card p-5">
      <div className="flex items-center gap-2 mb-3">
        {color.includes('green') ? (
          <TrendingUp className="w-3.5 h-3.5" style={{ color }} />
        ) : (
          <TrendingDown className="w-3.5 h-3.5" style={{ color }} />
        )}
        <span className="label-meta" style={{ color }}>{title}</span>
      </div>
      <ul className="space-y-2">
        {themes.map((t: any, i: number) => (
          <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: color }} />
            <span>
              {t.theme || t}
              {t.evidence_count && (
                <span className="text-muted-foreground ml-1">({t.evidence_count} citations)</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChatBubble({
  msg,
  isUser,
  agent,
  onAgentClick,
}: {
  msg: { role: string; content: string };
  isUser: boolean;
  agent?: Agent | null;
  onAgentClick?: (agent: Agent) => void;
}) {
  const agentLabel = agent ? `${agent.name} · ${sentimentLabel(agent.sentiment)}` : 'Agent';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
        isUser
          ? 'bg-[hsl(210,100%,56%)]/15 text-foreground border border-[hsl(210,100%,56%)]/25 rounded-br-sm'
          : 'bg-card border border-border text-foreground/80 rounded-bl-sm'
      }`}>
        {!isUser && (
          <div className="mb-1.5">
            {agent ? (
              <button
                type="button"
                onClick={() => onAgentClick?.(agent)}
                className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-[9px] text-foreground">
                  {agent.name.split(' ').map((name) => name[0]).join('').slice(0, 2)}
                </span>
                <span>{agentLabel}</span>
              </button>
            ) : (
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Agent</span>
            )}
          </div>
        )}
        {msg.content}
      </div>
    </div>
  );
}

function StanceDot({ sentiment }: { sentiment: string }) {
  const color = sentiment === 'positive'
    ? 'bg-[hsl(var(--data-green))]'
    : sentiment === 'negative'
    ? 'bg-[hsl(var(--data-red))]'
    : 'bg-white/30';
  return <span className={`w-2 h-2 rounded-full ${color}`} />;
}

function AgentProfileDrawer({
  agent,
  posts,
  onClose,
  onOpenOneToOne,
}: {
  agent: Agent;
  posts: SimPost[];
  onClose: () => void;
  onOpenOneToOne: () => void;
}) {
  const score = Math.max(1, Math.min(10, Math.round(agent.approvalScore / 10)));
  const scoreColor = agent.sentiment === 'positive'
    ? 'hsl(var(--data-green))'
    : agent.sentiment === 'negative'
    ? 'hsl(var(--data-red))'
    : 'hsl(var(--muted-foreground))';

  return (
    <aside className="absolute inset-y-0 right-0 z-30 w-[340px] border-l border-white/10 bg-[#0B0B0B]/95 backdrop-blur-sm">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Agent Profile</div>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin">
          <div className="surface-card p-4">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 font-mono text-sm text-foreground">
                {agent.name.split(' ').map((name) => name[0]).join('').slice(0, 2)}
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  {agent.name}
                  <BadgeCheck className="h-3.5 w-3.5 text-[hsl(var(--data-blue))]" />
                </div>
                <div className="text-[11px] text-muted-foreground">{sentimentLabel(agent.sentiment)}</div>
              </div>
            </div>

            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2"><BriefcaseBusiness className="h-3.5 w-3.5" /> {agent.occupation}</div>
              <div className="flex items-center gap-2"><MapPin className="h-3.5 w-3.5" /> {agent.planningArea}</div>
              <div className="flex items-center gap-2"><Wallet className="h-3.5 w-3.5" /> {agent.incomeBracket}</div>
              <div className="text-muted-foreground/90">Age {agent.age} · {agent.gender} · {agent.ethnicity}</div>
            </div>
          </div>

          <div className="surface-card p-4">
            <div className="label-meta mb-2">Core Viewpoint</div>
            <p className="text-xs leading-relaxed text-foreground/80">{buildCoreViewpoint(agent)}</p>

            <div className="mt-3 border-t border-border pt-3">
              <div className="mb-2 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <span>Stance Score</span>
                <span style={{ color: scoreColor }}>{score}/10</span>
              </div>
              <div className="h-2 rounded-full bg-white/10">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${score * 10}%`, backgroundColor: scoreColor }}
                />
              </div>
            </div>
          </div>

          <div className="surface-card p-4">
            <div className="label-meta mb-3">Key Posts</div>
            <div className="space-y-3">
              {posts.length > 0 ? posts.map((post) => (
                <div key={post.id} className="rounded border border-white/10 bg-black/20 p-2.5">
                  <div className="text-xs font-medium text-foreground">{post.title}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">▲ {post.upvotes} · ▼ {post.downvotes} · 💬 {post.commentCount}</div>
                </div>
              )) : (
                <div className="text-xs text-muted-foreground">No tracked posts yet for this agent.</div>
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-border p-4">
          <Button onClick={onOpenOneToOne} className="h-10 w-full bg-primary text-primary-foreground">
            Chat 1:1
          </Button>
        </div>
      </div>
    </aside>
  );
}

function sentimentLabel(sentiment: Agent['sentiment']): string {
  if (sentiment === 'positive') return 'Supporter';
  if (sentiment === 'negative') return 'Dissenter';
  return 'Neutral';
}

function buildCoreViewpoint(agent: Agent): string {
  if (agent.sentiment === 'positive') {
    return `${agent.name.split(' ')[0]} generally supports the policy direction, while asking for implementation details that protect everyday households in ${agent.planningArea}.`;
  }
  if (agent.sentiment === 'negative') {
    return `${agent.name.split(' ')[0]} believes the current approach puts disproportionate pressure on working residents and wants stronger cost-of-living safeguards for ${agent.occupation.toLowerCase()} households.`;
  }
  return `${agent.name.split(' ')[0]} sees tradeoffs on both sides and asks for clearer data transparency before committing to a stronger stance.`;
}

function formatCountry(country: string): string {
  const normalized = String(country || '').trim().toLowerCase();
  if (normalized === 'usa') return 'USA';
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : 'Singapore';
}

function formatUseCase(useCase: string): string {
  const normalized = String(useCase || '').trim().toLowerCase();
  if (normalized === 'policy-review') return 'Policy Review';
  if (normalized === 'ad-testing') return 'Ad Testing';
  if (normalized === 'pmf-discovery') return 'PMF Discovery';
  if (normalized === 'reviews') return 'Reviews';
  return 'Policy Review';
}

function getReportMetricDisplay(
  report: StructuredReportState,
  keys: string[],
  kind: 'percent' | 'count' = 'percent',
): string {
  const payload = report as Record<string, unknown>;
  for (const key of keys) {
    const raw = payload[key];
    const value = typeof raw === 'number' ? raw : Number(raw);
    if (!Number.isFinite(value)) continue;
    return kind === 'count' ? `${Math.round(value)}` : `${Number(value).toFixed(1)}%`;
  }
  return '—';
}
===
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  FileText, Loader2, Download, Send, Search, X,
  MessageSquare, Users, User, TrendingUp, TrendingDown,
  AlertTriangle, ArrowRight, BadgeCheck, BriefcaseBusiness, MapPin, Wallet
} from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  StructuredReportState,
  exportReportDocx,
  generateReport,
  getStructuredReport,
  sendAgentChatMessage,
  sendGroupChatMessage,
  isLiveBootMode,
} from '@/lib/console-api';
import { agentResponses, Agent, type SimPost } from '@/data/mockData';
import { toast } from '@/hooks/use-toast';

const POLL_INTERVAL_MS = 1500;

type ViewMode = 'report' | 'split' | 'chat';
type ChatSegment = 'dissenters' | 'supporters' | 'one-on-one';

const EMPTY_REPORT: StructuredReportState = {
  session_id: '',
  status: 'idle',
  generated_at: null,
  executive_summary: null,
  insight_cards: [],
  support_themes: [],
  dissent_themes: [],
  demographic_breakdown: [],
  influential_content: [],
  recommendations: [],
  risks: [],
  error: null,
};

/* ── Mock report data for demo mode ── */
const DEMO_REPORT: StructuredReportState = {
  session_id: 'demo',
  status: 'complete',
  generated_at: new Date().toISOString(),
  executive_summary:
    'The simulation reveals a deeply divided population regarding Budget 2026 policies. Initial approval of 65% eroded to 34% over 5 rounds of discourse, driven primarily by concerns about cost of living, AI-driven job displacement, and insufficient support for gig workers. The most influential agents were dissenters from lower-income brackets who reframed policy benefits as insufficient relative to rising costs.',
  insight_cards: [
    { title: 'Generational Divide', description: 'Under-35s are 29pp less likely to approve than over-55s. Housing and CPF concerns dominate.', icon: 'trend' },
    { title: 'Income Correlation', description: 'Below $4k income bracket shows 35% approval vs 64% for above $8k. Inequality is the key driver.', icon: 'chart' },
    { title: 'Cascade Effect', description: 'A single viral post about AI job displacement shifted 42 agents from supporter to dissenter.', icon: 'alert' },
  ],
  support_themes: [
    { theme: 'AI investment is forward-thinking and positions Singapore competitively', evidence_count: 23 },
    { theme: 'SkillsFuture enhancements address workforce readiness', evidence_count: 18 },
    { theme: 'Family support measures are practical and well-targeted', evidence_count: 15 },
  ],
  dissent_themes: [
    { theme: 'Cost of living not adequately addressed — wage growth lags inflation', evidence_count: 47 },
    { theme: 'AI benefits accrue to top earners while displacing middle-income jobs', evidence_count: 31 },
    { theme: 'Carbon tax increases will hit transport-dependent workers hardest', evidence_count: 22 },
  ],
  demographic_breakdown: [
    { group: '21–30', approval: 38, count: 62 },
    { group: '31–40', approval: 47, count: 58 },
    { group: '41–55', approval: 58, count: 72 },
    { group: '55+', approval: 67, count: 58 },
  ],
  influential_content: [
    { title: 'Innovation hubs only benefit top earners', author: 'Raj Kumar', engagement: 142, shift: -0.42 },
    { title: 'SkillsFuture is a band-aid on structural inequality', author: 'Siti Ibrahim', engagement: 98, shift: -0.28 },
  ],
  recommendations: [
    { title: 'Address cost-of-living gap', description: 'Introduce targeted wage supplements for income brackets below $4,000 to reduce the approval gap.' },
    { title: 'AI transition support', description: 'Create an AI Displacement Fund with retraining credits specifically for middle-income workers in at-risk sectors.' },
    { title: 'Carbon tax rebates', description: 'Expand U-Save rebates and introduce transport subsidies for workers in non-CBD areas.' },
  ],
  risks: [],
  error: null,
};

export default function ReportChat() {
  const {
    sessionId,
    simulationComplete,
    agents,
    simPosts,
    chatHistory,
    addChatMessage,
    completeStep,
    setCurrentStep,
    country,
    useCase,
    simulationRounds,
  } = useApp();
  const liveMode = isLiveBootMode();

  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [reportState, setReportState] = useState<StructuredReportState>(EMPTY_REPORT);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const startedRef = useRef<string | null>(null);

  // Chat state
  const [chatSegment, setChatSegment] = useState<ChatSegment>('dissenters');
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [profileAgent, setProfileAgent] = useState<Agent | null>(null);
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const topSupporters = useMemo(
    () => agents.filter((agent) => agent.sentiment === 'positive').slice(0, 5),
    [agents],
  );
  const topDissenters = useMemo(
    () => agents.filter((agent) => agent.sentiment === 'negative').slice(0, 5),
    [agents],
  );
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);

  const loadDemoReport = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch('/demo-output.json');
      if (response.ok) {
        const data = await response.json();
        if (data?.report || data?.reportFull) {
          const reportFromDemo = data.reportFull || data.report;
          setReportState({ ...DEMO_REPORT, ...reportFromDemo, status: 'complete' });
          return;
        }
      }
    } catch {
      // Fall through to built-in demo report.
    }
    setReportState(DEMO_REPORT);
  }, []);

  // Load demo data if no backend
  useEffect(() => {
    if (isLiveBootMode()) {
      return;
    }
    if (reportState.status === 'idle' && !loading) {
      void loadDemoReport();
    }
  }, [loadDemoReport, reportState.status, loading]);

  const beginReportGeneration = useCallback(async () => {
    if (!sessionId) {
      setReportError('Complete a simulation before generating a report.');
      return;
    }
    startedRef.current = sessionId;
    setLoading(true);
    setReportError(null);
    try {
      const [, polled] = await Promise.all([
        generateReport(sessionId),
        getStructuredReport(sessionId),
      ]);
      setReportState(polled);
    } catch (error) {
      startedRef.current = null;
      if (!isLiveBootMode()) {
        await loadDemoReport();
        setReportError(null);
        toast({
          title: 'Demo report loaded',
          description: error instanceof Error ? `${error.message}. Showing cached demo report.` : 'Backend unavailable. Showing cached demo report.',
        });
      } else {
        const message = error instanceof Error ? error.message : 'Report generation failed.';
        setReportState(EMPTY_REPORT);
        setReportError(message);
        toast({
          title: 'Report generation failed',
          description: message,
          variant: 'destructive',
        });
      }
    } finally {
      setLoading(false);
    }
  }, [loadDemoReport, sessionId]);

  useLayoutEffect(() => {
    if (!simulationComplete || !sessionId) return;
    if (startedRef.current === sessionId) return;
    void beginReportGeneration();
  }, [beginReportGeneration, sessionId, simulationComplete]);

  useEffect(() => {
    if (!sessionId || reportState.status !== 'running') return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getStructuredReport(sessionId);
        setReportState(next);
      } catch { /* ignore */ }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [sessionId, reportState.status]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [chatHistory, selectedAgent]);

  const enqueueDemoGroupReplies = useCallback((threadId: string, responders: Agent[]) => {
    responders.slice(0, 5).forEach((agent, index) => {
      window.setTimeout(() => {
        const responses = agentResponses[agent.sentiment] || agentResponses.neutral;
        const reply = responses[Math.floor(Math.random() * responses.length)];
        addChatMessage(threadId, 'agent', reply, agent.id);
      }, 420 + index * 220 + Math.random() * 300);
    });
  }, [addChatMessage]);

  const enqueueDemoOneToOneReply = useCallback((threadId: string, selected: Agent) => {
    window.setTimeout(() => {
      const responses = agentResponses[selected.sentiment] || agentResponses.neutral;
      const reply = responses[Math.floor(Math.random() * responses.length)];
      addChatMessage(threadId, 'agent', reply, selected.id);
    }, 520 + Math.random() * 500);
  }, [addChatMessage]);

  const sendMessage = useCallback(async () => {
    const trimmed = message.trim();
    if (!trimmed) return;

    if (chatSegment === 'one-on-one') {
      if (!selectedAgent) return;
      const threadId = selectedAgent.id;
      addChatMessage(threadId, 'user', trimmed, selectedAgent.id);
      setMessage('');
      if (!sessionId) {
        enqueueDemoOneToOneReply(threadId, selectedAgent);
        return;
      }
      try {
        const response = await sendAgentChatMessage(sessionId, {
          agent_id: selectedAgent.id,
          message: trimmed,
        });
        if (response.responses.length > 0) {
          response.responses.forEach((entry) => {
            addChatMessage(threadId, 'agent', entry.content, entry.agent_id ?? selectedAgent.id);
          });
          return;
        }
        if (liveMode) {
          toast({
            title: 'Live chat unavailable',
            description: 'The backend returned no agent response.',
            variant: 'destructive',
          });
          return;
        }
        enqueueDemoOneToOneReply(threadId, selectedAgent);
      } catch (error) {
        if (liveMode) {
          toast({
            title: 'Live chat unavailable',
            description: error instanceof Error ? error.message : 'The backend request failed.',
            variant: 'destructive',
          });
          return;
        }
        enqueueDemoOneToOneReply(threadId, selectedAgent);
      }
      return;
    }

    const threadId = `group-${chatSegment}`;
    const responders = chatSegment === 'supporters' ? topSupporters : topDissenters;
    if (!responders.length) {
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: 'No live agents are available for this chat segment.',
          variant: 'destructive',
        });
      }
      return;
    }

    addChatMessage(threadId, 'user', trimmed);
    setMessage('');
    if (!sessionId) {
      enqueueDemoGroupReplies(threadId, responders);
      return;
    }
    try {
      const response = await sendGroupChatMessage(sessionId, {
        segment: chatSegment,
        message: trimmed,
      });
      if (response.responses.length > 0) {
        response.responses.forEach((entry, index) => {
          addChatMessage(
            threadId,
            'agent',
            entry.content,
            entry.agent_id ?? responders[index]?.id,
          );
        });
        return;
      }
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: 'The backend returned no agent responses.',
          variant: 'destructive',
        });
        return;
      }
      enqueueDemoGroupReplies(threadId, responders);
    } catch (error) {
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: error instanceof Error ? error.message : 'The backend request failed.',
          variant: 'destructive',
        });
        return;
      }
      enqueueDemoGroupReplies(threadId, responders);
    }
  }, [
    addChatMessage,
    chatSegment,
    enqueueDemoGroupReplies,
    enqueueDemoOneToOneReply,
    message,
    selectedAgent,
    sessionId,
    liveMode,
    topDissenters,
    topSupporters,
  ]);

  const handleExport = useCallback(async () => {
    if (!sessionId) {
      toast({ title: 'Export failed', description: 'No active session found.' });
      return;
    }
    try {
      const file = await exportReportDocx(sessionId);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `mckainsey-report-${sessionId}.docx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: 'Export unavailable',
        description: error instanceof Error ? error.message : 'Unable to export DOCX right now.',
      });
    }
  }, [sessionId]);

  const handleProceed = useCallback(() => {
    completeStep(4);
    setCurrentStep(5);
  }, [completeStep, setCurrentStep]);

  const report = reportState;
  const filteredAgents = agents.filter(a => {
    const matchSearch = a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.occupation.toLowerCase().includes(search.toLowerCase());
    return matchSearch;
  }).slice(0, 30);

  const activeThreadId = chatSegment === 'one-on-one'
    ? selectedAgent?.id ?? null
    : `group-${chatSegment}`;
  const history = activeThreadId ? (chatHistory[activeThreadId] || []) : [];

  const showReport = viewMode === 'report' || viewMode === 'split';
  const showChat = viewMode === 'chat' || viewMode === 'split';

  const activeProfilePosts = useMemo(() => {
    if (!profileAgent) return [];
    return simPosts
      .filter((post) => post.agentId === profileAgent.id)
      .sort((left, right) => (right.upvotes + right.commentCount) - (left.upvotes + left.commentCount))
      .slice(0, 3);
  }, [profileAgent, simPosts]);

  const openOneToOneChat = useCallback((agent: Agent) => {
    setSelectedAgent(agent);
    setChatSegment('one-on-one');
    setViewMode('split');
    setProfileAgent(null);
  }, []);

  const headerAgentCount = agents.length > 0 ? String(agents.length) : (liveMode ? '—' : '250');
  const agentsSimulated = liveMode
    ? getReportMetricDisplay(report, ['agent_count', 'agents_simulated', 'simulation_agents', 'population_size'], 'count')
    : '250';

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
        <div>
          <h2 className="text-lg font-semibold text-foreground tracking-tight">Analysis Report</h2>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {headerAgentCount} agents · {simulationRounds} rounds
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SegmentedControl
            value={viewMode}
            options={[
              { value: 'report', label: 'Report' },
              { value: 'split', label: 'Report + Chat' },
              { value: 'chat', label: 'Chat' },
            ]}
            onChange={(v) => setViewMode(v as ViewMode)}
          />
          <Button onClick={handleExport} variant="outline" size="sm" className="border-border text-foreground gap-1.5 h-8">
            <Download className="w-3.5 h-3.5" /> Export
          </Button>
          <Button onClick={handleProceed} size="sm" className="bg-success/20 text-success hover:bg-success/30 border border-success/30 h-8 px-4 font-mono uppercase tracking-wider">
            Proceed <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── Report Panel ── */}
        {showReport && (
          <div className={`overflow-y-auto scrollbar-thin p-6 space-y-6 ${showChat ? 'w-[60%] border-r border-border' : 'w-full max-w-4xl mx-auto'}`}>
            {loading ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Generating report...</span>
              </div>
            ) : reportError ? (
              <div className="text-center py-16">
                <AlertTriangle className="w-8 h-8 text-destructive mx-auto mb-3" />
                <p className="text-sm text-destructive">{reportError}</p>
                <Button onClick={beginReportGeneration} variant="outline" className="mt-4 border-border text-foreground">
                  Retry
                </Button>
              </div>
            ) : (
              <>
                {/* Executive Summary */}
                <section className="surface-card p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    <span className="label-meta">Executive Summary</span>
                  </div>
                  <p className="text-sm text-foreground/80 leading-relaxed">
                    {report.executive_summary || 'No summary available.'}
                  </p>
                  {/* Quick stats from new structure */}
                  <div className="mt-4 pt-4 border-t border-border flex items-center gap-6 flex-wrap">
                    <QuickStat label="Agents Simulated" value={agentsSimulated} />
                    <QuickStat label="Rounds" value={String(simulationRounds)} />
                  </div>
                </section>

                {/* Metric Deltas (from analysis_questions) */}
                {(report as any).metric_deltas && (report as any).metric_deltas.length > 0 && (
                  <section>
                    <span className="label-meta block mb-3">Key Metrics</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {((report as any).metric_deltas as any[]).map((delta: any, i: number) => (
                        <div key={i} className="surface-card p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                              {delta.metric_label || delta.metric_name}
                            </span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              delta.direction === 'up' ? 'bg-emerald-500/10 text-emerald-400' :
                              delta.direction === 'down' ? 'bg-red-500/10 text-red-400' :
                              'bg-white/5 text-muted-foreground'
                            }`}>
                              {delta.direction === 'up' ? '▲' : delta.direction === 'down' ? '▼' : '—'} {delta.delta > 0 ? '+' : ''}{delta.delta}{delta.metric_unit || ''}
                            </span>
                          </div>
                          <div className="flex items-baseline gap-2">
                            <span className="text-lg font-mono font-medium text-foreground">
                              {delta.final_value}{delta.metric_unit || ''}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              from {delta.initial_value}{delta.metric_unit || ''}
                            </span>
                          </div>
                          {delta.report_title && (
                            <p className="text-[10px] text-muted-foreground mt-1">{delta.report_title}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Analysis Question Sections */}
                {(report as any).sections && (report as any).sections.length > 0 && (
                  <section className="space-y-4">
                    <span className="label-meta block">Analysis Findings</span>
                    {((report as any).sections as any[]).map((section: any, i: number) => (
                      <div key={i} className="surface-card p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider ${
                            section.type === 'scale' ? 'bg-blue-500/10 text-blue-400' :
                            section.type === 'yes-no' ? 'bg-emerald-500/10 text-emerald-400' :
                            'bg-white/5 text-muted-foreground'
                          }`}>
                            {section.type || 'open-ended'}
                          </span>
                          <span className="text-sm font-medium text-foreground">{section.report_title || section.question}</span>
                        </div>
                        {section.metric && (
                          <div className="flex items-center gap-3 mb-3 px-3 py-2 rounded bg-white/[0.03] border border-white/5">
                            <span className="text-lg font-mono font-medium text-foreground">
                              {section.metric.final_value}{section.metric.metric_unit || ''}
                            </span>
                            <ArrowRight className="w-3 h-3 text-muted-foreground" />
                            <span className={`text-sm font-mono ${
                              section.metric.direction === 'up' ? 'text-emerald-400' :
                              section.metric.direction === 'down' ? 'text-red-400' :
                              'text-muted-foreground'
                            }`}>
                              {section.metric.delta > 0 ? '+' : ''}{section.metric.delta}
                            </span>
                          </div>
                        )}
                        <p className="text-xs text-foreground/80 leading-relaxed">{section.answer}</p>
                      </div>
                    ))}
                  </section>
                )}

                {/* Insight Blocks */}
                {(report as any).insight_blocks && (report as any).insight_blocks.length > 0 && (
                  <section className="space-y-4">
                    <span className="label-meta block">Insight Blocks</span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {((report as any).insight_blocks as any[]).map((block: any, i: number) => (
                        <div key={i} className="surface-card p-5">
                          <div className="flex items-center gap-2 mb-3">
                            <BadgeCheck className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm font-medium text-foreground">{block.title}</span>
                          </div>
                          {block.description && (
                            <p className="text-xs text-muted-foreground mb-3">{block.description}</p>
                          )}
                          {block.data && block.data.status !== 'not_applicable' ? (
                            <InsightBlockData data={block.data} type={block.type} />
                          ) : (
                            <p className="text-xs text-muted-foreground/50 italic">Not applicable for this use case.</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Preset Sections */}
                {(report as any).preset_sections && (report as any).preset_sections.length > 0 && (
                  <section className="space-y-4">
                    {((report as any).preset_sections as any[]).map((preset: any, i: number) => (
                      <div key={i} className="surface-card p-5">
                        <span className="label-meta block mb-3">{preset.title}</span>
                        <p className="text-sm text-foreground/80 leading-relaxed">{preset.answer}</p>
                      </div>
                    ))}
                  </section>
                )}

                {/* Legacy fallback: Insight Cards */}
                {report.insight_cards && report.insight_cards.length > 0 && !(report as any).metric_deltas && (
                  <section>
                    <span className="label-meta block mb-3">Key Insights</span>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {report.insight_cards.map((card: any, i: number) => (
                        <div key={i} className="surface-card p-4">
                          <div className="text-sm font-medium text-foreground mb-1">{card.title || card.headline}</div>
                          <p className="text-xs text-muted-foreground leading-relaxed">{card.description}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Legacy fallback: Supporting vs Dissenting */}
                {!(report as any).sections && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <ThemeCard
                      title="Supporting Views"
                      color="hsl(var(--data-green))"
                      themes={report.support_themes}
                    />
                    <ThemeCard
                      title="Dissenting Views"
                      color="hsl(var(--data-red))"
                      themes={report.dissent_themes}
                    />
                  </div>
                )}

                {/* Legacy fallback: Recommendations */}
                {report.recommendations && report.recommendations.length > 0 && !(report as any).preset_sections && (
                  <section className="surface-card p-5">
                    <span className="label-meta block mb-4">Recommendations</span>
                    <div className="space-y-4">
                      {report.recommendations.map((rec: any, i: number) => (
                        <div key={i} className="flex gap-3">
                          <div className="w-5 h-5 rounded flex items-center justify-center bg-white/5 text-[9px] font-mono text-muted-foreground flex-shrink-0 mt-0.5">
                            {i + 1}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">{rec.title}</div>
                            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{rec.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Chat Panel ── */}
        {showChat && (
          <div className={`flex flex-col ${showReport ? 'w-[40%]' : 'w-full'}`}>
            {/* Chat Header */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Agent Chat</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[hsl(210,100%,56%)]/15 text-[hsl(210,100%,56%)] uppercase tracking-wider">
                  {chatSegment === 'one-on-one' ? '1:1' : 'Group'}
                </span>
              </div>
              {viewMode === 'split' && (
                <button
                  onClick={() => setViewMode('report')}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Segment Tabs */}
            <div className="px-4 py-2.5 border-b border-border flex gap-1.5 flex-shrink-0">
              {(['dissenters', 'supporters', 'one-on-one'] as ChatSegment[]).map(seg => (
                <button
                  key={seg}
                  onClick={() => setChatSegment(seg)}
                  className={`px-3 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    chatSegment === seg
                      ? 'bg-white/10 text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {seg === 'one-on-one' ? '1:1 Chat' : `Top ${seg}`}
                </button>
              ))}
            </div>

            {/* Agent selector for 1:1 */}
            {chatSegment === 'one-on-one' && (
              <div className="px-4 py-2.5 border-b border-border flex-shrink-0">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search agents..."
                    className="pl-9 h-8 text-sm bg-card border-border"
                  />
                </div>
                {search && filteredAgents.length > 0 && (
                  <div className="mt-1.5 max-h-36 overflow-y-auto space-y-0.5 scrollbar-thin">
                    {filteredAgents.map(agent => (
                      <button
                        key={agent.id}
                        onClick={() => { setSelectedAgent(agent); setSearch(''); }}
                        onDoubleClick={() => setProfileAgent(agent)}
                        className={`w-full text-left px-3 py-2 rounded text-xs transition-colors ${
                          selectedAgent?.id === agent.id
                            ? 'bg-white/10 text-foreground'
                            : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'
                        }`}
                      >
                        <span className="font-medium">{agent.name}</span>
                        <span className="text-muted-foreground ml-1.5">{agent.occupation}</span>
                      </button>
                    ))}
                  </div>
                )}
                {selectedAgent && (
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded bg-card border border-border">
                    <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[9px] font-mono text-foreground">
                      {selectedAgent.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                    </div>
                    <button
                      type="button"
                      onClick={() => setProfileAgent(selectedAgent)}
                      className="text-xs text-foreground hover:text-white underline-offset-2 hover:underline"
                    >
                      {selectedAgent.name}
                    </button>
                    <StanceDot sentiment={selectedAgent.sentiment} />
                    <button
                      onClick={() => setSelectedAgent(null)}
                      className="ml-auto text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scrollbar-thin">
              {chatSegment !== 'one-on-one' ? (
                /* Group chat: show a welcome prompt */
                history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                    <Users className="w-8 h-8 opacity-30" />
                    <p className="text-sm">Ask a question to the {chatSegment}</p>
                    <p className="text-[10px] font-mono uppercase tracking-wider opacity-50">
                      Top 5 most influential agents will respond
                    </p>
                  </div>
                ) : (
                  history.map((msg, i) => {
                    const sourceAgent = msg.agentId ? agentsById.get(msg.agentId) : null;
                    return (
                      <ChatBubble
                        key={i}
                        msg={msg}
                        isUser={msg.role === 'user'}
                        agent={sourceAgent}
                        onAgentClick={setProfileAgent}
                      />
                    );
                  })
                )
              ) : selectedAgent ? (
                history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                    <User className="w-8 h-8 opacity-30" />
                    <p className="text-sm">Chat with {selectedAgent.name.split(' ')[0]}</p>
                  </div>
                ) : (
                  history.map((msg, i) => (
                    <ChatBubble
                      key={i}
                      msg={msg}
                      isUser={msg.role === 'user'}
                      agent={selectedAgent}
                      onAgentClick={setProfileAgent}
                    />
                  ))
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                  <Search className="w-8 h-8 opacity-30" />
                  <p className="text-sm">Select an agent above</p>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border flex gap-2 flex-shrink-0">
              <Input
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    void sendMessage();
                  }
                }}
                placeholder={
                  chatSegment === 'one-on-one' && selectedAgent
                    ? `Ask ${selectedAgent.name.split(' ')[0]}...`
                    : 'Ask the group a question...'
                }
                className="bg-card border-border text-sm h-10"
              />
              <Button
                onClick={() => void sendMessage()}
                size="icon"
                className="h-10 w-10 shrink-0 bg-[hsl(210,100%,56%)] hover:bg-[hsl(210,100%,50%)] text-white border-0"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {profileAgent && (
          <AgentProfileDrawer
            agent={profileAgent}
            posts={activeProfilePosts}
            onClose={() => setProfileAgent(null)}
            onOpenOneToOne={() => openOneToOneChat(profileAgent)}
          />
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function SegmentedControl({ value, options, onChange }: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded border border-border bg-card p-0.5">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded px-3 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            opt.value === value
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function QuickStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-lg font-mono font-medium" style={color ? { color } : { color: 'hsl(var(--foreground))' }}>
        {value}
      </div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.16em]">{label}</div>
    </div>
  );
}

function ThemeCard({ title, color, themes }: { title: string; color: string; themes: any[] }) {
  if (!themes || themes.length === 0) return null;
  return (
    <div className="surface-card p-5">
      <div className="flex items-center gap-2 mb-3">
        {color.includes('green') ? (
          <TrendingUp className="w-3.5 h-3.5" style={{ color }} />
        ) : (
          <TrendingDown className="w-3.5 h-3.5" style={{ color }} />
        )}
        <span className="label-meta" style={{ color }}>{title}</span>
      </div>
      <ul className="space-y-2">
        {themes.map((t: any, i: number) => (
          <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: color }} />
            <span>
              {t.theme || t}
              {t.evidence_count && (
                <span className="text-muted-foreground ml-1">({t.evidence_count} citations)</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function InsightBlockData({ data, type }: { data: any; type: string }) {
  if (!data) return null;

  // If data is an array (e.g. pain_points, top_advocates, viral_posts)
  if (Array.isArray(data)) {
    return (
      <ul className="space-y-1.5">
        {data.slice(0, 8).map((item: any, i: number) => (
          <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 bg-white/20" />
            <span>{typeof item === 'string' ? item : JSON.stringify(item)}</span>
          </li>
        ))}
      </ul>
    );
  }

  // If data has items/entries array
  const entries = data.items || data.entries || data.segments || data.rows;
  if (Array.isArray(entries)) {
    return (
      <div className="space-y-2">
        {entries.slice(0, 8).map((entry: any, i: number) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="text-foreground/80 truncate mr-2">
              {entry.label || entry.name || entry.segment || `Item ${i + 1}`}
            </span>
            <span className="font-mono text-muted-foreground flex-shrink-0">
              {entry.value ?? entry.count ?? entry.score ?? ''}
            </span>
          </div>
        ))}
      </div>
    );
  }

  // If data is an object with key-value pairs
  if (typeof data === 'object' && data !== null) {
    const displayKeys = Object.keys(data).filter(k => k !== 'status');
    if (displayKeys.length === 0) return null;
    return (
      <div className="space-y-1.5">
        {displayKeys.slice(0, 8).map((key) => (
          <div key={key} className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{key.replace(/_/g, ' ')}</span>
            <span className="font-mono text-foreground/80">
              {typeof data[key] === 'object' ? JSON.stringify(data[key]).slice(0, 40) : String(data[key])}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return <p className="text-xs text-muted-foreground">{String(data)}</p>;
}

function ChatBubble({
  msg,
  isUser,
  agent,
  onAgentClick,
}: {
  msg: { role: string; content: string };
  isUser: boolean;
  agent?: Agent | null;
  onAgentClick?: (agent: Agent) => void;
}) {
  const agentLabel = agent ? `${agent.name} · ${sentimentLabel(agent.sentiment)}` : 'Agent';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
        isUser
          ? 'bg-[hsl(210,100%,56%)]/15 text-foreground border border-[hsl(210,100%,56%)]/25 rounded-br-sm'
          : 'bg-card border border-border text-foreground/80 rounded-bl-sm'
      }`}>
        {!isUser && (
          <div className="mb-1.5">
            {agent ? (
              <button
                type="button"
                onClick={() => onAgentClick?.(agent)}
                className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-[9px] text-foreground">
                  {agent.name.split(' ').map((name) => name[0]).join('').slice(0, 2)}
                </span>
                <span>{agentLabel}</span>
              </button>
            ) : (
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Agent</span>
            )}
          </div>
        )}
        {msg.content}
      </div>
    </div>
  );
}

function StanceDot({ sentiment }: { sentiment: string }) {
  const color = sentiment === 'positive'
    ? 'bg-[hsl(var(--data-green))]'
    : sentiment === 'negative'
    ? 'bg-[hsl(var(--data-red))]'
    : 'bg-white/30';
  return <span className={`w-2 h-2 rounded-full ${color}`} />;
}

function AgentProfileDrawer({
  agent,
  posts,
  onClose,
  onOpenOneToOne,
}: {
  agent: Agent;
  posts: SimPost[];
  onClose: () => void;
  onOpenOneToOne: () => void;
}) {
  const score = Math.max(1, Math.min(10, Math.round(agent.approvalScore / 10)));
  const scoreColor = agent.sentiment === 'positive'
    ? 'hsl(var(--data-green))'
    : agent.sentiment === 'negative'
    ? 'hsl(var(--data-red))'
    : 'hsl(var(--muted-foreground))';

  return (
    <aside className="absolute inset-y-0 right-0 z-30 w-[340px] border-l border-white/10 bg-[#0B0B0B]/95 backdrop-blur-sm">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Agent Profile</div>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin">
          <div className="surface-card p-4">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 font-mono text-sm text-foreground">
                {agent.name.split(' ').map((name) => name[0]).join('').slice(0, 2)}
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  {agent.name}
                  <BadgeCheck className="h-3.5 w-3.5 text-[hsl(var(--data-blue))]" />
                </div>
                <div className="text-[11px] text-muted-foreground">{sentimentLabel(agent.sentiment)}</div>
              </div>
            </div>

            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2"><BriefcaseBusiness className="h-3.5 w-3.5" /> {agent.occupation}</div>
              <div className="flex items-center gap-2"><MapPin className="h-3.5 w-3.5" /> {agent.planningArea}</div>
              <div className="flex items-center gap-2"><Wallet className="h-3.5 w-3.5" /> {agent.incomeBracket}</div>
              <div className="text-muted-foreground/90">Age {agent.age} · {agent.gender} · {agent.ethnicity}</div>
            </div>
          </div>

          <div className="surface-card p-4">
            <div className="label-meta mb-2">Core Viewpoint</div>
            <p className="text-xs leading-relaxed text-foreground/80">{buildCoreViewpoint(agent)}</p>

            <div className="mt-3 border-t border-border pt-3">
              <div className="mb-2 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <span>Stance Score</span>
                <span style={{ color: scoreColor }}>{score}/10</span>
              </div>
              <div className="h-2 rounded-full bg-white/10">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${score * 10}%`, backgroundColor: scoreColor }}
                />
              </div>
            </div>
          </div>

          <div className="surface-card p-4">
            <div className="label-meta mb-3">Key Posts</div>
            <div className="space-y-3">
              {posts.length > 0 ? posts.map((post) => (
                <div key={post.id} className="rounded border border-white/10 bg-black/20 p-2.5">
                  <div className="text-xs font-medium text-foreground">{post.title}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">▲ {post.upvotes} · ▼ {post.downvotes} · 💬 {post.commentCount}</div>
                </div>
              )) : (
                <div className="text-xs text-muted-foreground">No tracked posts yet for this agent.</div>
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-border p-4">
          <Button onClick={onOpenOneToOne} className="h-10 w-full bg-primary text-primary-foreground">
            Chat 1:1
          </Button>
        </div>
      </div>
    </aside>
  );
}

function sentimentLabel(sentiment: Agent['sentiment']): string {
  if (sentiment === 'positive') return 'Supporter';
  if (sentiment === 'negative') return 'Dissenter';
  return 'Neutral';
}

function buildCoreViewpoint(agent: Agent): string {
  if (agent.sentiment === 'positive') {
    return `${agent.name.split(' ')[0]} generally supports the policy direction, while asking for implementation details that protect everyday households in ${agent.planningArea}.`;
  }
  if (agent.sentiment === 'negative') {
    return `${agent.name.split(' ')[0]} believes the current approach puts disproportionate pressure on working residents and wants stronger cost-of-living safeguards for ${agent.occupation.toLowerCase()} households.`;
  }
  return `${agent.name.split(' ')[0]} sees tradeoffs on both sides and asks for clearer data transparency before committing to a stronger stance.`;
}

function formatCountry(country: string): string {
  const normalized = String(country || '').trim().toLowerCase();
  if (normalized === 'usa') return 'USA';
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : 'Singapore';
}

function formatUseCase(useCase: string): string {
  const normalized = String(useCase || '').trim().toLowerCase();
  if (normalized === 'public-policy-testing') return 'Public Policy Testing';
  if (normalized === 'product-market-research') return 'Product & Market Research';
  if (normalized === 'campaign-content-testing') return 'Campaign & Content Testing';
  // V1 backward compat
  if (normalized === 'policy-review') return 'Public Policy Testing';
  if (normalized === 'ad-testing') return 'Campaign & Content Testing';
  if (normalized === 'pmf-discovery' || normalized === 'reviews') return 'Product & Market Research';
  return 'Public Policy Testing';
}

function getReportMetricDisplay(
  report: StructuredReportState,
  keys: string[],
  kind: 'percent' | 'count' = 'percent',
): string {
  const payload = report as Record<string, unknown>;
  for (const key of keys) {
    const raw = payload[key];
    const value = typeof raw === 'number' ? raw : Number(raw);
    if (!Number.isFinite(value)) continue;
    return kind === 'count' ? `${Math.round(value)}` : `${Number(value).toFixed(1)}%`;
  }
  return '—';
}
```

- **Metric Delta Cards**: Grid with directional arrows (▲/▼), initial→final values
- **Analysis Question Sections**: Type badges + metric spotlight + narrative
- **Insight Blocks**: `InsightBlockData` sub-component renders lists, tables, key-value data
- **Preset Sections**: LLM narrative blocks
- **Legacy fallback**: V1 insight cards, theme cards, recommendations still render when V2 data absent
- Removed unused `initialApproval`/`finalApproval` variables

### Analytics (Screen 3)
```diff:Analytics.tsx
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Flame, GitBranch, Megaphone, Users2 } from "lucide-react";

import { useApp } from "@/contexts/AppContext";
import { generateAgents, type Agent } from "@/data/mockData";
import {
  getAnalyticsCascades,
  getAnalyticsInfluence,
  getAnalyticsOpinionFlow,
  getAnalyticsPolarization,
  isLiveBootMode,
} from "@/lib/console-api";

type PolarizationPoint = {
  round: string;
  index: number;
  severity: "low" | "moderate" | "high";
};

type Stance = "supporter" | "neutral" | "dissenter";
type DemographicDimension = "industry" | "occupation" | "planningArea" | "incomeBracket" | "ageBucket" | "gender";

type OpinionFlowData = {
  initial: Record<Stance, number>;
  final: Record<Stance, number>;
  flows: Array<{ from: Stance; to: Stance; count: number }>;
};

type Leader = {
  name: string;
  stance: Stance | "mixed";
  influence: number;
  topView: string;
  topPost: string;
};

type ViralComment = {
  author: string;
  stance: Stance | "mixed";
  content: string;
  likes: number;
  dislikes: number;
};

type ViralPost = {
  author: string;
  stance: Stance | "mixed";
  title: string;
  content: string;
  likes: number;
  dislikes: number;
  comments: ViralComment[];
};

type DemographicGroup = {
  name: string;
  agents: Agent[];
  supporters: number;
  neutral: number;
  dissenters: number;
};

const POLARIZATION_DATA: PolarizationPoint[] = [
  { round: "R1", index: 0.12, severity: "low" },
  { round: "R2", index: 0.28, severity: "moderate" },
  { round: "R3", index: 0.45, severity: "moderate" },
  { round: "R4", index: 0.67, severity: "high" },
  { round: "R5", index: 0.82, severity: "high" },
];

const OPINION_FLOW: OpinionFlowData = {
  initial: { supporter: 162, neutral: 38, dissenter: 50 },
  final: { supporter: 85, neutral: 12, dissenter: 153 },
  flows: [
    { from: "supporter", to: "supporter", count: 80 },
    { from: "supporter", to: "dissenter", count: 72 },
    { from: "supporter", to: "neutral", count: 10 },
    { from: "neutral", to: "dissenter", count: 30 },
    { from: "neutral", to: "supporter", count: 5 },
    { from: "neutral", to: "neutral", count: 3 },
    { from: "dissenter", to: "dissenter", count: 48 },
    { from: "dissenter", to: "supporter", count: 2 },
  ],
};

const KEY_OPINION_LEADERS: Leader[] = [
  {
    name: "Raj Kumar",
    stance: "dissenter",
    influence: 0.92,
    topView: "Argues the policy disproportionately burdens low-income households and renters.",
    topPost: "Innovation hubs only benefit top earners and push out long-time residents.",
  },
  {
    name: "Siti Ibrahim",
    stance: "dissenter",
    influence: 0.86,
    topView: "Frames the policy as structurally unfair for working families with unstable income.",
    topPost: "If costs keep rising this way, ordinary families cannot keep up.",
  },
  {
    name: "Priya Nair",
    stance: "dissenter",
    influence: 0.79,
    topView: "Highlights service-sector stress and fear of being excluded from policy benefits.",
    topPost: "Support programs are not reaching the people who need them most.",
  },
  {
    name: "Janet Lee",
    stance: "supporter",
    influence: 0.78,
    topView: "Defends policy intent but asks for stronger safeguards and clearer rollout communication.",
    topPost: "The policy can work if implementation is transparent and phased carefully.",
  },
  {
    name: "Ahmad Hassan",
    stance: "supporter",
    influence: 0.73,
    topView: "Supports the direction while pushing for targeted adjustments for vulnerable groups.",
    topPost: "Keep the framework, but improve support for transition costs.",
  },
  {
    name: "Kavitha Pillai",
    stance: "supporter",
    influence: 0.69,
    topView: "Emphasizes long-term macro gains while acknowledging short-term friction.",
    topPost: "Short-term pain can be manageable if the compensations are concrete.",
  },
  {
    name: "Wei Ming Tan",
    stance: "mixed",
    influence: 0.65,
    topView: "Bridges camps by comparing tradeoffs and asking for data-based revisions.",
    topPost: "Can we publish clearer impact metrics by district before full rollout?",
  },
];

const VIRAL_POSTS: ViralPost[] = [
  {
    author: "Raj Kumar",
    stance: "dissenter",
    title: "Innovation hubs only help top earners",
    content:
      "The latest policy package is framed as future-ready, but on the ground it is accelerating rent pressure and squeezing families already near the edge.",
    likes: 142,
    dislikes: 28,
    comments: [
      {
        author: "Tan Li Wei",
        stance: "dissenter",
        content: "I see this in schools too. Families are moving further away and commute stress is rising.",
        likes: 86,
        dislikes: 5,
      },
      {
        author: "Mary Santos",
        stance: "mixed",
        content: "I supported this initially, but this argument changed my view after comparing household costs.",
        likes: 41,
        dislikes: 3,
      },
      {
        author: "Ahmad Y.",
        stance: "dissenter",
        content: "As a driver, this already affects where I can afford to live and work.",
        likes: 67,
        dislikes: 8,
      },
    ],
  },
  {
    author: "Janet Lee",
    stance: "supporter",
    title: "Policy direction is right, but rollout needs guardrails",
    content:
      "I still think the policy can work, but only if there are stronger short-term protections for lower-income households during transition.",
    likes: 120,
    dislikes: 19,
    comments: [
      {
        author: "Kelvin Ho",
        stance: "supporter",
        content: "Agree. Keep the direction, but announce support details upfront.",
        likes: 58,
        dislikes: 6,
      },
      {
        author: "Nora Lim",
        stance: "mixed",
        content: "I am neutral for now. The safeguards decide whether this is fair in practice.",
        likes: 44,
        dislikes: 7,
      },
      {
        author: "Siti Ibrahim",
        stance: "dissenter",
        content: "Without hard protections, this still lands hardest on lower-income workers.",
        likes: 52,
        dislikes: 12,
      },
    ],
  },
  {
    author: "Wei Ming Tan",
    stance: "mixed",
    title: "Show district-level impact data before expansion",
    content:
      "This debate is too abstract. Publish district-level impact metrics and revise the policy where downside risk is highest before scaling nationally.",
    likes: 109,
    dislikes: 11,
    comments: [
      {
        author: "Priya Nair",
        stance: "dissenter",
        content: "This would make accountability real. Right now people feel unheard.",
        likes: 61,
        dislikes: 4,
      },
      {
        author: "Ahmad Hassan",
        stance: "supporter",
        content: "Good compromise: data first, then calibrated rollout by district.",
        likes: 57,
        dislikes: 5,
      },
      {
        author: "Jia Wen",
        stance: "mixed",
        content: "Data transparency might reduce polarization more than any speech campaign.",
        likes: 48,
        dislikes: 3,
      },
    ],
  },
];

const STANCE_ORDER: Stance[] = ["supporter", "neutral", "dissenter"];

export default function Analytics() {
  const { agents, useCase, country, simulationRounds, sessionId } = useApp();
  const liveMode = isLiveBootMode();

  const [dimension, setDimension] = useState<DemographicDimension>(() => defaultDimensionForUseCase(useCase));
  const [polarizationData, setPolarizationData] = useState<PolarizationPoint[]>(() => (liveMode ? [] : POLARIZATION_DATA));
  const [opinionFlowData, setOpinionFlowData] = useState<OpinionFlowData>(() => (liveMode ? { initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] } : OPINION_FLOW));
  const [leaderData, setLeaderData] = useState<Leader[]>(() => (liveMode ? [] : KEY_OPINION_LEADERS));
  const [viralPostData, setViralPostData] = useState<ViralPost[]>(() => (liveMode ? [] : VIRAL_POSTS));
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  useEffect(() => {
    setDimension(defaultDimensionForUseCase(useCase));
  }, [useCase]);

  useEffect(() => {
    const isLive = isLiveBootMode();
    if (!sessionId) {
      if (isLive) {
        setPolarizationData([]);
        setOpinionFlowData({ initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData([]);
        setViralPostData([]);
        setAnalyticsError("Complete Screen 3 before loading live analytics.");
      } else {
        setPolarizationData(POLARIZATION_DATA);
        setOpinionFlowData(OPINION_FLOW);
        setLeaderData(KEY_OPINION_LEADERS);
        setViralPostData(VIRAL_POSTS);
        setAnalyticsError(null);
      }
      setAnalyticsLoading(false);
      return;
    }

    let active = true;
    setAnalyticsLoading(true);
    setAnalyticsError(null);

    void Promise.allSettled([
      getAnalyticsPolarization(sessionId),
      getAnalyticsOpinionFlow(sessionId),
      getAnalyticsInfluence(sessionId),
      getAnalyticsCascades(sessionId),
    ]).then(([polarization, flow, influence, cascades]) => {
      if (!active) return;

      const normalizedPolarization = polarization.status === "fulfilled"
        ? normalizePolarizationPayload(polarization.value)
        : null;
      const normalizedFlow = flow.status === "fulfilled"
        ? normalizeOpinionFlowPayload(flow.value)
        : null;
      const normalizedLeaders = influence.status === "fulfilled"
        ? normalizeLeadersPayload(influence.value)
        : null;
      const normalizedCascades = cascades.status === "fulfilled"
        ? normalizeCascadesPayload(cascades.value)
        : null;

      if (isLive) {
        const hasPolarization = (normalizedPolarization?.length ?? 0) > 0;
        const hasFlow = Boolean(normalizedFlow && normalizedFlow.flows.length > 0);
        const hasLeaders = (normalizedLeaders?.length ?? 0) > 0;
        const hasCascades = (normalizedCascades?.length ?? 0) > 0;

        setPolarizationData(hasPolarization ? normalizedPolarization! : []);
        setOpinionFlowData(hasFlow ? normalizedFlow! : { initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData(hasLeaders ? normalizedLeaders! : []);
        setViralPostData(hasCascades ? normalizedCascades! : []);

        const anyFailure =
          [polarization, flow, influence, cascades].some((entry) => entry.status === "rejected") ||
          !hasPolarization ||
          !hasFlow ||
          !hasLeaders ||
          !hasCascades;
        setAnalyticsError(anyFailure ? "Live analytics returned incomplete data." : null);
      } else {
        setPolarizationData(normalizedPolarization ?? POLARIZATION_DATA);
        setOpinionFlowData(normalizedFlow ?? OPINION_FLOW);
        setLeaderData(normalizedLeaders ?? KEY_OPINION_LEADERS);
        setViralPostData(normalizedCascades ?? VIRAL_POSTS);

        const anyFailure = [polarization, flow, influence, cascades].some((entry) => entry.status === "rejected");
        setAnalyticsError(anyFailure ? "Showing demo analytics data while live analytics is unavailable." : null);
      }
      setAnalyticsLoading(false);
    }).catch(() => {
      if (!active) return;
      if (isLive) {
        setPolarizationData([]);
        setOpinionFlowData({ initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData([]);
        setViralPostData([]);
        setAnalyticsError("Live analytics request failed.");
      } else {
        setPolarizationData(POLARIZATION_DATA);
        setOpinionFlowData(OPINION_FLOW);
        setLeaderData(KEY_OPINION_LEADERS);
        setViralPostData(VIRAL_POSTS);
        setAnalyticsError("Showing demo analytics data while live analytics is unavailable.");
      }
      setAnalyticsLoading(false);
    });

    return () => {
      active = false;
    };
  }, [sessionId]);

  const sourceAgents = useMemo<Agent[]>(() => {
    if (agents.length > 0) return agents;
    if (liveMode) return [];
    if (sessionId) return [];
    return generateAgents(220);
  }, [agents, liveMode, sessionId]);

  const demographicGroups = useMemo(() => {
    const grouped = new Map<string, Agent[]>();

    sourceAgents.forEach((agent: Agent) => {
      const key = resolveDemographicKey(agent, dimension);
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)?.push(agent);
    });

    const groups = Array.from(grouped.entries())
      .sort((left, right) => right[1].length - left[1].length)
      .map(([name, agentsInGroup]) => {
        const supporters = agentsInGroup.filter((agent) => agent.sentiment === "positive").length;
        const dissenters = agentsInGroup.filter((agent) => agent.sentiment === "negative").length;
        const neutral = agentsInGroup.length - supporters - dissenters;

        return {
          name,
          agents: agentsInGroup,
          supporters,
          neutral,
          dissenters,
        } satisfies DemographicGroup;
      });

    const topGroups = groups.slice(0, 10);
    const overflow = groups.slice(10);

    if (overflow.length === 0) return topGroups;

    const overflowAgents = overflow.flatMap((group) => group.agents);
    const supporters = overflowAgents.filter((agent) => agent.sentiment === "positive").length;
    const dissenters = overflowAgents.filter((agent) => agent.sentiment === "negative").length;

    return [
      ...topGroups,
      {
        name: "Other",
        agents: overflowAgents,
        supporters,
        neutral: overflowAgents.length - supporters - dissenters,
        dissenters,
      },
    ];
  }, [dimension, sourceAgents]);

  const dimensionOptions = useMemo(() => {
    if (useCase === "policy-review") {
      return [
        { key: "industry", label: "Industry" },
        { key: "planningArea", label: "Planning Area" },
        { key: "incomeBracket", label: "Income" },
        { key: "ageBucket", label: "Age" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    if (useCase === "ad-testing") {
      return [
        { key: "ageBucket", label: "Age" },
        { key: "incomeBracket", label: "Income" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
        { key: "planningArea", label: "Planning Area" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    return [
      { key: "occupation", label: "Occupation" },
      { key: "industry", label: "Industry" },
      { key: "incomeBracket", label: "Income" },
      { key: "ageBucket", label: "Age" },
      { key: "planningArea", label: "Planning Area" },
      { key: "gender", label: "Gender" },
    ] as Array<{ key: DemographicDimension; label: string }>;
  }, [useCase]);

  const demographicLoading = analyticsLoading && !!sessionId && agents.length === 0;
  const showDemographicEmpty = !demographicLoading && demographicGroups.length === 0;

  return (
    <div className="h-full overflow-y-auto scrollbar-thin bg-background">
      <div className="mx-auto flex w-full max-w-[1700px] flex-col gap-5 px-6 py-6">
        <header className="surface-card px-5 py-4">
          <h2 className="text-xl font-semibold tracking-tight text-white">Simulation Analytics</h2>
          <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {sourceAgents.length} agents · {simulationRounds} rounds
          </p>
        </header>

        {analyticsLoading && (
          <section className="surface-card px-5 py-3">
            <p className="text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              Loading analytics data...
            </p>
          </section>
        )}

        {analyticsError && (
          <section className="surface-card border border-amber-500/30 bg-amber-500/5 px-5 py-3">
            <p className="text-xs text-amber-200">{analyticsError}</p>
          </section>
        )}

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Activity className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">Sentiment Dynamics</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <PolarizationCard data={polarizationData} loading={analyticsLoading} />
            <OpinionFlowCard data={opinionFlowData} loading={analyticsLoading} />
          </div>
        </section>

        <section className="surface-card p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users2 className="h-4 w-4 text-white/70" />
              <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Demographic Sentiment Map</h3>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {dimensionOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setDimension(option.key)}
                  className={`rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    dimension === option.key
                      ? "border-white/25 bg-white/10 text-white"
                      : "border-white/10 text-muted-foreground hover:border-white/20 hover:text-white"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {demographicLoading ? (
            <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              Loading demographic data...
            </div>
          ) : showDemographicEmpty ? (
            <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              No demographic data yet.
            </div>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[hsl(var(--data-green))]" /> Supporter</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-white/35" /> Neutral</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[hsl(var(--data-red))]" /> Dissenter</span>
              </div>

              <div className="flex flex-wrap gap-x-8 gap-y-10">
                {demographicGroups.map((group) => (
                  <div key={group.name} className="flex min-w-[220px] max-w-[340px] shrink-0 flex-col">
                    <div className="mb-3 flex w-full items-baseline justify-between border-b border-white/5 pb-1">
                      <h4 className="max-w-[260px] truncate text-sm font-semibold text-white/90" title={group.name}>{group.name}</h4>
                      <span className="ml-3 rounded bg-white/5 px-2 py-0.5 text-[11px] font-mono text-muted-foreground">{group.agents.length}</span>
                    </div>

                    <div className="mb-3 flex flex-wrap items-center gap-2 text-[10px] font-mono text-muted-foreground">
                      <span className="text-[hsl(var(--data-green))]">{group.supporters}</span>
                      <span className="text-white/35">neutral {group.neutral}</span>
                      <span className="text-[hsl(var(--data-red))]">{group.dissenters}</span>
                    </div>

                    <div className="flex max-w-[340px] flex-wrap gap-1">
                      {group.agents.map((agent) => (
                        <span
                          key={agent.id}
                          className="h-3.5 w-3.5 cursor-crosshair rounded-[2px] border border-black/20 transition-transform hover:z-10 hover:scale-125"
                          style={{ backgroundColor: sentimentColor(agent.sentiment) }}
                          title={`${agent.name} · ${agent.sentiment}`}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Megaphone className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">KOL & Viral Posts</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <KeyOpinionLeadersCard leaders={leaderData} loading={analyticsLoading} />
            <ViralPostsCard posts={viralPostData} loading={analyticsLoading} />
          </div>
        </section>
      </div>
    </div>
  );
}

type PolarizationDotProps = {
  cx?: number;
  cy?: number;
  payload?: PolarizationPoint;
};

function PolarizationDot({ cx, cy, payload }: PolarizationDotProps) {
  if (cx === undefined || cy === undefined || !payload) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill={severityColor(payload.severity)}
      stroke="hsl(0 0% 15%)"
      strokeWidth={2}
    />
  );
}

type PolarizationTooltipProps = {
  active?: boolean;
  label?: string;
  payload?: Array<{ value?: number; payload?: PolarizationPoint }>;
};

function PolarizationTooltip({ active, label, payload }: PolarizationTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const rawValue = Number(payload[0]?.value ?? 0);
  const severity = payload[0]?.payload?.severity ?? "moderate";

  return (
    <div className="min-w-[140px] rounded-md border border-white/15 bg-[#101010] px-3 py-2 text-xs text-white shadow-xl">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/80">{label}</div>
      <div className="mt-1 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-white">{toPercent(rawValue)}</span>
        <span className="text-[10px] font-mono uppercase" style={{ color: severityColor(severity) }}>
          {severity}
        </span>
      </div>
    </div>
  );
}

function PolarizationCard({ data, loading }: { data: PolarizationPoint[]; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Polarization Index" label="Loading polarization data..." />;
  }
  if (data.length === 0) {
    return <EmptyAnalyticsCard title="Polarization Index" label="No polarization data yet." />;
  }
  const safeData = data;
  const latest = safeData[safeData.length - 1];

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-white/70" />
          <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Polarization Index</h3>
        </div>
        <span
          className="rounded px-2 py-1 text-[10px] font-mono uppercase tracking-wider"
          style={{ color: severityColor(latest.severity), backgroundColor: `${severityColor(latest.severity)}20` }}
        >
          {latest.severity === "high" ? "Highly Polarized" : "Low Polarization"}
        </span>
      </div>

      <div className="h-[210px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={safeData} margin={{ top: 8, right: 16, left: -16, bottom: 4 }}>
            <CartesianGrid stroke="hsl(0 0% 16%)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="round" tick={{ fill: "hsl(0 0% 72%)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}
              tick={{ fill: "hsl(0 0% 55%)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<PolarizationTooltip />} cursor={{ stroke: "hsl(0 0% 34%)", strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="index"
              stroke="hsl(0 0% 75%)"
              strokeWidth={2}
              dot={<PolarizationDot />}
              activeDot={{ r: 6, stroke: "hsl(0 0% 36%)", strokeWidth: 2, fill: "hsl(0 0% 14%)" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Higher values indicate the population is splitting into opposing camps rather than converging.
      </p>
    </section>
  );
}

function OpinionFlowCard({ data, loading }: { data: OpinionFlowData; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Opinion Flow" label="Loading opinion flow data..." />;
  }
  if (data.flows.length === 0) {
    return <EmptyAnalyticsCard title="Opinion Flow" label="No opinion flow data yet." />;
  }
  const safeData = data;
  const total = STANCE_ORDER.reduce((sum, stance) => sum + safeData.initial[stance], 0);
  const maxFlow = Math.max(...safeData.flows.map((flow) => flow.count), 1);
  const rowY: Record<Stance, number> = {
    supporter: 28,
    neutral: 86,
    dissenter: 144,
  };

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Opinion Flow</h3>
      </div>

      <div className="grid grid-cols-[94px_minmax(0,1fr)_94px] gap-3">
        <FlowDistributionColumn title="Initial" values={safeData.initial} total={total} />

        <div className="h-[178px] rounded border border-white/10 bg-white/[0.02] p-2">
          <svg viewBox="0 0 220 172" className="h-full w-full" preserveAspectRatio="none">
            {safeData.flows.map((flow, index) => {
              const width = Math.max(2, (flow.count / maxFlow) * 14);
              return (
                <path
                  key={`${flow.from}-${flow.to}-${index}`}
                  d={`M 0 ${rowY[flow.from]} C 80 ${rowY[flow.from]}, 140 ${rowY[flow.to]}, 220 ${rowY[flow.to]}`}
                  fill="none"
                  stroke={stanceColor(flow.to)}
                  strokeOpacity={0.55}
                  strokeWidth={width}
                />
              );
            })}
          </svg>
        </div>

        <FlowDistributionColumn title="Final" values={safeData.final} total={total} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {STANCE_ORDER.map((stance) => (
          <span key={stance} className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: stanceColor(stance) }} />
            {stance}
          </span>
        ))}
      </div>
    </section>
  );
}

function FlowDistributionColumn({
  title,
  values,
  total,
}: {
  title: string;
  values: Record<Stance, number>;
  total: number;
}) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.02] p-2">
      <div className="mb-2 text-center text-[10px] font-mono uppercase tracking-[0.14em] text-white/70">{title}</div>
      <div className="space-y-1.5">
        {STANCE_ORDER.map((stance) => {
          const count = values[stance];
          const percent = count / total;
          const height = Math.max(26, Math.round(percent * 112));
          return (
            <div
              key={stance}
              className="flex items-center justify-center rounded-sm text-[10px] font-mono text-white"
              style={{
                height,
                backgroundColor: stanceColor(stance),
              }}
              title={`${stance}: ${count}`}
            >
              {toPercent(percent)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KeyOpinionLeadersCard({ leaders, loading }: { leaders: Leader[]; loading: boolean }) {
  const sections = useMemo(() => {
    const safeLeaders = leaders;
    const supporters = safeLeaders.filter((leader) => leader.stance === "supporter").slice(0, 3);
    const dissenters = safeLeaders.filter((leader) => leader.stance === "dissenter").slice(0, 3);

    if (supporters.length > 0 && dissenters.length > 0) {
      return [
        { title: "Top Supporters", leaders: supporters },
        { title: "Top Dissenters", leaders: dissenters },
      ];
    }

    return [
      {
        title: "Top Opinion Leaders",
        leaders: [...safeLeaders].sort((left, right) => right.influence - left.influence).slice(0, 3),
      },
    ];
  }, [leaders]);

  if (loading) {
    return <LoadingAnalyticsCard title="Key Opinion Leaders" label="Loading leader data..." />;
  }
  if (leaders.length === 0) {
    return <EmptyAnalyticsCard title="Key Opinion Leaders" label="No leader data yet." />;
  }

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Megaphone className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Key Opinion Leaders</h3>
      </div>

      <div className="space-y-4">
        {sections.map((section) => (
          <div key={section.title} className="space-y-2.5">
            <h4 className="text-[11px] font-mono uppercase tracking-[0.13em] text-white/75">{section.title}</h4>
            {section.leaders.map((leader) => (
              <article key={leader.name} className="rounded border border-white/10 bg-white/[0.02] p-3">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-white">{leader.name}</span>
                  <span
                    className="rounded px-2 py-0.5 text-[10px] font-mono"
                    style={{ color: stanceColor(leader.stance), backgroundColor: `${stanceColor(leader.stance)}1f` }}
                  >
                    {Math.round(leader.influence * 100)}%
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-white/80">{leader.topView}</p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="font-mono uppercase tracking-wide text-white/65">Top Post:</span> {leader.topPost}
                </p>
              </article>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function ViralPostsCard({ posts, loading }: { posts: ViralPost[]; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Viral Posts" label="Loading viral post data..." />;
  }
  if (posts.length === 0) {
    return <EmptyAnalyticsCard title="Viral Posts" label="No viral post data yet." />;
  }
  const safePosts = posts;
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Flame className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Viral Posts</h3>
      </div>

      <div className="space-y-4">
        {safePosts.slice(0, 3).map((post, index) => (
          <article key={`${post.author}-${index}`} className="rounded border border-white/10 bg-white/[0.02] p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">{post.author}</span>
                <span
                  className="rounded px-2 py-0.5 text-[10px] font-mono uppercase"
                  style={{ color: stanceColor(post.stance), backgroundColor: `${stanceColor(post.stance)}1f` }}
                >
                  {post.stance}
                </span>
              </div>
              <span className="text-[10px] font-mono uppercase tracking-[0.12em] text-white/55">Post #{index + 1}</span>
            </div>

            <h4 className="text-sm font-semibold leading-snug text-white">{post.title}</h4>
            <p className="mt-2 text-sm leading-relaxed text-white/80">{post.content}</p>

            <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] font-mono text-muted-foreground">
              <span className="text-[hsl(var(--data-green))]">▲ {post.likes}</span>
              <span className="text-[hsl(var(--data-red))]">▼ {post.dislikes}</span>
              <span className="text-white/70">💬 {post.comments.length} comments</span>
            </div>

            <div className="mt-3 space-y-2 border-l border-white/10 pl-3">
              {post.comments.slice(0, 3).map((comment, commentIndex) => (
                <div key={`${post.author}-comment-${commentIndex}`} className="rounded border border-white/10 bg-black/20 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-white/90">{comment.author}</span>
                    <span
                      className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase"
                      style={{ color: stanceColor(comment.stance), backgroundColor: `${stanceColor(comment.stance)}1f` }}
                    >
                      {comment.stance}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-white/80">{comment.content}</p>
                  <div className="mt-1.5 flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
                    <span className="text-[hsl(var(--data-green))]">▲ {comment.likes}</span>
                    <span className="text-[hsl(var(--data-red))]">▼ {comment.dislikes}</span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LoadingAnalyticsCard({ title, label }: { title: string; label: string }) {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-4 w-4 rounded-full bg-white/10" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">{title}</h3>
      </div>
      <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </div>
    </section>
  );
}

function EmptyAnalyticsCard({ title, label }: { title: string; label: string }) {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-4 w-4 rounded-full bg-white/10" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">{title}</h3>
      </div>
      <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs text-muted-foreground">
        {label}
      </div>
    </section>
  );
}

function normalizePolarizationPayload(payload: Record<string, unknown>): PolarizationPoint[] | null {
  const candidate = payload.points ?? payload.polarization ?? payload.rounds ?? payload.data;
  if (!Array.isArray(candidate)) {
    return null;
  }
  const normalized = candidate
    .map((row, index) => {
      if (!row || typeof row !== "object") return null;
      const data = row as Record<string, unknown>;
      const roundNo = Number(data.round_no ?? data.round ?? index + 1);
      const indexValue = Number(data.index ?? data.polarization_index ?? data.value ?? 0);
      if (!Number.isFinite(indexValue)) return null;
      const severityRaw = String(data.severity ?? "");
      let severity: PolarizationPoint["severity"] = "moderate";
      if (severityRaw === "low") severity = "low";
      if (severityRaw === "high" || severityRaw === "critical") severity = "high";
      return {
        round: typeof data.round === "string" ? data.round : `R${Math.max(1, roundNo)}`,
        index: Math.max(0, Math.min(1, indexValue)),
        severity,
      } satisfies PolarizationPoint;
    })
    .filter((row): row is PolarizationPoint => Boolean(row));
  return normalized;
}

function normalizeOpinionFlowPayload(payload: Record<string, unknown>): OpinionFlowData | null {
  const initial = payload.initial;
  const final = payload.final;
  const flows = payload.flows;
  if (!initial || !final || !Array.isArray(flows)) {
    return null;
  }
  const initialRecord = initial as Record<string, unknown>;
  const finalRecord = final as Record<string, unknown>;
  const normalizedFlows = flows
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const from = String(entry.from ?? "").toLowerCase() as Stance;
      const to = String(entry.to ?? "").toLowerCase() as Stance;
      if (!STANCE_ORDER.includes(from) || !STANCE_ORDER.includes(to)) {
        return null;
      }
      return {
        from,
        to,
        count: Math.max(0, Number(entry.count ?? 0)),
      };
    })
    .filter((row): row is { from: Stance; to: Stance; count: number } => Boolean(row));

  return {
    initial: {
      supporter: Math.max(0, Number(initialRecord.supporter ?? 0)),
      neutral: Math.max(0, Number(initialRecord.neutral ?? 0)),
      dissenter: Math.max(0, Number(initialRecord.dissenter ?? 0)),
    },
    final: {
      supporter: Math.max(0, Number(finalRecord.supporter ?? 0)),
      neutral: Math.max(0, Number(finalRecord.neutral ?? 0)),
      dissenter: Math.max(0, Number(finalRecord.dissenter ?? 0)),
    },
    flows: normalizedFlows,
  };
}

function normalizeLeadersPayload(payload: Record<string, unknown>): Leader[] | null {
  const candidates = payload.top_influencers ?? payload.leaders ?? payload.items;
  if (!Array.isArray(candidates)) {
    return null;
  }
  const normalized = candidates
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const name = String(entry.name ?? entry.agent_name ?? entry.agent_id ?? "").trim();
      if (!name) return null;
      const stanceRaw = String(entry.stance ?? entry.segment ?? "mixed").toLowerCase();
      const stance: Leader["stance"] =
        stanceRaw === "supporter" || stanceRaw === "dissenter" || stanceRaw === "mixed"
          ? stanceRaw
          : "mixed";
      return {
        name,
        stance,
        influence: Number(entry.influence ?? entry.influence_score ?? entry.score ?? 0),
        topView: String(entry.top_view ?? entry.topView ?? entry.core_viewpoint ?? ""),
        topPost: String(entry.top_post ?? entry.topPost ?? entry.example_post ?? ""),
      } satisfies Leader;
    })
    .filter((row): row is Leader => Boolean(row));
  return normalized;
}

function normalizeCascadesPayload(payload: Record<string, unknown>): ViralPost[] | null {
  const candidates = payload.viral_posts ?? payload.cascades ?? payload.top_threads ?? payload.posts;
  if (!Array.isArray(candidates)) {
    return null;
  }
  const normalized = candidates
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const commentsCandidate = entry.comments;
      const comments = Array.isArray(commentsCandidate)
        ? commentsCandidate
            .map((comment) => {
              if (!comment || typeof comment !== "object") return null;
              const commentRow = comment as Record<string, unknown>;
              return {
                author: String(commentRow.author ?? commentRow.agent_name ?? "Agent"),
                stance: normalizeStance(commentRow.stance),
                content: String(commentRow.content ?? commentRow.text ?? ""),
                likes: Math.max(0, Number(commentRow.likes ?? commentRow.upvotes ?? 0)),
                dislikes: Math.max(0, Number(commentRow.dislikes ?? commentRow.downvotes ?? 0)),
              } satisfies ViralComment;
            })
            .filter((comment): comment is ViralComment => Boolean(comment))
        : [];

      return {
        author: String(entry.author ?? entry.author_name ?? "Agent"),
        stance: normalizeStance(entry.stance),
        title: String(entry.title ?? entry.headline ?? "Untitled thread"),
        content: String(entry.content ?? entry.body ?? ""),
        likes: Math.max(0, Number(entry.likes ?? entry.upvotes ?? 0)),
        dislikes: Math.max(0, Number(entry.dislikes ?? entry.downvotes ?? 0)),
        comments,
      } satisfies ViralPost;
    })
    .filter((row): row is ViralPost => Boolean(row));
  return normalized;
}

function normalizeStance(raw: unknown): Stance | "mixed" {
  const stance = String(raw ?? "").toLowerCase();
  if (stance === "supporter" || stance === "dissenter" || stance === "neutral" || stance === "mixed") {
    return stance;
  }
  return "mixed";
}

function stanceColor(stance: Stance | "mixed"): string {
  if (stance === "supporter") return "hsl(var(--data-green))";
  if (stance === "dissenter") return "hsl(var(--data-red))";
  if (stance === "mixed") return "hsl(var(--data-blue))";
  return "hsl(var(--muted-foreground))";
}

function sentimentColor(sentiment: Agent["sentiment"]): string {
  if (sentiment === "positive") return "hsl(var(--data-green))";
  if (sentiment === "negative") return "hsl(var(--data-red))";
  return "hsl(0 0% 45%)";
}

function severityColor(severity: PolarizationPoint["severity"]): string {
  if (severity === "low") return "hsl(var(--data-green))";
  if (severity === "moderate") return "hsl(var(--data-amber))";
  return "hsl(var(--data-red))";
}

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function resolveDemographicKey(agent: Agent, dimension: DemographicDimension): string {
  if (dimension === "planningArea") return agent.planningArea;
  if (dimension === "occupation") return agent.occupation;
  if (dimension === "incomeBracket") return agent.incomeBracket;
  if (dimension === "gender") return agent.gender;
  if (dimension === "ageBucket") {
    if (agent.age <= 24) return "18-24";
    if (agent.age <= 34) return "25-34";
    if (agent.age <= 49) return "35-49";
    if (agent.age <= 64) return "50-64";
    return "65+";
  }
  return inferIndustry(agent.occupation);
}

function inferIndustry(occupation: string): string {
  const normalized = String(occupation || "").toLowerCase();
  if (normalized.includes("teacher") || normalized.includes("school") || normalized.includes("professor")) return "Education";
  if (normalized.includes("nurse") || normalized.includes("doctor") || normalized.includes("health")) return "Healthcare";
  if (normalized.includes("engineer") || normalized.includes("software") || normalized.includes("developer") || normalized.includes("technician")) return "Technology";
  if (normalized.includes("bank") || normalized.includes("account") || normalized.includes("finance")) return "Finance";
  if (normalized.includes("driver") || normalized.includes("transport") || normalized.includes("delivery")) return "Transport";
  if (normalized.includes("civil") || normalized.includes("public") || normalized.includes("government")) return "Public Service";
  if (normalized.includes("manager") || normalized.includes("marketing") || normalized.includes("sales") || normalized.includes("real estate")) return "Business";
  if (normalized.includes("f&b") || normalized.includes("hawker") || normalized.includes("service")) return "Services";
  return "General";
}

function defaultDimensionForUseCase(useCase: string): DemographicDimension {
  if (useCase === "policy-review") return "industry";
  if (useCase === "ad-testing") return "ageBucket";
  if (useCase === "pmf-discovery") return "occupation";
  return "industry";
}

function formatCountry(country: string): string {
  const normalized = String(country || "").trim().toLowerCase();
  if (normalized === "usa") return "USA";
  if (!normalized) return "Singapore";
  return normalized[0].toUpperCase() + normalized.slice(1);
}

function formatUseCase(useCase: string): string {
  const normalized = String(useCase || "").trim().toLowerCase();
  if (normalized === "policy-review") return "Policy Review";
  if (normalized === "ad-testing") return "Ad Testing";
  if (normalized === "pmf-discovery") return "PMF Discovery";
  if (normalized === "reviews") return "Reviews";
  return "Policy Review";
}
===
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Flame, GitBranch, Megaphone, Users2 } from "lucide-react";

import { useApp } from "@/contexts/AppContext";
import { generateAgents, type Agent } from "@/data/mockData";
import {
  getAnalyticsCascades,
  getAnalyticsInfluence,
  getAnalyticsOpinionFlow,
  getAnalyticsPolarization,
  isLiveBootMode,
} from "@/lib/console-api";

type PolarizationPoint = {
  round: string;
  index: number;
  severity: "low" | "moderate" | "high";
};

type Stance = "supporter" | "neutral" | "dissenter";
type DemographicDimension = "industry" | "occupation" | "planningArea" | "incomeBracket" | "ageBucket" | "gender";

type OpinionFlowData = {
  initial: Record<Stance, number>;
  final: Record<Stance, number>;
  flows: Array<{ from: Stance; to: Stance; count: number }>;
};

type Leader = {
  name: string;
  stance: Stance | "mixed";
  influence: number;
  topView: string;
  topPost: string;
};

type ViralComment = {
  author: string;
  stance: Stance | "mixed";
  content: string;
  likes: number;
  dislikes: number;
};

type ViralPost = {
  author: string;
  stance: Stance | "mixed";
  title: string;
  content: string;
  likes: number;
  dislikes: number;
  comments: ViralComment[];
};

type DemographicGroup = {
  name: string;
  agents: Agent[];
  supporters: number;
  neutral: number;
  dissenters: number;
};

const POLARIZATION_DATA: PolarizationPoint[] = [
  { round: "R1", index: 0.12, severity: "low" },
  { round: "R2", index: 0.28, severity: "moderate" },
  { round: "R3", index: 0.45, severity: "moderate" },
  { round: "R4", index: 0.67, severity: "high" },
  { round: "R5", index: 0.82, severity: "high" },
];

const OPINION_FLOW: OpinionFlowData = {
  initial: { supporter: 162, neutral: 38, dissenter: 50 },
  final: { supporter: 85, neutral: 12, dissenter: 153 },
  flows: [
    { from: "supporter", to: "supporter", count: 80 },
    { from: "supporter", to: "dissenter", count: 72 },
    { from: "supporter", to: "neutral", count: 10 },
    { from: "neutral", to: "dissenter", count: 30 },
    { from: "neutral", to: "supporter", count: 5 },
    { from: "neutral", to: "neutral", count: 3 },
    { from: "dissenter", to: "dissenter", count: 48 },
    { from: "dissenter", to: "supporter", count: 2 },
  ],
};

const KEY_OPINION_LEADERS: Leader[] = [
  {
    name: "Raj Kumar",
    stance: "dissenter",
    influence: 0.92,
    topView: "Argues the policy disproportionately burdens low-income households and renters.",
    topPost: "Innovation hubs only benefit top earners and push out long-time residents.",
  },
  {
    name: "Siti Ibrahim",
    stance: "dissenter",
    influence: 0.86,
    topView: "Frames the policy as structurally unfair for working families with unstable income.",
    topPost: "If costs keep rising this way, ordinary families cannot keep up.",
  },
  {
    name: "Priya Nair",
    stance: "dissenter",
    influence: 0.79,
    topView: "Highlights service-sector stress and fear of being excluded from policy benefits.",
    topPost: "Support programs are not reaching the people who need them most.",
  },
  {
    name: "Janet Lee",
    stance: "supporter",
    influence: 0.78,
    topView: "Defends policy intent but asks for stronger safeguards and clearer rollout communication.",
    topPost: "The policy can work if implementation is transparent and phased carefully.",
  },
  {
    name: "Ahmad Hassan",
    stance: "supporter",
    influence: 0.73,
    topView: "Supports the direction while pushing for targeted adjustments for vulnerable groups.",
    topPost: "Keep the framework, but improve support for transition costs.",
  },
  {
    name: "Kavitha Pillai",
    stance: "supporter",
    influence: 0.69,
    topView: "Emphasizes long-term macro gains while acknowledging short-term friction.",
    topPost: "Short-term pain can be manageable if the compensations are concrete.",
  },
  {
    name: "Wei Ming Tan",
    stance: "mixed",
    influence: 0.65,
    topView: "Bridges camps by comparing tradeoffs and asking for data-based revisions.",
    topPost: "Can we publish clearer impact metrics by district before full rollout?",
  },
];

const VIRAL_POSTS: ViralPost[] = [
  {
    author: "Raj Kumar",
    stance: "dissenter",
    title: "Innovation hubs only help top earners",
    content:
      "The latest policy package is framed as future-ready, but on the ground it is accelerating rent pressure and squeezing families already near the edge.",
    likes: 142,
    dislikes: 28,
    comments: [
      {
        author: "Tan Li Wei",
        stance: "dissenter",
        content: "I see this in schools too. Families are moving further away and commute stress is rising.",
        likes: 86,
        dislikes: 5,
      },
      {
        author: "Mary Santos",
        stance: "mixed",
        content: "I supported this initially, but this argument changed my view after comparing household costs.",
        likes: 41,
        dislikes: 3,
      },
      {
        author: "Ahmad Y.",
        stance: "dissenter",
        content: "As a driver, this already affects where I can afford to live and work.",
        likes: 67,
        dislikes: 8,
      },
    ],
  },
  {
    author: "Janet Lee",
    stance: "supporter",
    title: "Policy direction is right, but rollout needs guardrails",
    content:
      "I still think the policy can work, but only if there are stronger short-term protections for lower-income households during transition.",
    likes: 120,
    dislikes: 19,
    comments: [
      {
        author: "Kelvin Ho",
        stance: "supporter",
        content: "Agree. Keep the direction, but announce support details upfront.",
        likes: 58,
        dislikes: 6,
      },
      {
        author: "Nora Lim",
        stance: "mixed",
        content: "I am neutral for now. The safeguards decide whether this is fair in practice.",
        likes: 44,
        dislikes: 7,
      },
      {
        author: "Siti Ibrahim",
        stance: "dissenter",
        content: "Without hard protections, this still lands hardest on lower-income workers.",
        likes: 52,
        dislikes: 12,
      },
    ],
  },
  {
    author: "Wei Ming Tan",
    stance: "mixed",
    title: "Show district-level impact data before expansion",
    content:
      "This debate is too abstract. Publish district-level impact metrics and revise the policy where downside risk is highest before scaling nationally.",
    likes: 109,
    dislikes: 11,
    comments: [
      {
        author: "Priya Nair",
        stance: "dissenter",
        content: "This would make accountability real. Right now people feel unheard.",
        likes: 61,
        dislikes: 4,
      },
      {
        author: "Ahmad Hassan",
        stance: "supporter",
        content: "Good compromise: data first, then calibrated rollout by district.",
        likes: 57,
        dislikes: 5,
      },
      {
        author: "Jia Wen",
        stance: "mixed",
        content: "Data transparency might reduce polarization more than any speech campaign.",
        likes: 48,
        dislikes: 3,
      },
    ],
  },
];

const STANCE_ORDER: Stance[] = ["supporter", "neutral", "dissenter"];

export default function Analytics() {
  const { agents, useCase, country, simulationRounds, sessionId } = useApp();
  const liveMode = isLiveBootMode();

  const [dimension, setDimension] = useState<DemographicDimension>(() => defaultDimensionForUseCase(useCase));
  const [polarizationData, setPolarizationData] = useState<PolarizationPoint[]>(() => (liveMode ? [] : POLARIZATION_DATA));
  const [opinionFlowData, setOpinionFlowData] = useState<OpinionFlowData>(() => (liveMode ? { initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] } : OPINION_FLOW));
  const [leaderData, setLeaderData] = useState<Leader[]>(() => (liveMode ? [] : KEY_OPINION_LEADERS));
  const [viralPostData, setViralPostData] = useState<ViralPost[]>(() => (liveMode ? [] : VIRAL_POSTS));
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  useEffect(() => {
    setDimension(defaultDimensionForUseCase(useCase));
  }, [useCase]);

  useEffect(() => {
    const isLive = isLiveBootMode();
    if (!sessionId) {
      if (isLive) {
        setPolarizationData([]);
        setOpinionFlowData({ initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData([]);
        setViralPostData([]);
        setAnalyticsError("Complete Screen 3 before loading live analytics.");
      } else {
        setPolarizationData(POLARIZATION_DATA);
        setOpinionFlowData(OPINION_FLOW);
        setLeaderData(KEY_OPINION_LEADERS);
        setViralPostData(VIRAL_POSTS);
        setAnalyticsError(null);
      }
      setAnalyticsLoading(false);
      return;
    }

    let active = true;
    setAnalyticsLoading(true);
    setAnalyticsError(null);

    void Promise.allSettled([
      getAnalyticsPolarization(sessionId),
      getAnalyticsOpinionFlow(sessionId),
      getAnalyticsInfluence(sessionId),
      getAnalyticsCascades(sessionId),
    ]).then(([polarization, flow, influence, cascades]) => {
      if (!active) return;

      const normalizedPolarization = polarization.status === "fulfilled"
        ? normalizePolarizationPayload(polarization.value)
        : null;
      const normalizedFlow = flow.status === "fulfilled"
        ? normalizeOpinionFlowPayload(flow.value)
        : null;
      const normalizedLeaders = influence.status === "fulfilled"
        ? normalizeLeadersPayload(influence.value)
        : null;
      const normalizedCascades = cascades.status === "fulfilled"
        ? normalizeCascadesPayload(cascades.value)
        : null;

      if (isLive) {
        const hasPolarization = (normalizedPolarization?.length ?? 0) > 0;
        const hasFlow = Boolean(normalizedFlow && normalizedFlow.flows.length > 0);
        const hasLeaders = (normalizedLeaders?.length ?? 0) > 0;
        const hasCascades = (normalizedCascades?.length ?? 0) > 0;

        setPolarizationData(hasPolarization ? normalizedPolarization! : []);
        setOpinionFlowData(hasFlow ? normalizedFlow! : { initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData(hasLeaders ? normalizedLeaders! : []);
        setViralPostData(hasCascades ? normalizedCascades! : []);

        const anyFailure =
          [polarization, flow, influence, cascades].some((entry) => entry.status === "rejected") ||
          !hasPolarization ||
          !hasFlow ||
          !hasLeaders ||
          !hasCascades;
        setAnalyticsError(anyFailure ? "Live analytics returned incomplete data." : null);
      } else {
        setPolarizationData(normalizedPolarization ?? POLARIZATION_DATA);
        setOpinionFlowData(normalizedFlow ?? OPINION_FLOW);
        setLeaderData(normalizedLeaders ?? KEY_OPINION_LEADERS);
        setViralPostData(normalizedCascades ?? VIRAL_POSTS);

        const anyFailure = [polarization, flow, influence, cascades].some((entry) => entry.status === "rejected");
        setAnalyticsError(anyFailure ? "Showing demo analytics data while live analytics is unavailable." : null);
      }
      setAnalyticsLoading(false);
    }).catch(() => {
      if (!active) return;
      if (isLive) {
        setPolarizationData([]);
        setOpinionFlowData({ initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData([]);
        setViralPostData([]);
        setAnalyticsError("Live analytics request failed.");
      } else {
        setPolarizationData(POLARIZATION_DATA);
        setOpinionFlowData(OPINION_FLOW);
        setLeaderData(KEY_OPINION_LEADERS);
        setViralPostData(VIRAL_POSTS);
        setAnalyticsError("Showing demo analytics data while live analytics is unavailable.");
      }
      setAnalyticsLoading(false);
    });

    return () => {
      active = false;
    };
  }, [sessionId]);

  const sourceAgents = useMemo<Agent[]>(() => {
    if (agents.length > 0) return agents;
    if (liveMode) return [];
    if (sessionId) return [];
    return generateAgents(220);
  }, [agents, liveMode, sessionId]);

  const demographicGroups = useMemo(() => {
    const grouped = new Map<string, Agent[]>();

    sourceAgents.forEach((agent: Agent) => {
      const key = resolveDemographicKey(agent, dimension);
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)?.push(agent);
    });

    const groups = Array.from(grouped.entries())
      .sort((left, right) => right[1].length - left[1].length)
      .map(([name, agentsInGroup]) => {
        const supporters = agentsInGroup.filter((agent) => agent.sentiment === "positive").length;
        const dissenters = agentsInGroup.filter((agent) => agent.sentiment === "negative").length;
        const neutral = agentsInGroup.length - supporters - dissenters;

        return {
          name,
          agents: agentsInGroup,
          supporters,
          neutral,
          dissenters,
        } satisfies DemographicGroup;
      });

    const topGroups = groups.slice(0, 10);
    const overflow = groups.slice(10);

    if (overflow.length === 0) return topGroups;

    const overflowAgents = overflow.flatMap((group) => group.agents);
    const supporters = overflowAgents.filter((agent) => agent.sentiment === "positive").length;
    const dissenters = overflowAgents.filter((agent) => agent.sentiment === "negative").length;

    return [
      ...topGroups,
      {
        name: "Other",
        agents: overflowAgents,
        supporters,
        neutral: overflowAgents.length - supporters - dissenters,
        dissenters,
      },
    ];
  }, [dimension, sourceAgents]);

  const dimensionOptions = useMemo(() => {
    if (useCase === "public-policy-testing" || useCase === "policy-review") {
      return [
        { key: "industry", label: "Industry" },
        { key: "planningArea", label: "Planning Area" },
        { key: "incomeBracket", label: "Income" },
        { key: "ageBucket", label: "Age" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    if (useCase === "campaign-content-testing" || useCase === "ad-testing") {
      return [
        { key: "ageBucket", label: "Age" },
        { key: "incomeBracket", label: "Income" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
        { key: "planningArea", label: "Planning Area" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    return [
      { key: "occupation", label: "Occupation" },
      { key: "industry", label: "Industry" },
      { key: "incomeBracket", label: "Income" },
      { key: "ageBucket", label: "Age" },
      { key: "planningArea", label: "Planning Area" },
      { key: "gender", label: "Gender" },
    ] as Array<{ key: DemographicDimension; label: string }>;
  }, [useCase]);

  const demographicLoading = analyticsLoading && !!sessionId && agents.length === 0;
  const showDemographicEmpty = !demographicLoading && demographicGroups.length === 0;

  return (
    <div className="h-full overflow-y-auto scrollbar-thin bg-background">
      <div className="mx-auto flex w-full max-w-[1700px] flex-col gap-5 px-6 py-6">
        <header className="surface-card px-5 py-4">
          <h2 className="text-xl font-semibold tracking-tight text-white">Simulation Analytics</h2>
          <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {sourceAgents.length} agents · {simulationRounds} rounds
          </p>
        </header>

        {analyticsLoading && (
          <section className="surface-card px-5 py-3">
            <p className="text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              Loading analytics data...
            </p>
          </section>
        )}

        {analyticsError && (
          <section className="surface-card border border-amber-500/30 bg-amber-500/5 px-5 py-3">
            <p className="text-xs text-amber-200">{analyticsError}</p>
          </section>
        )}

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Activity className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">Sentiment Dynamics</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <PolarizationCard data={polarizationData} loading={analyticsLoading} />
            <OpinionFlowCard data={opinionFlowData} loading={analyticsLoading} />
          </div>
        </section>

        <section className="surface-card p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users2 className="h-4 w-4 text-white/70" />
              <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Demographic Sentiment Map</h3>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {dimensionOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setDimension(option.key)}
                  className={`rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    dimension === option.key
                      ? "border-white/25 bg-white/10 text-white"
                      : "border-white/10 text-muted-foreground hover:border-white/20 hover:text-white"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {demographicLoading ? (
            <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              Loading demographic data...
            </div>
          ) : showDemographicEmpty ? (
            <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              No demographic data yet.
            </div>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[hsl(var(--data-green))]" /> Supporter</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-white/35" /> Neutral</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[hsl(var(--data-red))]" /> Dissenter</span>
              </div>

              <div className="flex flex-wrap gap-x-8 gap-y-10">
                {demographicGroups.map((group) => (
                  <div key={group.name} className="flex min-w-[220px] max-w-[340px] shrink-0 flex-col">
                    <div className="mb-3 flex w-full items-baseline justify-between border-b border-white/5 pb-1">
                      <h4 className="max-w-[260px] truncate text-sm font-semibold text-white/90" title={group.name}>{group.name}</h4>
                      <span className="ml-3 rounded bg-white/5 px-2 py-0.5 text-[11px] font-mono text-muted-foreground">{group.agents.length}</span>
                    </div>

                    <div className="mb-3 flex flex-wrap items-center gap-2 text-[10px] font-mono text-muted-foreground">
                      <span className="text-[hsl(var(--data-green))]">{group.supporters}</span>
                      <span className="text-white/35">neutral {group.neutral}</span>
                      <span className="text-[hsl(var(--data-red))]">{group.dissenters}</span>
                    </div>

                    <div className="flex max-w-[340px] flex-wrap gap-1">
                      {group.agents.map((agent) => (
                        <span
                          key={agent.id}
                          className="h-3.5 w-3.5 cursor-crosshair rounded-[2px] border border-black/20 transition-transform hover:z-10 hover:scale-125"
                          style={{ backgroundColor: sentimentColor(agent.sentiment) }}
                          title={`${agent.name} · ${agent.sentiment}`}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Megaphone className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">KOL & Viral Posts</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <KeyOpinionLeadersCard leaders={leaderData} loading={analyticsLoading} />
            <ViralPostsCard posts={viralPostData} loading={analyticsLoading} />
          </div>
        </section>
      </div>
    </div>
  );
}

type PolarizationDotProps = {
  cx?: number;
  cy?: number;
  payload?: PolarizationPoint;
};

function PolarizationDot({ cx, cy, payload }: PolarizationDotProps) {
  if (cx === undefined || cy === undefined || !payload) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill={severityColor(payload.severity)}
      stroke="hsl(0 0% 15%)"
      strokeWidth={2}
    />
  );
}

type PolarizationTooltipProps = {
  active?: boolean;
  label?: string;
  payload?: Array<{ value?: number; payload?: PolarizationPoint }>;
};

function PolarizationTooltip({ active, label, payload }: PolarizationTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const rawValue = Number(payload[0]?.value ?? 0);
  const severity = payload[0]?.payload?.severity ?? "moderate";

  return (
    <div className="min-w-[140px] rounded-md border border-white/15 bg-[#101010] px-3 py-2 text-xs text-white shadow-xl">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/80">{label}</div>
      <div className="mt-1 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-white">{toPercent(rawValue)}</span>
        <span className="text-[10px] font-mono uppercase" style={{ color: severityColor(severity) }}>
          {severity}
        </span>
      </div>
    </div>
  );
}

function PolarizationCard({ data, loading }: { data: PolarizationPoint[]; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Polarization Index" label="Loading polarization data..." />;
  }
  if (data.length === 0) {
    return <EmptyAnalyticsCard title="Polarization Index" label="No polarization data yet." />;
  }
  const safeData = data;
  const latest = safeData[safeData.length - 1];

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-white/70" />
          <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Polarization Index</h3>
        </div>
        <span
          className="rounded px-2 py-1 text-[10px] font-mono uppercase tracking-wider"
          style={{ color: severityColor(latest.severity), backgroundColor: `${severityColor(latest.severity)}20` }}
        >
          {latest.severity === "high" ? "Highly Polarized" : "Low Polarization"}
        </span>
      </div>

      <div className="h-[210px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={safeData} margin={{ top: 8, right: 16, left: -16, bottom: 4 }}>
            <CartesianGrid stroke="hsl(0 0% 16%)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="round" tick={{ fill: "hsl(0 0% 72%)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}
              tick={{ fill: "hsl(0 0% 55%)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<PolarizationTooltip />} cursor={{ stroke: "hsl(0 0% 34%)", strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="index"
              stroke="hsl(0 0% 75%)"
              strokeWidth={2}
              dot={<PolarizationDot />}
              activeDot={{ r: 6, stroke: "hsl(0 0% 36%)", strokeWidth: 2, fill: "hsl(0 0% 14%)" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Higher values indicate the population is splitting into opposing camps rather than converging.
      </p>
    </section>
  );
}

function OpinionFlowCard({ data, loading }: { data: OpinionFlowData; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Opinion Flow" label="Loading opinion flow data..." />;
  }
  if (data.flows.length === 0) {
    return <EmptyAnalyticsCard title="Opinion Flow" label="No opinion flow data yet." />;
  }
  const safeData = data;
  const total = STANCE_ORDER.reduce((sum, stance) => sum + safeData.initial[stance], 0);
  const maxFlow = Math.max(...safeData.flows.map((flow) => flow.count), 1);
  const rowY: Record<Stance, number> = {
    supporter: 28,
    neutral: 86,
    dissenter: 144,
  };

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Opinion Flow</h3>
      </div>

      <div className="grid grid-cols-[94px_minmax(0,1fr)_94px] gap-3">
        <FlowDistributionColumn title="Initial" values={safeData.initial} total={total} />

        <div className="h-[178px] rounded border border-white/10 bg-white/[0.02] p-2">
          <svg viewBox="0 0 220 172" className="h-full w-full" preserveAspectRatio="none">
            {safeData.flows.map((flow, index) => {
              const width = Math.max(2, (flow.count / maxFlow) * 14);
              return (
                <path
                  key={`${flow.from}-${flow.to}-${index}`}
                  d={`M 0 ${rowY[flow.from]} C 80 ${rowY[flow.from]}, 140 ${rowY[flow.to]}, 220 ${rowY[flow.to]}`}
                  fill="none"
                  stroke={stanceColor(flow.to)}
                  strokeOpacity={0.55}
                  strokeWidth={width}
                />
              );
            })}
          </svg>
        </div>

        <FlowDistributionColumn title="Final" values={safeData.final} total={total} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {STANCE_ORDER.map((stance) => (
          <span key={stance} className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: stanceColor(stance) }} />
            {stance}
          </span>
        ))}
      </div>
    </section>
  );
}

function FlowDistributionColumn({
  title,
  values,
  total,
}: {
  title: string;
  values: Record<Stance, number>;
  total: number;
}) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.02] p-2">
      <div className="mb-2 text-center text-[10px] font-mono uppercase tracking-[0.14em] text-white/70">{title}</div>
      <div className="space-y-1.5">
        {STANCE_ORDER.map((stance) => {
          const count = values[stance];
          const percent = count / total;
          const height = Math.max(26, Math.round(percent * 112));
          return (
            <div
              key={stance}
              className="flex items-center justify-center rounded-sm text-[10px] font-mono text-white"
              style={{
                height,
                backgroundColor: stanceColor(stance),
              }}
              title={`${stance}: ${count}`}
            >
              {toPercent(percent)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KeyOpinionLeadersCard({ leaders, loading }: { leaders: Leader[]; loading: boolean }) {
  const sections = useMemo(() => {
    const safeLeaders = leaders;
    const supporters = safeLeaders.filter((leader) => leader.stance === "supporter").slice(0, 3);
    const dissenters = safeLeaders.filter((leader) => leader.stance === "dissenter").slice(0, 3);

    if (supporters.length > 0 && dissenters.length > 0) {
      return [
        { title: "Top Supporters", leaders: supporters },
        { title: "Top Dissenters", leaders: dissenters },
      ];
    }

    return [
      {
        title: "Top Opinion Leaders",
        leaders: [...safeLeaders].sort((left, right) => right.influence - left.influence).slice(0, 3),
      },
    ];
  }, [leaders]);

  if (loading) {
    return <LoadingAnalyticsCard title="Key Opinion Leaders" label="Loading leader data..." />;
  }
  if (leaders.length === 0) {
    return <EmptyAnalyticsCard title="Key Opinion Leaders" label="No leader data yet." />;
  }

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Megaphone className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Key Opinion Leaders</h3>
      </div>

      <div className="space-y-4">
        {sections.map((section) => (
          <div key={section.title} className="space-y-2.5">
            <h4 className="text-[11px] font-mono uppercase tracking-[0.13em] text-white/75">{section.title}</h4>
            {section.leaders.map((leader) => (
              <article key={leader.name} className="rounded border border-white/10 bg-white/[0.02] p-3">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-white">{leader.name}</span>
                  <span
                    className="rounded px-2 py-0.5 text-[10px] font-mono"
                    style={{ color: stanceColor(leader.stance), backgroundColor: `${stanceColor(leader.stance)}1f` }}
                  >
                    {Math.round(leader.influence * 100)}%
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-white/80">{leader.topView}</p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="font-mono uppercase tracking-wide text-white/65">Top Post:</span> {leader.topPost}
                </p>
              </article>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function ViralPostsCard({ posts, loading }: { posts: ViralPost[]; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Viral Posts" label="Loading viral post data..." />;
  }
  if (posts.length === 0) {
    return <EmptyAnalyticsCard title="Viral Posts" label="No viral post data yet." />;
  }
  const safePosts = posts;
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Flame className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Viral Posts</h3>
      </div>

      <div className="space-y-4">
        {safePosts.slice(0, 3).map((post, index) => (
          <article key={`${post.author}-${index}`} className="rounded border border-white/10 bg-white/[0.02] p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">{post.author}</span>
                <span
                  className="rounded px-2 py-0.5 text-[10px] font-mono uppercase"
                  style={{ color: stanceColor(post.stance), backgroundColor: `${stanceColor(post.stance)}1f` }}
                >
                  {post.stance}
                </span>
              </div>
              <span className="text-[10px] font-mono uppercase tracking-[0.12em] text-white/55">Post #{index + 1}</span>
            </div>

            <h4 className="text-sm font-semibold leading-snug text-white">{post.title}</h4>
            <p className="mt-2 text-sm leading-relaxed text-white/80">{post.content}</p>

            <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] font-mono text-muted-foreground">
              <span className="text-[hsl(var(--data-green))]">▲ {post.likes}</span>
              <span className="text-[hsl(var(--data-red))]">▼ {post.dislikes}</span>
              <span className="text-white/70">💬 {post.comments.length} comments</span>
            </div>

            <div className="mt-3 space-y-2 border-l border-white/10 pl-3">
              {post.comments.slice(0, 3).map((comment, commentIndex) => (
                <div key={`${post.author}-comment-${commentIndex}`} className="rounded border border-white/10 bg-black/20 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-white/90">{comment.author}</span>
                    <span
                      className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase"
                      style={{ color: stanceColor(comment.stance), backgroundColor: `${stanceColor(comment.stance)}1f` }}
                    >
                      {comment.stance}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-white/80">{comment.content}</p>
                  <div className="mt-1.5 flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
                    <span className="text-[hsl(var(--data-green))]">▲ {comment.likes}</span>
                    <span className="text-[hsl(var(--data-red))]">▼ {comment.dislikes}</span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LoadingAnalyticsCard({ title, label }: { title: string; label: string }) {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-4 w-4 rounded-full bg-white/10" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">{title}</h3>
      </div>
      <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </div>
    </section>
  );
}

function EmptyAnalyticsCard({ title, label }: { title: string; label: string }) {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-4 w-4 rounded-full bg-white/10" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">{title}</h3>
      </div>
      <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs text-muted-foreground">
        {label}
      </div>
    </section>
  );
}

function normalizePolarizationPayload(payload: Record<string, unknown>): PolarizationPoint[] | null {
  const candidate = payload.points ?? payload.polarization ?? payload.rounds ?? payload.data;
  if (!Array.isArray(candidate)) {
    return null;
  }
  const normalized = candidate
    .map((row, index) => {
      if (!row || typeof row !== "object") return null;
      const data = row as Record<string, unknown>;
      const roundNo = Number(data.round_no ?? data.round ?? index + 1);
      const indexValue = Number(data.index ?? data.polarization_index ?? data.value ?? 0);
      if (!Number.isFinite(indexValue)) return null;
      const severityRaw = String(data.severity ?? "");
      let severity: PolarizationPoint["severity"] = "moderate";
      if (severityRaw === "low") severity = "low";
      if (severityRaw === "high" || severityRaw === "critical") severity = "high";
      return {
        round: typeof data.round === "string" ? data.round : `R${Math.max(1, roundNo)}`,
        index: Math.max(0, Math.min(1, indexValue)),
        severity,
      } satisfies PolarizationPoint;
    })
    .filter((row): row is PolarizationPoint => Boolean(row));
  return normalized;
}

function normalizeOpinionFlowPayload(payload: Record<string, unknown>): OpinionFlowData | null {
  const initial = payload.initial;
  const final = payload.final;
  const flows = payload.flows;
  if (!initial || !final || !Array.isArray(flows)) {
    return null;
  }
  const initialRecord = initial as Record<string, unknown>;
  const finalRecord = final as Record<string, unknown>;
  const normalizedFlows = flows
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const from = String(entry.from ?? "").toLowerCase() as Stance;
      const to = String(entry.to ?? "").toLowerCase() as Stance;
      if (!STANCE_ORDER.includes(from) || !STANCE_ORDER.includes(to)) {
        return null;
      }
      return {
        from,
        to,
        count: Math.max(0, Number(entry.count ?? 0)),
      };
    })
    .filter((row): row is { from: Stance; to: Stance; count: number } => Boolean(row));

  return {
    initial: {
      supporter: Math.max(0, Number(initialRecord.supporter ?? 0)),
      neutral: Math.max(0, Number(initialRecord.neutral ?? 0)),
      dissenter: Math.max(0, Number(initialRecord.dissenter ?? 0)),
    },
    final: {
      supporter: Math.max(0, Number(finalRecord.supporter ?? 0)),
      neutral: Math.max(0, Number(finalRecord.neutral ?? 0)),
      dissenter: Math.max(0, Number(finalRecord.dissenter ?? 0)),
    },
    flows: normalizedFlows,
  };
}

function normalizeLeadersPayload(payload: Record<string, unknown>): Leader[] | null {
  const candidates = payload.top_influencers ?? payload.leaders ?? payload.items;
  if (!Array.isArray(candidates)) {
    return null;
  }
  const normalized = candidates
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const name = String(entry.name ?? entry.agent_name ?? entry.agent_id ?? "").trim();
      if (!name) return null;
      const stanceRaw = String(entry.stance ?? entry.segment ?? "mixed").toLowerCase();
      const stance: Leader["stance"] =
        stanceRaw === "supporter" || stanceRaw === "dissenter" || stanceRaw === "mixed"
          ? stanceRaw
          : "mixed";
      return {
        name,
        stance,
        influence: Number(entry.influence ?? entry.influence_score ?? entry.score ?? 0),
        topView: String(entry.top_view ?? entry.topView ?? entry.core_viewpoint ?? ""),
        topPost: String(entry.top_post ?? entry.topPost ?? entry.example_post ?? ""),
      } satisfies Leader;
    })
    .filter((row): row is Leader => Boolean(row));
  return normalized;
}

function normalizeCascadesPayload(payload: Record<string, unknown>): ViralPost[] | null {
  const candidates = payload.viral_posts ?? payload.cascades ?? payload.top_threads ?? payload.posts;
  if (!Array.isArray(candidates)) {
    return null;
  }
  const normalized = candidates
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const commentsCandidate = entry.comments;
      const comments = Array.isArray(commentsCandidate)
        ? commentsCandidate
            .map((comment) => {
              if (!comment || typeof comment !== "object") return null;
              const commentRow = comment as Record<string, unknown>;
              return {
                author: String(commentRow.author ?? commentRow.agent_name ?? "Agent"),
                stance: normalizeStance(commentRow.stance),
                content: String(commentRow.content ?? commentRow.text ?? ""),
                likes: Math.max(0, Number(commentRow.likes ?? commentRow.upvotes ?? 0)),
                dislikes: Math.max(0, Number(commentRow.dislikes ?? commentRow.downvotes ?? 0)),
              } satisfies ViralComment;
            })
            .filter((comment): comment is ViralComment => Boolean(comment))
        : [];

      return {
        author: String(entry.author ?? entry.author_name ?? "Agent"),
        stance: normalizeStance(entry.stance),
        title: String(entry.title ?? entry.headline ?? "Untitled thread"),
        content: String(entry.content ?? entry.body ?? ""),
        likes: Math.max(0, Number(entry.likes ?? entry.upvotes ?? 0)),
        dislikes: Math.max(0, Number(entry.dislikes ?? entry.downvotes ?? 0)),
        comments,
      } satisfies ViralPost;
    })
    .filter((row): row is ViralPost => Boolean(row));
  return normalized;
}

function normalizeStance(raw: unknown): Stance | "mixed" {
  const stance = String(raw ?? "").toLowerCase();
  if (stance === "supporter" || stance === "dissenter" || stance === "neutral" || stance === "mixed") {
    return stance;
  }
  return "mixed";
}

function stanceColor(stance: Stance | "mixed"): string {
  if (stance === "supporter") return "hsl(var(--data-green))";
  if (stance === "dissenter") return "hsl(var(--data-red))";
  if (stance === "mixed") return "hsl(var(--data-blue))";
  return "hsl(var(--muted-foreground))";
}

function sentimentColor(sentiment: Agent["sentiment"]): string {
  if (sentiment === "positive") return "hsl(var(--data-green))";
  if (sentiment === "negative") return "hsl(var(--data-red))";
  return "hsl(0 0% 45%)";
}

function severityColor(severity: PolarizationPoint["severity"]): string {
  if (severity === "low") return "hsl(var(--data-green))";
  if (severity === "moderate") return "hsl(var(--data-amber))";
  return "hsl(var(--data-red))";
}

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function resolveDemographicKey(agent: Agent, dimension: DemographicDimension): string {
  if (dimension === "planningArea") return agent.planningArea;
  if (dimension === "occupation") return agent.occupation;
  if (dimension === "incomeBracket") return agent.incomeBracket;
  if (dimension === "gender") return agent.gender;
  if (dimension === "ageBucket") {
    if (agent.age <= 24) return "18-24";
    if (agent.age <= 34) return "25-34";
    if (agent.age <= 49) return "35-49";
    if (agent.age <= 64) return "50-64";
    return "65+";
  }
  return inferIndustry(agent.occupation);
}

function inferIndustry(occupation: string): string {
  const normalized = String(occupation || "").toLowerCase();
  if (normalized.includes("teacher") || normalized.includes("school") || normalized.includes("professor")) return "Education";
  if (normalized.includes("nurse") || normalized.includes("doctor") || normalized.includes("health")) return "Healthcare";
  if (normalized.includes("engineer") || normalized.includes("software") || normalized.includes("developer") || normalized.includes("technician")) return "Technology";
  if (normalized.includes("bank") || normalized.includes("account") || normalized.includes("finance")) return "Finance";
  if (normalized.includes("driver") || normalized.includes("transport") || normalized.includes("delivery")) return "Transport";
  if (normalized.includes("civil") || normalized.includes("public") || normalized.includes("government")) return "Public Service";
  if (normalized.includes("manager") || normalized.includes("marketing") || normalized.includes("sales") || normalized.includes("real estate")) return "Business";
  if (normalized.includes("f&b") || normalized.includes("hawker") || normalized.includes("service")) return "Services";
  return "General";
}

function defaultDimensionForUseCase(useCase: string): DemographicDimension {
  if (useCase === "public-policy-testing" || useCase === "policy-review") return "industry";
  if (useCase === "campaign-content-testing" || useCase === "ad-testing") return "ageBucket";
  if (useCase === "product-market-research" || useCase === "pmf-discovery") return "occupation";
  return "industry";
}

function formatCountry(country: string): string {
  const normalized = String(country || "").trim().toLowerCase();
  if (normalized === "usa") return "USA";
  if (!normalized) return "Singapore";
  return normalized[0].toUpperCase() + normalized.slice(1);
}

function formatUseCase(useCase: string): string {
  const normalized = String(useCase || "").trim().toLowerCase();
  if (normalized === "public-policy-testing") return "Public Policy Testing";
  if (normalized === "product-market-research") return "Product & Market Research";
  if (normalized === "campaign-content-testing") return "Campaign & Content Testing";
  // V1 backward compat
  if (normalized === "policy-review") return "Public Policy Testing";
  if (normalized === "ad-testing") return "Campaign & Content Testing";
  if (normalized === "pmf-discovery" || normalized === "reviews") return "Product & Market Research";
  return "Public Policy Testing";
}
```

- V2 dimension mapping and `formatUseCase()` + backward compat

### Console API
```diff:console-api.ts
export type ConsoleMode = "demo" | "live";
export type ModelProviderId = "google" | "openrouter" | "openai" | "ollama";
export type V2ProviderId = "gemini" | "openai" | "ollama";

export interface ConsoleSessionModelConfigRequest {
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name?: string;
  api_key?: string;
  base_url?: string;
}

export interface ConsoleSessionModelConfigResponse {
  session_id: string;
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked?: string | null;
}

export interface ConsoleModelProvider {
  id: ModelProviderId;
  label: string;
  default_model: string;
  default_embed_model: string;
  default_base_url: string;
  requires_api_key: boolean;
}

export interface ConsoleModelProviderCatalogResponse {
  providers: ConsoleModelProvider[];
}

export interface ConsoleModelOption {
  id: string;
  label: string;
}

export interface ConsoleProviderModelsResponse {
  provider: ModelProviderId;
  models: ConsoleModelOption[];
}

export interface V2CountryResponse {
  name: string;
  code: string;
  flag_emoji: string;
  dataset_path: string;
  available: boolean;
}

export interface V2ProviderResponse {
  name: V2ProviderId;
  models: string[];
  requires_api_key: boolean;
}

export interface V2SessionCreateRequest {
  country: string;
  provider: V2ProviderId | ModelProviderId;
  model: string;
  api_key?: string;
  use_case: string;
  mode?: ConsoleMode;
  session_id?: string;
}

export interface V2SessionCreateResponse {
  session_id: string;
}

export interface ConsoleSessionResponse {
  session_id: string;
  mode: ConsoleMode;
  status: string;
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked?: string | null;
}

export interface KnowledgeNode {
  id: string;
  label: string;
  type: string;
  description?: string | null;
  summary?: string | null;
  weight?: number | null;
  families?: string[] | null;
  facet_kind?: string | null;
  canonical_key?: string | null;
  canonical_value?: string | null;
  display_bucket?: string | null;
  support_count?: number | null;
  degree_count?: number | null;
  importance_score?: number | null;
  source_ids?: string[] | null;
  file_paths?: string[] | null;
  generic_placeholder?: boolean | null;
  low_value_orphan?: boolean | null;
  ui_default_hidden?: boolean | null;
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  type: string;
  label?: string | null;
  summary?: string | null;
  normalized_type?: string | null;
  raw_relation_text?: string | null;
  source_ids?: string[] | null;
  file_paths?: string[] | null;
}

export interface KnowledgeArtifact {
  session_id: string;
  document: {
    document_id: string;
    source_path?: string | null;
    file_name?: string | null;
    file_type?: string | null;
    text_length?: number | null;
    paragraph_count?: number | null;
  };
  summary: string;
  guiding_prompt?: string | null;
  entity_nodes: KnowledgeNode[];
  relationship_edges: KnowledgeEdge[];
  entity_type_counts: Record<string, number>;
  processing_logs: string[];
  demographic_focus_summary?: string | null;
}

export interface ConsoleKnowledgeDocumentInput {
  document_text: string;
  source_path?: string | null;
}

export interface ConsoleKnowledgeProcessRequest {
  document_text?: string | null;
  source_path?: string | null;
  documents?: ConsoleKnowledgeDocumentInput[];
  guiding_prompt?: string | null;
  demographic_focus?: string | null;
  use_default_demo_document?: boolean;
}

export interface ConsoleScrapeResponse {
  url: string;
  title: string;
  text: string;
  length: number;
}

export interface ConsoleDynamicFilterFieldResponse {
  field: string;
  type: "range" | "multi-select-chips" | "single-select-chips" | "dropdown" | string;
  label: string;
  options: string[];
  min?: number | null;
  max?: number | null;
  default_min?: number | null;
  default_max?: number | null;
  default?: string | string[] | null;
}

export interface ConsoleDynamicFiltersResponse {
  session_id: string;
  country: string;
  use_case?: string | null;
  filters: ConsoleDynamicFilterFieldResponse[];
}

export interface TokenUsageEstimateResponse {
  with_caching_usd: number;
  without_caching_usd: number;
  savings_pct: number;
  model: string;
}

export interface TokenUsageRuntimeResponse {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  estimated_cost_usd: number;
  cost_without_caching_usd: number;
  caching_savings_usd: number;
  caching_savings_pct: number;
  model: string;
}

export interface ParsedSamplingInstructions {
  hard_filters: Record<string, string[]>;
  soft_boosts: Record<string, string[]>;
  soft_penalties?: Record<string, string[]>;
  exclusions: Record<string, string[]>;
  distribution_targets: Record<string, string[]>;
  notes_for_ui: string[];
  source?: string;
}

export interface PopulationSelectionReason {
  score: number;
  selection_score?: number;
  matched_facets: string[];
  matched_document_entities: string[];
  instruction_matches: string[];
  bm25_terms: string[];
  semantic_summary: string;
  semantic_relevance: number;
  bm25_relevance?: number;
  geographic_relevance: number;
  socioeconomic_relevance: number;
  digital_behavior_relevance: number;
  filter_alignment: number;
}

export interface SampledPersona {
  agent_id: string;
  display_name?: string;
  persona: Record<string, unknown>;
  selection_reason: PopulationSelectionReason;
}

export interface PopulationGraphNode {
  id: string;
  label: string;
  subtitle?: string;
  planning_area?: string;
  industry?: string;
  node_type?: string;
  score?: number;
  age?: number;
  sex?: string;
}

export interface PopulationGraphLink {
  source: string;
  target: string;
  weight?: number;
  reason?: string;
  reasons?: string[];
  label?: string;
}

export interface PopulationArtifact {
  session_id: string;
  candidate_count: number;
  sample_count: number;
  sample_mode: "affected_groups" | "population_baseline";
  sample_seed: number;
  parsed_sampling_instructions: ParsedSamplingInstructions;
  coverage: {
    planning_areas: string[];
    age_buckets: Record<string, number>;
    sex_distribution?: Record<string, number>;
  };
  sampled_personas: SampledPersona[];
  agent_graph: {
    nodes: PopulationGraphNode[];
    links: PopulationGraphLink[];
  };
  representativeness: {
    status: string;
    planning_area_distribution?: Record<string, number>;
    sex_distribution?: Record<string, number>;
  };
  selection_diagnostics: {
    candidate_count?: number;
    structured_filter_count?: number;
    shortlist_count?: number;
    bm25_shortlist_count?: number;
    semantic_rerank_count?: number;
  };
}

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export function isLiveBootMode(): boolean {
  return import.meta.env.VITE_BOOT_MODE === "live";
}

function getDefaultMode(): ConsoleMode {
  return isLiveBootMode() ? "live" : "demo";
}

export interface SimulationCounters {
  posts: number;
  comments: number;
  reactions: number;
  active_authors: number;
}

export interface SimulationCheckpointStatus {
  status: string;
  completed_agents: number;
  total_agents: number;
}

export interface SimulationState {
  session_id: string;
  status: string;
  event_count: number;
  last_round: number;
  platform?: string | null;
  planned_rounds?: number | null;
  current_round?: number | null;
  elapsed_seconds?: number | null;
  estimated_total_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  counters: SimulationCounters;
  checkpoint_status: Record<string, SimulationCheckpointStatus>;
  top_threads: Array<Record<string, unknown>>;
  discussion_momentum: Record<string, unknown>;
  latest_metrics: Record<string, unknown>;
  recent_events: Array<Record<string, unknown>>;
}

export interface StructuredReportState {
  session_id: string;
  status: string;
  generated_at?: string | null;
  executive_summary?: string | null;
  insight_cards: Array<Record<string, unknown>>;
  support_themes: Array<Record<string, unknown>>;
  dissent_themes: Array<Record<string, unknown>>;
  demographic_breakdown: Array<Record<string, unknown>>;
  influential_content: Array<Record<string, unknown>>;
  recommendations: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  error?: string | null;
}

export interface ConsoleChatResponseMessage {
  agent_id?: string;
  agent_name?: string;
  content: string;
}

export interface ConsoleGroupChatResponse {
  session_id: string;
  responses: ConsoleChatResponseMessage[];
}

export interface ConsoleAgentChatResponse {
  session_id: string;
  agent_id?: string;
  responses: ConsoleChatResponseMessage[];
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (body?.detail !== undefined) {
        detail = JSON.stringify(body.detail);
      } else if (typeof body?.message === "string") {
        detail = body.message;
      } else {
        detail = JSON.stringify(body);
      }
    } catch {
      const text = await response.text();
      if (text) {
        detail = text;
      }
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function normalizeProviderId(provider: string | null | undefined): ModelProviderId | V2ProviderId {
  const normalized = String(provider ?? "").trim().toLowerCase();
  if (normalized === "gemini") {
    return "google";
  }
  if (normalized === "google" || normalized === "openrouter" || normalized === "openai" || normalized === "ollama") {
    return normalized;
  }
  return normalized as ModelProviderId | V2ProviderId;
}

export function displayProviderId(provider: string | null | undefined): string {
  const normalized = String(provider ?? "").trim().toLowerCase();
  if (normalized === "google") {
    return "gemini";
  }
  return normalized;
}

export function normalizeUseCaseId(useCase: string | null | undefined): string {
  const normalized = String(useCase ?? "").trim().toLowerCase();
  if (normalized === "reviews") {
    return "customer-review";
  }
  if (normalized === "pmf-discovery") {
    return "product-market-fit";
  }
  return normalized;
}

export function displayUseCaseId(useCase: string | null | undefined): string {
  const normalized = String(useCase ?? "").trim().toLowerCase();
  if (normalized === "customer-review") {
    return "reviews";
  }
  if (normalized === "product-market-fit") {
    return "pmf-discovery";
  }
  return normalized;
}

export async function createConsoleSession(
  mode: ConsoleMode = getDefaultMode(),
  modelConfig: Partial<ConsoleSessionModelConfigRequest> = {},
): Promise<ConsoleSessionResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode,
      ...modelConfig,
      model_provider: modelConfig.model_provider ? normalizeProviderId(modelConfig.model_provider) : undefined,
    }),
  });
  return parseJson(response);
}

export async function getV2Countries(): Promise<V2CountryResponse[]> {
  const response = await fetch(`${API_BASE}/api/v2/countries`);
  return parseJson(response);
}

export async function getV2Providers(): Promise<V2ProviderResponse[]> {
  const response = await fetch(`${API_BASE}/api/v2/providers`);
  return parseJson(response);
}

export async function createV2Session(payload: V2SessionCreateRequest): Promise<V2SessionCreateResponse> {
  const response = await fetch(`${API_BASE}/api/v2/session/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      mode: payload.mode ?? getDefaultMode(),
      provider: normalizeProviderId(payload.provider),
      use_case: normalizeUseCaseId(payload.use_case),
    }),
  });
  return parseJson(response);
}

export async function getModelProviderCatalog(): Promise<ConsoleModelProviderCatalogResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/model/providers`);
  return parseJson(response);
}

export async function listProviderModels(
  provider: ModelProviderId,
  options: { api_key?: string; base_url?: string } = {},
): Promise<ConsoleProviderModelsResponse> {
  const params = new URLSearchParams();
  if (options.api_key) {
    params.set('api_key', options.api_key);
  }
  if (options.base_url) {
    params.set('base_url', options.base_url);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  const response = await fetch(`${API_BASE}/api/v2/console/model/providers/${provider}/models${suffix}`);
  return parseJson(response);
}

export async function getSessionModelConfig(sessionId: string): Promise<ConsoleSessionModelConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`);
  return parseJson(response);
}

export async function updateSessionModelConfig(
  sessionId: string,
  payload: ConsoleSessionModelConfigRequest,
): Promise<ConsoleSessionModelConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function uploadKnowledgeFile(
  sessionId: string,
  file: File,
  guidingPrompt?: string,
): Promise<KnowledgeArtifact> {
  const formData = new FormData();
  formData.append("file", file);
  if (guidingPrompt?.trim()) {
    formData.append("guiding_prompt", guidingPrompt.trim());
  }

  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/upload`, {
    method: "POST",
    body: formData,
  });
  return parseJson(response);
}

export async function processKnowledgeDocuments(
  sessionId: string,
  payload: ConsoleKnowledgeProcessRequest,
): Promise<KnowledgeArtifact> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function scrapeKnowledgeUrl(sessionId: string, url: string): Promise<ConsoleScrapeResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return parseJson(response);
}

export async function getDynamicFilters(sessionId: string): Promise<ConsoleDynamicFiltersResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/filters`);
  return parseJson(response);
}

export async function getTokenUsageEstimate(
  sessionId: string,
  agents: number,
  rounds: number,
): Promise<TokenUsageEstimateResponse> {
  const params = new URLSearchParams({
    agents: String(agents),
    rounds: String(rounds),
  });
  const response = await fetch(`${API_BASE}/api/v2/token-usage/${sessionId}/estimate?${params.toString()}`);
  return parseJson(response);
}

export async function getTokenUsageRuntime(sessionId: string): Promise<TokenUsageRuntimeResponse> {
  const response = await fetch(`${API_BASE}/api/v2/token-usage/${sessionId}`);
  return parseJson(response);
}

export async function previewPopulation(
  sessionId: string,
  payload: {
    agent_count: number;
    sample_mode: "affected_groups" | "population_baseline";
    sampling_instructions?: string;
    seed?: number;
    min_age?: number;
    max_age?: number;
    planning_areas?: string[];
    dynamic_filters?: Record<string, unknown>;
  },
): Promise<PopulationArtifact> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/sampling/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function startSimulation(
  sessionId: string,
  payload: {
    policy_summary: string;
    rounds: number;
    controversy_boost?: number;
    mode?: ConsoleMode;
  },
): Promise<SimulationState> {
  const simulateResponse = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rounds: payload.rounds,
      controversy_boost: payload.controversy_boost ?? 0,
      mode: payload.mode,
    }),
  });
  return parseJson(simulateResponse);
}

export async function getSimulationState(sessionId: string): Promise<SimulationState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/state`);
  return parseJson(response);
}

export async function getSimulationMetrics(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/metrics`);
  return parseJson(response);
}

export function buildSimulationStreamUrl(sessionId: string): string {
  return `${API_BASE}/api/v2/console/session/${sessionId}/simulation/stream`;
}

export async function generateReport(sessionId: string): Promise<StructuredReportState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/generate`, {
    method: "POST",
  });
  return parseJson(response);
}

export async function getStructuredReport(sessionId: string): Promise<StructuredReportState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report`);
  return parseJson(response);
}

export async function exportReportDocx(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/export`);
  await ensureResponseOk(response);
  return response.blob();
}

export async function sendGroupChatMessage(
  sessionId: string,
  payload: { segment: string; message: string },
): Promise<ConsoleGroupChatResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/chat/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (response.ok) {
    return normalizeGroupChatPayload(await response.json());
  }
  return normalizeGroupChatPayload(await parseJson<Record<string, unknown>>(response));
}

export async function sendAgentChatMessage(
  sessionId: string,
  payload: { agent_id: string; message: string },
): Promise<ConsoleAgentChatResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/chat/agent/${payload.agent_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: payload.message }),
  });

  if (response.ok) {
    return normalizeAgentChatPayload(payload.agent_id, await response.json());
  }
  return normalizeAgentChatPayload(payload.agent_id, await parseJson<Record<string, unknown>>(response));
}

export async function getAnalyticsPolarization(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/polarization`);
  return parseJson(response);
}

export async function getAnalyticsOpinionFlow(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/opinion-flow`);
  return parseJson(response);
}

export async function getAnalyticsInfluence(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/influence`);
  return parseJson(response);
}

export async function getAnalyticsCascades(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/cascades`);
  return parseJson(response);
}

async function ensureResponseOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (typeof body?.message === "string") {
      detail = body.message;
    } else {
      detail = JSON.stringify(body);
    }
  } catch {
    const text = await response.text();
    if (text) {
      detail = text;
    }
  }
  throw new Error(detail);
}

function normalizeGroupChatPayload(payload: Record<string, unknown>): ConsoleGroupChatResponse {
  return {
    session_id: String(payload.session_id ?? ""),
    responses: normalizeChatResponses(payload),
  };
}

function normalizeAgentChatPayload(
  fallbackAgentId: string,
  payload: Record<string, unknown>,
): ConsoleAgentChatResponse {
  const agentId = String(payload.agent_id ?? fallbackAgentId);
  const responses = normalizeChatResponses(payload);
  return {
    session_id: String(payload.session_id ?? ""),
    agent_id: agentId,
    responses:
      responses.length > 0
        ? responses.map((entry) => ({
            ...entry,
            agent_id: entry.agent_id ?? agentId,
          }))
        : [],
  };
}

function normalizeChatResponses(payload: Record<string, unknown>): ConsoleChatResponseMessage[] {
  const listCandidate = payload.responses ?? payload.messages;
  if (Array.isArray(listCandidate)) {
    return listCandidate
      .map((row) => normalizeChatResponseEntry(row))
      .filter((row): row is ConsoleChatResponseMessage => Boolean(row));
  }

  const single = normalizeChatResponseEntry(payload);
  if (single) {
    return [single];
  }
  return [];
}

function normalizeChatResponseEntry(value: unknown): ConsoleChatResponseMessage | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const row = value as Record<string, unknown>;
  const contentCandidate = row.content ?? row.response ?? row.message ?? row.text;
  const content = String(contentCandidate ?? "").trim();
  if (!content) {
    return null;
  }
  return {
    content,
    agent_id: row.agent_id ? String(row.agent_id) : row.id ? String(row.id) : undefined,
    agent_name: row.agent_name ? String(row.agent_name) : row.name ? String(row.name) : undefined,
  };
}
===
export type ConsoleMode = "demo" | "live";
export type ModelProviderId = "google" | "openrouter" | "openai" | "ollama";
export type V2ProviderId = "gemini" | "openai" | "ollama";

export interface ConsoleSessionModelConfigRequest {
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name?: string;
  api_key?: string;
  base_url?: string;
}

export interface ConsoleSessionModelConfigResponse {
  session_id: string;
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked?: string | null;
}

export interface ConsoleModelProvider {
  id: ModelProviderId;
  label: string;
  default_model: string;
  default_embed_model: string;
  default_base_url: string;
  requires_api_key: boolean;
}

export interface ConsoleModelProviderCatalogResponse {
  providers: ConsoleModelProvider[];
}

export interface ConsoleModelOption {
  id: string;
  label: string;
}

export interface ConsoleProviderModelsResponse {
  provider: ModelProviderId;
  models: ConsoleModelOption[];
}

export interface V2CountryResponse {
  name: string;
  code: string;
  flag_emoji: string;
  dataset_path: string;
  available: boolean;
}

export interface V2ProviderResponse {
  name: V2ProviderId;
  models: string[];
  requires_api_key: boolean;
}

export interface V2SessionCreateRequest {
  country: string;
  provider: V2ProviderId | ModelProviderId;
  model: string;
  api_key?: string;
  use_case: string;
  mode?: ConsoleMode;
  session_id?: string;
}

export interface V2SessionCreateResponse {
  session_id: string;
}

export interface ConsoleSessionResponse {
  session_id: string;
  mode: ConsoleMode;
  status: string;
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked?: string | null;
}

export interface KnowledgeNode {
  id: string;
  label: string;
  type: string;
  description?: string | null;
  summary?: string | null;
  weight?: number | null;
  families?: string[] | null;
  facet_kind?: string | null;
  canonical_key?: string | null;
  canonical_value?: string | null;
  display_bucket?: string | null;
  support_count?: number | null;
  degree_count?: number | null;
  importance_score?: number | null;
  source_ids?: string[] | null;
  file_paths?: string[] | null;
  generic_placeholder?: boolean | null;
  low_value_orphan?: boolean | null;
  ui_default_hidden?: boolean | null;
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  type: string;
  label?: string | null;
  summary?: string | null;
  normalized_type?: string | null;
  raw_relation_text?: string | null;
  source_ids?: string[] | null;
  file_paths?: string[] | null;
}

export interface KnowledgeArtifact {
  session_id: string;
  document: {
    document_id: string;
    source_path?: string | null;
    file_name?: string | null;
    file_type?: string | null;
    text_length?: number | null;
    paragraph_count?: number | null;
  };
  summary: string;
  guiding_prompt?: string | null;
  entity_nodes: KnowledgeNode[];
  relationship_edges: KnowledgeEdge[];
  entity_type_counts: Record<string, number>;
  processing_logs: string[];
  demographic_focus_summary?: string | null;
}

export interface ConsoleKnowledgeDocumentInput {
  document_text: string;
  source_path?: string | null;
}

export interface ConsoleKnowledgeProcessRequest {
  document_text?: string | null;
  source_path?: string | null;
  documents?: ConsoleKnowledgeDocumentInput[];
  guiding_prompt?: string | null;
  demographic_focus?: string | null;
  use_default_demo_document?: boolean;
}

export interface ConsoleScrapeResponse {
  url: string;
  title: string;
  text: string;
  length: number;
}

export interface ConsoleDynamicFilterFieldResponse {
  field: string;
  type: "range" | "multi-select-chips" | "single-select-chips" | "dropdown" | string;
  label: string;
  options: string[];
  min?: number | null;
  max?: number | null;
  default_min?: number | null;
  default_max?: number | null;
  default?: string | string[] | null;
}

export interface ConsoleDynamicFiltersResponse {
  session_id: string;
  country: string;
  use_case?: string | null;
  filters: ConsoleDynamicFilterFieldResponse[];
}

export interface TokenUsageEstimateResponse {
  with_caching_usd: number;
  without_caching_usd: number;
  savings_pct: number;
  model: string;
}

export interface TokenUsageRuntimeResponse {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  estimated_cost_usd: number;
  cost_without_caching_usd: number;
  caching_savings_usd: number;
  caching_savings_pct: number;
  model: string;
}

export interface ParsedSamplingInstructions {
  hard_filters: Record<string, string[]>;
  soft_boosts: Record<string, string[]>;
  soft_penalties?: Record<string, string[]>;
  exclusions: Record<string, string[]>;
  distribution_targets: Record<string, string[]>;
  notes_for_ui: string[];
  source?: string;
}

export interface PopulationSelectionReason {
  score: number;
  selection_score?: number;
  matched_facets: string[];
  matched_document_entities: string[];
  instruction_matches: string[];
  bm25_terms: string[];
  semantic_summary: string;
  semantic_relevance: number;
  bm25_relevance?: number;
  geographic_relevance: number;
  socioeconomic_relevance: number;
  digital_behavior_relevance: number;
  filter_alignment: number;
}

export interface SampledPersona {
  agent_id: string;
  display_name?: string;
  persona: Record<string, unknown>;
  selection_reason: PopulationSelectionReason;
}

export interface PopulationGraphNode {
  id: string;
  label: string;
  subtitle?: string;
  planning_area?: string;
  industry?: string;
  node_type?: string;
  score?: number;
  age?: number;
  sex?: string;
}

export interface PopulationGraphLink {
  source: string;
  target: string;
  weight?: number;
  reason?: string;
  reasons?: string[];
  label?: string;
}

export interface PopulationArtifact {
  session_id: string;
  candidate_count: number;
  sample_count: number;
  sample_mode: "affected_groups" | "population_baseline";
  sample_seed: number;
  parsed_sampling_instructions: ParsedSamplingInstructions;
  coverage: {
    planning_areas: string[];
    age_buckets: Record<string, number>;
    sex_distribution?: Record<string, number>;
  };
  sampled_personas: SampledPersona[];
  agent_graph: {
    nodes: PopulationGraphNode[];
    links: PopulationGraphLink[];
  };
  representativeness: {
    status: string;
    planning_area_distribution?: Record<string, number>;
    sex_distribution?: Record<string, number>;
  };
  selection_diagnostics: {
    candidate_count?: number;
    structured_filter_count?: number;
    shortlist_count?: number;
    bm25_shortlist_count?: number;
    semantic_rerank_count?: number;
  };
}

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export function isLiveBootMode(): boolean {
  return import.meta.env.VITE_BOOT_MODE === "live";
}

function getDefaultMode(): ConsoleMode {
  return isLiveBootMode() ? "live" : "demo";
}

export interface SimulationCounters {
  posts: number;
  comments: number;
  reactions: number;
  active_authors: number;
}

export interface SimulationCheckpointStatus {
  status: string;
  completed_agents: number;
  total_agents: number;
}

export interface SimulationState {
  session_id: string;
  status: string;
  event_count: number;
  last_round: number;
  platform?: string | null;
  planned_rounds?: number | null;
  current_round?: number | null;
  elapsed_seconds?: number | null;
  estimated_total_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  counters: SimulationCounters;
  checkpoint_status: Record<string, SimulationCheckpointStatus>;
  top_threads: Array<Record<string, unknown>>;
  discussion_momentum: Record<string, unknown>;
  latest_metrics: Record<string, unknown>;
  recent_events: Array<Record<string, unknown>>;
}

export interface StructuredReportState {
  session_id: string;
  status: string;
  generated_at?: string | null;
  executive_summary?: string | null;
  insight_cards: Array<Record<string, unknown>>;
  support_themes: Array<Record<string, unknown>>;
  dissent_themes: Array<Record<string, unknown>>;
  demographic_breakdown: Array<Record<string, unknown>>;
  influential_content: Array<Record<string, unknown>>;
  recommendations: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  error?: string | null;
}

export interface ConsoleChatResponseMessage {
  agent_id?: string;
  agent_name?: string;
  content: string;
}

export interface ConsoleGroupChatResponse {
  session_id: string;
  responses: ConsoleChatResponseMessage[];
}

export interface ConsoleAgentChatResponse {
  session_id: string;
  agent_id?: string;
  responses: ConsoleChatResponseMessage[];
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (body?.detail !== undefined) {
        detail = JSON.stringify(body.detail);
      } else if (typeof body?.message === "string") {
        detail = body.message;
      } else {
        detail = JSON.stringify(body);
      }
    } catch {
      const text = await response.text();
      if (text) {
        detail = text;
      }
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function normalizeProviderId(provider: string | null | undefined): ModelProviderId | V2ProviderId {
  const normalized = String(provider ?? "").trim().toLowerCase();
  if (normalized === "gemini") {
    return "google";
  }
  if (normalized === "google" || normalized === "openrouter" || normalized === "openai" || normalized === "ollama") {
    return normalized;
  }
  return normalized as ModelProviderId | V2ProviderId;
}

export function displayProviderId(provider: string | null | undefined): string {
  const normalized = String(provider ?? "").trim().toLowerCase();
  if (normalized === "google") {
    return "gemini";
  }
  return normalized;
}

export function normalizeUseCaseId(useCase: string | null | undefined): string {
  const normalized = String(useCase ?? "").trim().toLowerCase();
  // V2 canonical names — pass through
  if (normalized === "public-policy-testing" || normalized === "product-market-research" || normalized === "campaign-content-testing") {
    return normalized;
  }
  // V1 backward compat
  if (normalized === "policy-review") return "public-policy-testing";
  if (normalized === "reviews" || normalized === "customer-review") return "product-market-research";
  if (normalized === "pmf-discovery" || normalized === "product-market-fit") return "product-market-research";
  if (normalized === "ad-testing") return "campaign-content-testing";
  return normalized;
}

export function displayUseCaseId(useCase: string | null | undefined): string {
  const normalized = String(useCase ?? "").trim().toLowerCase();
  // V2 canonical names — pass through as-is for display
  if (normalized === "public-policy-testing" || normalized === "product-market-research" || normalized === "campaign-content-testing") {
    return normalized;
  }
  // V1 backward compat
  if (normalized === "policy-review") return "public-policy-testing";
  if (normalized === "customer-review" || normalized === "reviews") return "product-market-research";
  if (normalized === "product-market-fit" || normalized === "pmf-discovery") return "product-market-research";
  if (normalized === "ad-testing") return "campaign-content-testing";
  return normalized;
}

export async function createConsoleSession(
  mode: ConsoleMode = getDefaultMode(),
  modelConfig: Partial<ConsoleSessionModelConfigRequest> = {},
): Promise<ConsoleSessionResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode,
      ...modelConfig,
      model_provider: modelConfig.model_provider ? normalizeProviderId(modelConfig.model_provider) : undefined,
    }),
  });
  return parseJson(response);
}

export async function getV2Countries(): Promise<V2CountryResponse[]> {
  const response = await fetch(`${API_BASE}/api/v2/countries`);
  return parseJson(response);
}

export async function getV2Providers(): Promise<V2ProviderResponse[]> {
  const response = await fetch(`${API_BASE}/api/v2/providers`);
  return parseJson(response);
}

export async function createV2Session(payload: V2SessionCreateRequest): Promise<V2SessionCreateResponse> {
  const response = await fetch(`${API_BASE}/api/v2/session/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      mode: payload.mode ?? getDefaultMode(),
      provider: normalizeProviderId(payload.provider),
      use_case: normalizeUseCaseId(payload.use_case),
    }),
  });
  return parseJson(response);
}

export async function getModelProviderCatalog(): Promise<ConsoleModelProviderCatalogResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/model/providers`);
  return parseJson(response);
}

export async function listProviderModels(
  provider: ModelProviderId,
  options: { api_key?: string; base_url?: string } = {},
): Promise<ConsoleProviderModelsResponse> {
  const params = new URLSearchParams();
  if (options.api_key) {
    params.set('api_key', options.api_key);
  }
  if (options.base_url) {
    params.set('base_url', options.base_url);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  const response = await fetch(`${API_BASE}/api/v2/console/model/providers/${provider}/models${suffix}`);
  return parseJson(response);
}

export async function getSessionModelConfig(sessionId: string): Promise<ConsoleSessionModelConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`);
  return parseJson(response);
}

export async function updateSessionModelConfig(
  sessionId: string,
  payload: ConsoleSessionModelConfigRequest,
): Promise<ConsoleSessionModelConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function uploadKnowledgeFile(
  sessionId: string,
  file: File,
  guidingPrompt?: string,
): Promise<KnowledgeArtifact> {
  const formData = new FormData();
  formData.append("file", file);
  if (guidingPrompt?.trim()) {
    formData.append("guiding_prompt", guidingPrompt.trim());
  }

  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/upload`, {
    method: "POST",
    body: formData,
  });
  return parseJson(response);
}

export async function processKnowledgeDocuments(
  sessionId: string,
  payload: ConsoleKnowledgeProcessRequest,
): Promise<KnowledgeArtifact> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function scrapeKnowledgeUrl(sessionId: string, url: string): Promise<ConsoleScrapeResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return parseJson(response);
}

export async function getDynamicFilters(sessionId: string): Promise<ConsoleDynamicFiltersResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/filters`);
  return parseJson(response);
}

export async function getTokenUsageEstimate(
  sessionId: string,
  agents: number,
  rounds: number,
): Promise<TokenUsageEstimateResponse> {
  const params = new URLSearchParams({
    agents: String(agents),
    rounds: String(rounds),
  });
  const response = await fetch(`${API_BASE}/api/v2/token-usage/${sessionId}/estimate?${params.toString()}`);
  return parseJson(response);
}

export async function getTokenUsageRuntime(sessionId: string): Promise<TokenUsageRuntimeResponse> {
  const response = await fetch(`${API_BASE}/api/v2/token-usage/${sessionId}`);
  return parseJson(response);
}

export async function previewPopulation(
  sessionId: string,
  payload: {
    agent_count: number;
    sample_mode: "affected_groups" | "population_baseline";
    sampling_instructions?: string;
    seed?: number;
    min_age?: number;
    max_age?: number;
    planning_areas?: string[];
    dynamic_filters?: Record<string, unknown>;
  },
): Promise<PopulationArtifact> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/sampling/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function startSimulation(
  sessionId: string,
  payload: {
    policy_summary: string;
    rounds: number;
    controversy_boost?: number;
    mode?: ConsoleMode;
  },
): Promise<SimulationState> {
  const simulateResponse = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rounds: payload.rounds,
      controversy_boost: payload.controversy_boost ?? 0,
      mode: payload.mode,
    }),
  });
  return parseJson(simulateResponse);
}

export async function getSimulationState(sessionId: string): Promise<SimulationState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/state`);
  return parseJson(response);
}

export async function getSimulationMetrics(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/metrics`);
  return parseJson(response);
}

export function buildSimulationStreamUrl(sessionId: string): string {
  return `${API_BASE}/api/v2/console/session/${sessionId}/simulation/stream`;
}

export async function generateReport(sessionId: string): Promise<StructuredReportState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/generate`, {
    method: "POST",
  });
  return parseJson(response);
}

export async function getStructuredReport(sessionId: string): Promise<StructuredReportState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report`);
  return parseJson(response);
}

export async function exportReportDocx(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/export`);
  await ensureResponseOk(response);
  return response.blob();
}

export async function generateQuestionMetadata(
  question: string,
  useCase?: string,
): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/questions/generate-metadata`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, use_case: useCase }),
  });
  return parseJson(response);
}

export async function getAnalysisQuestions(
  sessionId: string,
): Promise<{ session_id: string; use_case: string; questions: Array<Record<string, unknown>> }> {
  const response = await fetch(`${API_BASE}/api/v2/session/${sessionId}/analysis-questions`);
  return parseJson(response);
}

export async function sendGroupChatMessage(
  sessionId: string,
  payload: { segment: string; message: string },
): Promise<ConsoleGroupChatResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/chat/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (response.ok) {
    return normalizeGroupChatPayload(await response.json());
  }
  return normalizeGroupChatPayload(await parseJson<Record<string, unknown>>(response));
}

export async function sendAgentChatMessage(
  sessionId: string,
  payload: { agent_id: string; message: string },
): Promise<ConsoleAgentChatResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/chat/agent/${payload.agent_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: payload.message }),
  });

  if (response.ok) {
    return normalizeAgentChatPayload(payload.agent_id, await response.json());
  }
  return normalizeAgentChatPayload(payload.agent_id, await parseJson<Record<string, unknown>>(response));
}

export async function getAnalyticsPolarization(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/polarization`);
  return parseJson(response);
}

export async function getAnalyticsOpinionFlow(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/opinion-flow`);
  return parseJson(response);
}

export async function getAnalyticsInfluence(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/influence`);
  return parseJson(response);
}

export async function getAnalyticsCascades(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/cascades`);
  return parseJson(response);
}

async function ensureResponseOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (typeof body?.message === "string") {
      detail = body.message;
    } else {
      detail = JSON.stringify(body);
    }
  } catch {
    const text = await response.text();
    if (text) {
      detail = text;
    }
  }
  throw new Error(detail);
}

function normalizeGroupChatPayload(payload: Record<string, unknown>): ConsoleGroupChatResponse {
  return {
    session_id: String(payload.session_id ?? ""),
    responses: normalizeChatResponses(payload),
  };
}

function normalizeAgentChatPayload(
  fallbackAgentId: string,
  payload: Record<string, unknown>,
): ConsoleAgentChatResponse {
  const agentId = String(payload.agent_id ?? fallbackAgentId);
  const responses = normalizeChatResponses(payload);
  return {
    session_id: String(payload.session_id ?? ""),
    agent_id: agentId,
    responses:
      responses.length > 0
        ? responses.map((entry) => ({
            ...entry,
            agent_id: entry.agent_id ?? agentId,
          }))
        : [],
  };
}

function normalizeChatResponses(payload: Record<string, unknown>): ConsoleChatResponseMessage[] {
  const listCandidate = payload.responses ?? payload.messages;
  if (Array.isArray(listCandidate)) {
    return listCandidate
      .map((row) => normalizeChatResponseEntry(row))
      .filter((row): row is ConsoleChatResponseMessage => Boolean(row));
  }

  const single = normalizeChatResponseEntry(payload);
  if (single) {
    return [single];
  }
  return [];
}

function normalizeChatResponseEntry(value: unknown): ConsoleChatResponseMessage | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const row = value as Record<string, unknown>;
  const contentCandidate = row.content ?? row.response ?? row.message ?? row.text;
  const content = String(contentCandidate ?? "").trim();
  if (!content) {
    return null;
  }
  return {
    content,
    agent_id: row.agent_id ? String(row.agent_id) : row.id ? String(row.id) : undefined,
    agent_name: row.agent_name ? String(row.agent_name) : row.name ? String(row.name) : undefined,
  };
}
```

- `normalizeUseCaseId()` / `displayUseCaseId()` — V1→V2 mapping
- `generateQuestionMetadata()` — POST to metadata endpoint
- `getAnalysisQuestions()` — GET session questions

---

## 4. Documentation Updates

| Document | Changes |
|----------|---------|
| [BRD_V2.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/BRD_V2.md) | Use cases, config structure, analysis_questions schema, YAML examples |
| [screen-0-onboarding.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/frontend/screen-0-onboarding.md) | 3 use case pills with emojis |
| [screen-1-knowledge-graph.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/frontend/screen-1-knowledge-graph.md) | Analysis Questions card list replacing Guiding Prompt |
| [screen-4-report-chat.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/frontend/screen-4-report-chat.md) | Metric deltas, analysis sections, insight blocks, preset sections, legacy fallback |
| [config-system.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/backend/config-system.md) | V2 YAML schema, ConfigService methods, USE_CASE_MAP, 3 full config examples |
| [metrics-heuristics.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/backend/metrics-heuristics.md) | V2 per-use-case metric definitions |

---

## 5. Lint Notes

All `Cannot find module '@/...'` lint errors are **pre-existing** path alias resolution issues in the IDE. They do not affect the Vite build or runtime. The single `Leader` type mismatch in Analytics.tsx is also pre-existing and unrelated to these changes.
