from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class RunnerInput:
    simulation_id: str
    subject_summary: str
    rounds: int
    personas: list[dict[str, Any]]
    model_name: str
    api_key: str
    base_url: str
    oasis_db_path: str
    controversy_boost: float = 0.0
    events_path: str | None = None
    elapsed_offset_seconds: int = 0
    tail_checkpoint_estimate_seconds: int = 0
    oasis_semaphore: int = 128
    seed_discussion_threads: list[str] | None = None
    country: str = "the country"


@dataclass(frozen=True)
class SeedPostSpec:
    title: str
    content: str


NAME_FIELD_PATTERN = re.compile(r"(?:^|\b)(?:name|full name|persona)\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})")
NAME_WITH_VERB_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:grew|works|is|was|lives|resides|studies|believes|prefers)\b"
)
CAPITALIZED_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
TITLE_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")
WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-/]*")
TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}
QUESTION_STOPWORDS = TITLE_STOPWORDS | {
    "about",
    "could",
    "does",
    "fellow",
    "from",
    "have",
    "into",
    "most",
    "other",
    "should",
    "their",
    "them",
    "these",
    "those",
    "what",
    "which",
    "would",
}

AI_REFUSAL_PATTERNS = [
    re.compile(r"\b(as an? ai|as a language model)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+cannot|i\s+can\'?t)\b[^.]{0,120}\b(opinion|approve|disapprove|rate|personal)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+do\s+not\s+have\s+personal\s+opinions?)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+am\s+unable\s+to)\b[^.]{0,120}\b(rate|judge|approve|disapprove)\b", re.IGNORECASE),
]

VOICE_STYLE_CUES = [
    "Use short, direct sentences and one practical example.",
    "Use a conversational tone with one concrete household detail.",
    "Use balanced reasoning and mention one trade-off clearly.",
    "Use plain language and include one neighborhood-level impact.",
    "Use concise bullet-like phrasing in sentence form.",
    "Use thoughtful tone and compare today versus earlier conditions.",
]


def _build_username(name: str, idx: int) -> str:
    tokens = re.findall(r"[a-z0-9]+", str(name or "").lower())
    stem = "_".join(tokens[:3]).strip("_")
    if not stem:
        stem = "resident"
    return f"{stem}_{idx + 1}"


def _normalize_country_label(country: str | None) -> str:
    label = str(country or "").strip()
    return label or "the country"


def _to_profile(persona: dict[str, Any], idx: int, country: str = "the country") -> dict[str, Any]:
    country_label = _normalize_country_label(country)
    age = int(persona.get("age") or random.randint(21, 70))
    name = _extract_persona_display_name(persona, idx)
    username = _build_username(name, idx)
    planning_area = str(persona.get("planning_area") or country_label)
    occupation = str(persona.get("occupation") or "Resident")
    industry = str(persona.get("industry") or "")
    household_type = str(persona.get("household_type") or "").strip()
    income_bracket = str(persona.get("income_bracket") or "").strip()
    education = str(persona.get("highest_education") or "").strip()
    agent_id = str(persona.get("agent_id") or f"agent-{idx + 1:04d}")
    relevance = float(persona.get("mckainsey_relevance_score") or 0.0)
    matched_nodes = [
        str(value).strip()
        for value in (persona.get("mckainsey_matched_context_nodes") or [])
        if str(value).strip()
    ]
    dossier = str(persona.get("mckainsey_context") or "").strip()
    subtitle_parts = [part for part in [planning_area, occupation] if part and part.lower() != "unknown"]
    subtitle = " · ".join(subtitle_parts) or "Sampled persona"
    persona_text = (
        f"{age}-year-old {occupation} in {planning_area}."
    )
    if industry:
        persona_text += f" Industry context: {industry}."
    if household_type:
        persona_text += f" Household context: {household_type}."
    if income_bracket:
        persona_text += f" Income context: {income_bracket}."
    if education:
        persona_text += f" Education background: {education}."
    if dossier:
        persona_text += f" Subject dossier: {dossier}"
    if matched_nodes:
        persona_text += f" Relevant knowledge graph nodes: {', '.join(matched_nodes[:6])}."
    if relevance >= 0.75:
        persona_text += " This issue is directly relevant to you, so you should feel motivated to post or reply early."
    elif relevance >= 0.45:
        persona_text += " This issue is moderately relevant to you, so you should engage when the discussion touches your situation."
    else:
        persona_text += f" You may not be directly affected, but you should still react when community discussion surfaces broader {country_label}-wide implications."
    style_cue = VOICE_STYLE_CUES[idx % len(VOICE_STYLE_CUES)]
    persona_text += f" Writing cue: {style_cue}"
    persona_text += " Never claim to be an AI. Never reuse another user's wording verbatim."
    return {
        "user_id": idx,
        "agent_id": agent_id,
        "username": username,
        "realname": name,
        "user_name": username,
        "name": name,
        "display_name": name,
        "subtitle": subtitle,
        "occupation": occupation,
        "bio": persona_text,
        "persona": persona_text,
        "age": age,
        "gender": str(persona.get("sex") or persona.get("gender") or "unknown"),
        "mbti": str(persona.get("mbti") or "ISFJ"),
        "country": country_label,
        "karma": int(persona.get("karma") or random.randint(20, 5000)),
        "created_at": "2024-01-01",
    }


def _approval(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return len([s for s in scores if s >= 7.0]) / len(scores)


def _seed_opinion(persona: dict[str, Any]) -> float:
    base = 5.5
    age = persona.get("age")
    if isinstance(age, (int, float)):
        if age >= 60:
            base -= 0.8
        elif age <= 30:
            base += 0.4

    income = str(persona.get("income_bracket", "")).lower()
    if "$1,000" in income or "$2,000" in income or "$3,000" in income:
        base -= 0.5
    if "$10,000" in income or "$12,000" in income:
        base += 0.6

    return max(1.0, min(10.0, base + random.uniform(-1.0, 1.0)))


def _extract_title(content: str) -> str:
    text = " ".join(str(content or "").split()).strip()
    if not text:
        return "New discussion thread"

    normalized = re.sub(r"^As an? [^,]{1,80},\s*", "", text, flags=re.IGNORECASE)
    normalized = re.sub(
        r"^(?:I\s+(?:think|feel|believe|support|oppose|worry|suspect)|I'm\s+concerned|I\s+am\s+concerned)\b[:,]?\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    contrast_split = re.split(r"\b(?:but|however|though|although)\b", normalized, maxsplit=1, flags=re.IGNORECASE)
    primary_clause = contrast_split[0].strip(" ,.;:") if contrast_split else normalized
    segments = [
        segment.strip(" .,!?:;\"")
        for segment in re.split(r"[.!?]\s+|,\s+", primary_clause or normalized)
        if segment.strip()
    ]
    candidate = next((segment for segment in segments if len(segment.split()) >= 4), primary_clause or normalized)
    tokens = TITLE_TOKEN_PATTERN.findall(candidate)
    informative = [token for token in tokens if token.lower() not in TITLE_STOPWORDS]
    chosen = informative if len(informative) >= 4 else tokens
    if not chosen:
        return normalized[:84]

    title = " ".join(chosen[:10]).strip(" .,!?:;")
    if not title:
        return normalized[:84]
    return title[:1].upper() + title[1:84]


def _normalize_seed_question(question_text: str) -> str:
    return " ".join(str(question_text or "").split()).strip()


def _limit_words(text: str, max_words: int = 100) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return " ".join(words).strip()
    return " ".join(words[:max_words]).rstrip(" ,.;:") + "…"


def _split_subject_sentences(text: str) -> list[str]:
    cleaned = _sanitize_subject_context(text)
    if not cleaned:
        return []
    sentences = [
        re.sub(r"\s+", " ", segment).strip(" ,;:-")
        for segment in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if re.sub(r"\s+", " ", segment).strip(" ,;:-")
    ]
    return sentences


def _question_keywords(question_text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_TOKEN_PATTERN.findall(_normalize_seed_question(question_text).lower())
        if len(token) >= 4 and token.lower() not in QUESTION_STOPWORDS
    }


def _ensure_sentence(text: str) -> str:
    cleaned = _sanitize_subject_context(text)
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _build_seed_title(question_text: str, country: str = "the country") -> str:
    country_label = _normalize_country_label(country)
    question = _normalize_seed_question(question_text)
    if question:
        return f"{question} (Seeded post)"
    return f"{country_label} topic impacts (Seeded post)"


def _select_relevant_subject_sentences(subject_summary: str, question_text: str, limit: int = 2) -> list[str]:
    sentences = _split_subject_sentences(subject_summary)
    if not sentences:
        return []
    keywords = _question_keywords(question_text)

    def score(sentence: str) -> tuple[int, int, int]:
        sentence_tokens = {token.lower() for token in WORD_TOKEN_PATTERN.findall(sentence)}
        overlap = len(sentence_tokens & keywords)
        return (overlap, -abs(len(sentence_tokens) - 16), -len(sentence))

    ranked = sorted(sentences, key=score, reverse=True)
    selected: list[str] = []
    for sentence in ranked:
        normalized = _ensure_sentence(sentence)
        if normalized and normalized not in selected:
            selected.append(normalized)
        if len(selected) >= limit:
            break
    return selected


def _seed_perspective_sentence(profile: dict[str, Any] | None, country: str = "the country") -> str:
    country_label = _normalize_country_label(country)
    profile = profile or {}
    occupation = str(profile.get("occupation") or "resident").strip()
    planning_area = str(profile.get("planning_area") or profile.get("planningArea") or country_label).strip()
    if occupation and planning_area:
        return f"As a {occupation.lower()} in {planning_area}, the everyday impact is what matters most to me."
    if occupation:
        return f"As a {occupation.lower()}, the everyday impact is what matters most to me."
    return f"As a resident in {country_label}, the everyday impact is what matters most to me."


def _build_seed_post_content(
    subject_summary: str,
    index: int,
    country: str = "the country",
    profile: dict[str, Any] | None = None,
) -> str:
    del index
    country_label = _normalize_country_label(country)
    subject_sentences = _select_relevant_subject_sentences(subject_summary, "", limit=2)
    parts = [_seed_perspective_sentence(profile, country_label)]
    if subject_sentences:
        parts.extend(subject_sentences)
    else:
        parts.append(f"I want to discuss how this could affect different {country_label} households in practice.")
    parts.append("I want to hear how other residents think this would play out in daily life.")
    return _limit_words(" ".join(part for part in parts if part), max_words=100)


def _build_analysis_seed_post_content(
    subject_summary: str,
    question_text: str,
    index: int,
    profile: dict[str, Any] | None = None,
    country: str = "the country",
) -> str:
    del index
    country_label = _normalize_country_label(country)
    subject_sentences = _select_relevant_subject_sentences(subject_summary, question_text, limit=2)
    parts = [_seed_perspective_sentence(profile, country_label)]
    if subject_sentences:
        parts.extend(subject_sentences)
    else:
        parts.append("I want to focus on the parts that would change costs, access, and everyday routines.")
    parts.append("I want to hear how fellow citizens think this would affect daily life in practice.")
    return _limit_words(" ".join(part for part in parts if part), max_words=100)


def _sanitize_subject_context(text: str) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""

    filtered = cleaned
    for pattern in AI_REFUSAL_PATTERNS:
        filtered = pattern.sub("", filtered)

    filtered = re.sub(r"\b(analysis question\s*\d*\s*:)\b", "", filtered, flags=re.IGNORECASE)
    filtered = re.sub(r"\s{2,}", " ", filtered).strip(" .;:-")
    if not filtered:
        return ""
    return filtered


def _resolve_seed_posts(
    subject_summary: str,
    seed_discussion_threads: list[str] | None,
    country: str = "the country",
    seed_profiles: list[dict[str, Any]] | None = None,
) -> list[SeedPostSpec]:
    seed_posts: list[SeedPostSpec] = []
    for index, question_text in enumerate(seed_discussion_threads or []):
        question = str(question_text or "").strip()
        if not question:
            continue
        profile = (seed_profiles or [{}])[index % max(1, len(seed_profiles or [{}]))]
        seed_posts.append(
            SeedPostSpec(
                title=_build_seed_title(question, country),
                content=_build_analysis_seed_post_content(subject_summary, question, index, profile=profile, country=country),
            )
        )
    if seed_posts:
        return seed_posts
    return [
        SeedPostSpec(
            title=_build_seed_title("", country),
            content=_build_seed_post_content(subject_summary, 0, country, profile=(seed_profiles or [{}])[0]),
        )
    ]


def _determine_batch_size(active_agent_count: int, round_no: int) -> int:
    if round_no <= 1:
        return 1
    return max(1, min(25, int(active_agent_count * 0.10) or 1))


def _extract_persona_display_name(persona: dict[str, Any], idx: int) -> str:
    direct_keys = ("display_name", "name", "full_name", "realname", "user_name")
    for key in direct_keys:
        value = str(persona.get(key) or "").strip()
        if _is_valid_display_name(value):
            return value

    text_fields = (
        str(persona.get("persona") or ""),
        str(persona.get("professional_persona") or ""),
        str(persona.get("mckainsey_context") or ""),
    )
    for text in text_fields:
        if not text:
            continue
        explicit = NAME_FIELD_PATTERN.search(text)
        if explicit:
            value = explicit.group(1).strip()
            if _is_valid_display_name(value):
                return value

        contextual = NAME_WITH_VERB_PATTERN.search(text)
        if contextual:
            value = contextual.group(1).strip()
            if _is_valid_display_name(value):
                return value

        for implicit in CAPITALIZED_NAME_PATTERN.findall(text[:260]):
            value = implicit.strip()
            if _is_valid_display_name(value):
                return value

    return f"Resident {idx + 1}"


def _is_valid_display_name(value: str) -> bool:
    if not value:
        return False
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) < 3 or len(cleaned) > 40:
        return False
    lowered = cleaned.lower()
    blocked_tokens = {
        "sg",
        "agent",
        "resident",
        "user",
        "unknown",
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
    if "year old" in lowered or "persona" in lowered or "singapore" in lowered:
        return False
    words = set(lowered.split())
    if words & blocked_tokens:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){1,2}", cleaned))


def _build_activity_profile(persona: dict[str, Any], user_id: int) -> dict[str, Any]:
    age = int(persona.get("age") or 35)
    occupation = str(persona.get("occupation") or "").lower()
    relevance = float(persona.get("mckainsey_relevance_score") or 0.5)

    active_hours = list(range(8, 23))
    if age >= 60 or "retired" in occupation:
        active_hours = list(range(7, 21))
    elif "student" in occupation:
        active_hours = list(range(9, 24))
    elif any(token in occupation for token in ("nurse", "service", "driver", "shift", "security")):
        active_hours = list(range(0, 24))

    activity_level = max(0.25, min(0.95, 0.35 + (relevance * 0.55)))
    if any(token in occupation for token in ("manager", "executive", "consultant")):
        activity_level = min(0.97, activity_level + 0.05)

    return {
        "agent_id": user_id,
        "active_hours": active_hours,
        "activity_level": activity_level,
    }


def _simulated_hour_for_round(round_index: int) -> int:
    start_hour = 8
    minutes_per_round = 30
    simulated_minutes = round_index * minutes_per_round
    return (start_hour + (simulated_minutes // 60)) % 24


def _get_active_agents_for_round(
    env,
    *,
    activity_profiles: dict[int, dict[str, Any]],
    current_hour: int,
    round_no: int,
) -> list[tuple[int, Any]]:
    total_agents = max(1, len(activity_profiles))
    base_min = max(1, int(total_agents * 0.12))
    base_max = max(base_min, int(total_agents * 0.42))

    peak_hours = {9, 10, 11, 14, 15, 20, 21, 22}
    off_peak_hours = {0, 1, 2, 3, 4, 5}
    if current_hour in peak_hours:
        multiplier = 1.4
    elif current_hour in off_peak_hours:
        multiplier = 0.45
    else:
        multiplier = 1.0
    if round_no == 1:
        multiplier = max(multiplier, 1.25)

    target_count = max(1, int(random.uniform(base_min, base_max) * multiplier))

    candidates: list[int] = []
    active_hour_pool: list[int] = []
    for agent_id, profile in activity_profiles.items():
        hours = {int(value) for value in (profile.get("active_hours") or list(range(8, 23)))}
        if current_hour not in hours:
            continue
        active_hour_pool.append(agent_id)
        if random.random() < float(profile.get("activity_level", 0.5)):
            candidates.append(agent_id)

    selection_pool = candidates or active_hour_pool or list(activity_profiles.keys())
    if not selection_pool:
        return []

    selected_count = min(target_count, len(selection_pool))
    if round_no == 1:
        selected_count = max(selected_count, min(len(selection_pool), max(1, int(total_agents * 0.7))))
    selected_ids = random.sample(selection_pool, selected_count)

    active_agents: list[tuple[int, Any]] = []
    for agent_id in selected_ids:
        try:
            agent = env.agent_graph.get_agent(agent_id)
            active_agents.append((agent_id, agent))
        except Exception:
            continue

    if not active_agents:
        fallback_agents = [agent for _, agent in env.agent_graph.get_agents()]
        if fallback_agents:
            active_agents.append((-1, random.choice(fallback_agents)))

    return active_agents


def _apply_controversy_boost_to_env(env: Any, controversy_boost: float) -> None:
    boost = max(0.0, min(1.0, float(controversy_boost or 0.0)))
    if boost <= 0:
        return
    recsys = getattr(env, "rec_sys_reddit", None) or getattr(env, "rec_sys", None)
    if recsys is None:
        return
    calculate_hot_score = getattr(recsys, "calculate_hot_score", None)
    if not callable(calculate_hot_score):
        return

    def wrapped_hot_score(num_likes: int, num_dislikes: int, created_at, *args, **kwargs):
        try:
            return calculate_hot_score(
                num_likes,
                num_dislikes,
                created_at,
                controversy_boost=boost,
                *args,
                **kwargs,
            )
        except TypeError:
            return calculate_hot_score(num_likes, num_dislikes, created_at, *args, **kwargs)

    setattr(recsys, "calculate_hot_score", wrapped_hot_score)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _count_table(conn: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"] if row else 0)


async def run_simulation(payload: RunnerInput) -> dict[str, Any]:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph

    event_file = None
    if payload.events_path:
        event_path = Path(payload.events_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_file = event_path.open("a", encoding="utf-8")

    def emit_event(event_type: str, **data: Any) -> None:
        if not event_file:
            return
        event = {
            "event_type": event_type,
            "session_id": payload.simulation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            **data,
        }
        event_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        event_file.flush()

    ordered_personas = sorted(
        payload.personas,
        key=lambda persona: float(persona.get("mckainsey_relevance_score") or 0.0),
        reverse=True,
    )
    print(
        f"[oasis-runner] start simulation_id={payload.simulation_id} agents={len(payload.personas)} rounds={payload.rounds}",
        flush=True,
    )
    emit_event(
        "run_started",
        round_no=0,
        agent_count=len(payload.personas),
        platform="reddit",
        planned_rounds=payload.rounds,
    )

    os.environ["OPENAI_API_KEY"] = payload.api_key
    os.environ["OPENAI_BASE_URL"] = payload.base_url

    profiles_path = Path(payload.oasis_db_path).with_suffix(".profiles.json")
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles = [_to_profile(p, idx, payload.country) for idx, p in enumerate(ordered_personas)]
    activity_profiles = {
        int(profile["user_id"]): _build_activity_profile(ordered_personas[int(profile["user_id"])], int(profile["user_id"]))
        for profile in profiles
    }
    profile_lookup = {
        int(profile["user_id"]): {
            "agent_id": str(profile["agent_id"]),
            "display_name": str(profile.get("display_name") or profile["name"]),
            "subtitle": str(profile.get("subtitle") or "Sampled persona"),
            "occupation": str(profile.get("occupation") or "Resident"),
            "age": int(profile.get("age") or 0),
        }
        for profile in profiles
    }
    profiles_path.write_text(json.dumps(profiles), encoding="utf-8")

    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=payload.model_name,
        model_config_dict={"max_tokens": 4096},
    )

    available_actions = [
        ActionType.LIKE_POST,
        ActionType.DISLIKE_POST,
        ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_COMMENT,
        ActionType.DISLIKE_COMMENT,
        ActionType.SEARCH_POSTS,
        ActionType.SEARCH_USER,
        ActionType.TREND,
        ActionType.REFRESH,
        ActionType.DO_NOTHING,
        ActionType.FOLLOW,
        ActionType.MUTE,
    ]

    agent_graph = await generate_reddit_agent_graph(
        profile_path=str(profiles_path),
        model=model,
        available_actions=available_actions,
    )

    db_path = Path(payload.oasis_db_path)
    if db_path.exists():
        db_path.unlink()

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=str(db_path),
        semaphore=max(1, int(payload.oasis_semaphore)),
    )
    _apply_controversy_boost_to_env(env, payload.controversy_boost)

    await env.reset()
    start_monotonic = time.monotonic()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Seed the subject into the discussion thread before autonomous rounds.
    all_seed_agents = [agent for _, agent in env.agent_graph.get_agents()]
    seed_posts = _resolve_seed_posts(
        payload.subject_summary,
        payload.seed_discussion_threads,
        payload.country,
        seed_profiles=ordered_personas,
    )
    seed_post_titles: dict[int, str] = {}
    latest_seed_post_id = 0
    if all_seed_agents and seed_posts:
        batch_size = max(1, len(all_seed_agents))
        for batch_start in range(0, len(seed_posts), batch_size):
            seed_actions: dict[Any, Any] = {}
            batch_specs = seed_posts[batch_start: batch_start + batch_size]
            for agent, spec in zip(all_seed_agents, batch_specs):
                seed_actions[agent] = ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": spec.content},
                )
            if not seed_actions:
                continue
            await env.step(seed_actions)
            new_seed_rows = conn.execute(
                "SELECT post_id FROM post WHERE post_id > ? ORDER BY post_id",
                (latest_seed_post_id,),
            ).fetchall()
            for row, spec in zip(new_seed_rows, batch_specs):
                seed_post_titles[int(row["post_id"])] = spec.title
            if new_seed_rows:
                latest_seed_post_id = max(int(row["post_id"]) for row in new_seed_rows)
    print("[oasis-runner] seed posts injected", flush=True)
    emit_event("seed_post_created", round_no=1, count=len(seed_post_titles))

    last_seen = {"post": 0, "comment": 0, "like": 0, "dislike": 0, "comment_like": 0, "comment_dislike": 0}
    _emit_incremental_db_events(
        conn,
        profile_lookup=profile_lookup,
        user_map=None,
        post_titles=seed_post_titles,
        last_seen=last_seen,
        round_no=1,
        emit_event=emit_event,
        started_at=start_monotonic,
        planned_rounds=payload.rounds,
        elapsed_offset_seconds=payload.elapsed_offset_seconds,
        tail_checkpoint_estimate_seconds=payload.tail_checkpoint_estimate_seconds,
    )

    for i in range(payload.rounds):
        round_no = i + 1
        simulated_hour = _simulated_hour_for_round(i)
        active_agents = _get_active_agents_for_round(
            env,
            activity_profiles=activity_profiles,
            current_hour=simulated_hour,
            round_no=round_no,
        )

        emit_event(
            "round_started",
            round_no=round_no,
            simulated_hour=simulated_hour,
            active_agents=len(active_agents),
        )

        if not active_agents:
            _emit_incremental_db_events(
                conn,
                profile_lookup=profile_lookup,
                user_map=None,
                post_titles=seed_post_titles,
                last_seen=last_seen,
                round_no=round_no,
                emit_event=emit_event,
                started_at=start_monotonic,
                planned_rounds=payload.rounds,
                elapsed_offset_seconds=payload.elapsed_offset_seconds,
                tail_checkpoint_estimate_seconds=payload.tail_checkpoint_estimate_seconds,
            )
            emit_event("round_completed", round_no=round_no, active_agents=0, batch_count=0)
            continue

        batch_size = _determine_batch_size(len(active_agents), round_no)
        batch_count = int(math.ceil(len(active_agents) / batch_size))
        for batch_index in range(batch_count):
            start = batch_index * batch_size
            end = start + batch_size
            batch = active_agents[start:end]
            actions = {agent: LLMAction() for _, agent in batch}
            await env.step(actions)

            _emit_incremental_db_events(
                conn,
                profile_lookup=profile_lookup,
                user_map=None,
                post_titles=seed_post_titles,
                last_seen=last_seen,
                round_no=round_no,
                emit_event=emit_event,
                started_at=start_monotonic,
                planned_rounds=payload.rounds,
                elapsed_offset_seconds=payload.elapsed_offset_seconds,
                tail_checkpoint_estimate_seconds=payload.tail_checkpoint_estimate_seconds,
            )

            progress_payload = {
                "round": round_no,
                "batch": batch_index + 1,
                "total_batches": batch_count,
                "percentage": round(((batch_index + 1) / max(1, batch_count)) * 100, 1),
                "label": f"Round {round_no} ({round(((batch_index + 1) / max(1, batch_count)) * 100, 0):.0f}%)",
            }
            emit_event(
                "round_batch_flushed",
                round_no=round_no,
                batch_index=batch_index + 1,
                batch_count=batch_count,
                batch_size=len(batch),
                active_agents=len(active_agents),
                **progress_payload,
            )

        emit_event("round_completed", round_no=round_no, active_agents=len(active_agents), batch_count=batch_count)
        print(
            f"[oasis-runner] completed round {round_no}/{payload.rounds} "
            f"hour={simulated_hour:02d} active_agents={len(active_agents)} batches={batch_count}",
            flush=True,
        )

    await env.close()
    print("[oasis-runner] env closed, collecting artifacts", flush=True)

    user_rows = conn.execute("SELECT user_id, name FROM user ORDER BY user_id").fetchall()
    user_map = {int(r["user_id"]): profile_lookup.get(int(r["user_id"]), {}).get("agent_id", f"agent-{int(r['user_id']) + 1:04d}") for r in user_rows}

    interactions: list[dict[str, Any]] = []

    post_rows = conn.execute(
        "SELECT post_id, user_id, content, created_at FROM post ORDER BY post_id"
    ).fetchall()
    for row in post_rows:
        post_id = int(row["post_id"])
        interactions.append(
            {
                "round_no": 1,
                "post_id": post_id,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": None,
                "action_type": "create_post",
                "title": seed_post_titles.get(post_id) or _extract_title(str(row["content"])),
                "content": row["content"],
                "delta": 0.08,
            }
        )

    comment_rows = conn.execute(
        "SELECT comment_id, post_id, user_id, content, created_at FROM comment ORDER BY comment_id"
    ).fetchall()
    post_owner_map = {int(r["post_id"]): int(r["user_id"]) for r in post_rows}
    for row in comment_rows:
        target_user = post_owner_map.get(int(row["post_id"]))
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": user_map.get(target_user) if target_user is not None else None,
                "action_type": "comment",
                "content": row["content"],
                "delta": 0.04,
            }
        )

    like_rows = conn.execute("SELECT user_id, post_id FROM like ORDER BY like_id").fetchall()
    for row in like_rows:
        target_user = post_owner_map.get(int(row["post_id"]))
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": user_map.get(target_user) if target_user is not None else None,
                "action_type": "like_post",
                "content": f"Liked post {row['post_id']}",
                "delta": 0.02,
            }
        )

    dislike_rows = conn.execute("SELECT user_id, post_id FROM dislike ORDER BY dislike_id").fetchall()
    for row in dislike_rows:
        target_user = post_owner_map.get(int(row["post_id"]))
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": user_map.get(target_user) if target_user is not None else None,
                "action_type": "dislike_post",
                "content": f"Disliked post {row['post_id']}",
                "delta": -0.02,
            }
        )

    trace_rows = conn.execute(
        "SELECT user_id, action, info FROM trace ORDER BY created_at"
    ).fetchall()
    for row in trace_rows:
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": None,
                "action_type": "trace",
                "content": f"{row['action']}: {row['info']}",
                "delta": 0.0,
            }
        )

    simulation_elapsed_seconds = max(1, int(time.monotonic() - start_monotonic))
    counters = {
        "posts": len(post_rows),
        "comments": len(comment_rows),
        "reactions": len(like_rows) + len(dislike_rows),
        "active_authors": len({event["actor_agent_id"] for event in interactions if event["action_type"] in {"create_post", "comment"}}),
    }
    conn.close()
    if event_file:
        event_file.close()

    agents: list[dict[str, Any]] = []
    pre_scores: list[float] = []
    post_scores: list[float] = []
    actor_balance: dict[str, float] = {}
    for event in interactions:
        actor_balance[event["actor_agent_id"]] = actor_balance.get(event["actor_agent_id"], 0.0) + float(event.get("delta", 0.0))

    for idx, persona in enumerate(ordered_personas):
        agent_id = profile_lookup.get(idx, {}).get("agent_id", f"agent-{idx + 1:04d}")
        opinion_pre = _seed_opinion(persona)
        opinion_post = max(1.0, min(10.0, opinion_pre + actor_balance.get(agent_id, 0.0)))
        pre_scores.append(opinion_pre)
        post_scores.append(opinion_post)
        agents.append(
            {
                "agent_id": agent_id,
                "persona": persona,
                "opinion_pre": opinion_pre,
                "opinion_post": opinion_post,
            }
        )

    prompt_chars = len(payload.subject_summary or "")
    generated_chars = sum(len(str(event.get("content", "") or "")) for event in interactions)
    token_usage = {
        "input_tokens": max(1, int(prompt_chars / 4)) * max(1, len(ordered_personas)),
        "output_tokens": max(1, int(generated_chars / 4)),
        "cached_tokens": 0,
    }

    return {
        "simulation_id": payload.simulation_id,
        "agents": agents,
        "interactions": interactions,
        "stage3a_approval_rate": round(_approval(pre_scores), 4),
        "stage3b_approval_rate": round(_approval(post_scores), 4),
        "net_opinion_shift": (sum(post_scores) / len(post_scores)) - (sum(pre_scores) / len(pre_scores)),
        "runtime": "oasis",
        "oasis_db_path": str(db_path),
        "elapsed_seconds": simulation_elapsed_seconds,
        "counters": counters,
        "token_usage": token_usage,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: oasis_reddit_runner.py <input_json> <output_json>")

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    payload = RunnerInput(**json.loads(input_path.read_text(encoding="utf-8")))
    result = asyncio.run(run_simulation(payload))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result), encoding="utf-8")


def _emit_incremental_db_events(
    conn: sqlite3.Connection,
    *,
    profile_lookup: dict[int, dict[str, Any]],
    user_map: dict[int, str] | None,
    post_titles: dict[int, str],
    last_seen: dict[str, int],
    round_no: int,
    emit_event,
    started_at: float,
    planned_rounds: int,
    elapsed_offset_seconds: int,
    tail_checkpoint_estimate_seconds: int,
) -> None:
    user_rows = conn.execute("SELECT user_id, name FROM user ORDER BY user_id").fetchall()
    resolved_user_map = user_map or {
        int(r["user_id"]): profile_lookup.get(int(r["user_id"]), {}).get("agent_id", f"agent-{int(r['user_id']) + 1:04d}")
        for r in user_rows
    }

    post_rows = conn.execute(
        "SELECT post_id, user_id, content, created_at FROM post WHERE post_id > ? ORDER BY post_id",
        (last_seen["post"],),
    ).fetchall()
    for row in post_rows:
        user_id = int(row["user_id"])
        post_id = int(row["post_id"])
        last_seen["post"] = max(last_seen["post"], int(row["post_id"]))
        profile = profile_lookup.get(user_id, {})
        emit_event(
            "post_created",
            round_no=round_no,
            post_id=post_id,
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile.get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile.get("subtitle", "Sampled persona"),
            actor_occupation=profile.get("occupation", "Resident"),
            actor_age=profile.get("age", 0),
            title=post_titles.get(post_id) or _extract_title(str(row["content"])),
            content=row["content"],
            created_at=row["created_at"],
        )

    comment_rows = conn.execute(
        "SELECT comment_id, post_id, user_id, content, created_at FROM comment WHERE comment_id > ? ORDER BY comment_id",
        (last_seen["comment"],),
    ).fetchall()
    for row in comment_rows:
        user_id = int(row["user_id"])
        last_seen["comment"] = max(last_seen["comment"], int(row["comment_id"]))
        profile = profile_lookup.get(user_id, {})
        emit_event(
            "comment_created",
            round_no=round_no,
            comment_id=int(row["comment_id"]),
            post_id=int(row["post_id"]),
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile.get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile.get("subtitle", "Sampled persona"),
            actor_occupation=profile.get("occupation", "Resident"),
            actor_age=profile.get("age", 0),
            content=row["content"],
            created_at=row["created_at"],
        )

    like_rows = conn.execute(
        "SELECT like_id, user_id, post_id FROM like WHERE like_id > ? ORDER BY like_id",
        (last_seen["like"],),
    ).fetchall()
    for row in like_rows:
        user_id = int(row["user_id"])
        last_seen["like"] = max(last_seen["like"], int(row["like_id"]))
        profile = profile_lookup.get(user_id, {})
        emit_event(
            "reaction_added",
            round_no=round_no,
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile.get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile.get("subtitle", "Sampled persona"),
            actor_occupation=profile.get("occupation", "Resident"),
            actor_age=profile.get("age", 0),
            reaction="like",
            post_id=int(row["post_id"]),
        )

    dislike_rows = conn.execute(
        "SELECT dislike_id, user_id, post_id FROM dislike WHERE dislike_id > ? ORDER BY dislike_id",
        (last_seen["dislike"],),
    ).fetchall()
    for row in dislike_rows:
        user_id = int(row["user_id"])
        last_seen["dislike"] = max(last_seen["dislike"], int(row["dislike_id"]))
        profile = profile_lookup.get(user_id, {})
        emit_event(
            "reaction_added",
            round_no=round_no,
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile.get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile.get("subtitle", "Sampled persona"),
            actor_occupation=profile.get("occupation", "Resident"),
            actor_age=profile.get("age", 0),
            reaction="dislike",
            post_id=int(row["post_id"]),
        )

    # --- Comment likes ---
    comment_like_rows = conn.execute(
        "SELECT comment_like_id, user_id, comment_id FROM comment_like WHERE comment_like_id > ? ORDER BY comment_like_id",
        (last_seen["comment_like"],),
    ).fetchall()
    for row in comment_like_rows:
        user_id = int(row["user_id"])
        comment_id = int(row["comment_id"])
        last_seen["comment_like"] = max(last_seen["comment_like"], int(row["comment_like_id"]))
        comment_row = conn.execute("SELECT post_id FROM comment WHERE comment_id = ?", (comment_id,)).fetchone()
        if not comment_row:
            continue
        profile = profile_lookup.get(user_id, {})
        emit_event(
            "comment_reaction_added",
            round_no=round_no,
            comment_id=comment_id,
            post_id=int(comment_row["post_id"]),
            reaction="like",
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile.get("display_name", f"Agent {user_id + 1}"),
        )

    # --- Comment dislikes ---
    comment_dislike_rows = conn.execute(
        "SELECT comment_dislike_id, user_id, comment_id FROM comment_dislike WHERE comment_dislike_id > ? ORDER BY comment_dislike_id",
        (last_seen["comment_dislike"],),
    ).fetchall()
    for row in comment_dislike_rows:
        user_id = int(row["user_id"])
        comment_id = int(row["comment_id"])
        last_seen["comment_dislike"] = max(last_seen["comment_dislike"], int(row["comment_dislike_id"]))
        comment_row = conn.execute("SELECT post_id FROM comment WHERE comment_id = ?", (comment_id,)).fetchone()
        if not comment_row:
            continue
        profile = profile_lookup.get(user_id, {})
        emit_event(
            "comment_reaction_added",
            round_no=round_no,
            comment_id=comment_id,
            post_id=int(comment_row["post_id"]),
            reaction="dislike",
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile.get("display_name", f"Agent {user_id + 1}"),
        )

    comment_like_count = _count_table(conn, "comment_like")
    comment_dislike_count = _count_table(conn, "comment_dislike")
    total_like_count = _count_table(conn, "like")
    total_dislike_count = _count_table(conn, "dislike")
    total_posts = _count_table(conn, "post")
    total_comments = _count_table(conn, "comment")

    active_author_row = conn.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS count
        FROM (
            SELECT user_id FROM post
            UNION ALL
            SELECT user_id FROM comment
        )
        """
    ).fetchone()
    active_authors = int(active_author_row["count"] if active_author_row else 0)

    top_threads = []
    for row in conn.execute(
        """
        SELECT
            p.post_id,
            p.user_id,
            p.content,
            COALESCE(c.comment_count, 0) AS comment_count,
            COALESCE(lp.like_count, 0) AS like_count,
            COALESCE(dp.dislike_count, 0) AS dislike_count
        FROM post p
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count
            FROM comment
            GROUP BY post_id
        ) c ON c.post_id = p.post_id
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count
            FROM like
            GROUP BY post_id
        ) lp ON lp.post_id = p.post_id
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS dislike_count
            FROM dislike
            GROUP BY post_id
        ) dp ON dp.post_id = p.post_id
        ORDER BY (COALESCE(c.comment_count, 0) + COALESCE(lp.like_count, 0) + COALESCE(dp.dislike_count, 0)) DESC, p.post_id DESC
        LIMIT 3
        """
    ).fetchall():
        user_id = int(row["user_id"])
        engagement = int(row["comment_count"]) + int(row["like_count"]) + int(row["dislike_count"])
        post_id = int(row["post_id"])
        top_threads.append(
            {
            "post_id": post_id,
            "title": post_titles.get(post_id) or _extract_title(str(row["content"])),
                "author_agent_id": resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
                "author_name": profile_lookup.get(user_id, {}).get("display_name", f"Agent {user_id + 1}"),
                "engagement": engagement,
                "comments": int(row["comment_count"]),
                "likes": int(row["like_count"]),
                "dislikes": int(row["dislike_count"]),
            }
        )

    total_reactions = total_like_count + total_dislike_count + comment_like_count + comment_dislike_count
    net_reaction = total_like_count - total_dislike_count
    if net_reaction > 0:
        dominant_stance = "support"
    elif net_reaction < 0:
        dominant_stance = "dissent"
    else:
        dominant_stance = "mixed"

    runtime_elapsed_seconds = max(1, int(time.monotonic() - started_at))
    elapsed_seconds = elapsed_offset_seconds + runtime_elapsed_seconds
    if round_no > 0:
        observed_round_seconds = max(6, runtime_elapsed_seconds / max(1, round_no))
    else:
        observed_round_seconds = 12
    estimated_total_seconds = int(
        elapsed_offset_seconds + (observed_round_seconds * max(1, planned_rounds)) + tail_checkpoint_estimate_seconds
    )
    estimated_remaining_seconds = max(0, estimated_total_seconds - elapsed_seconds)
    round_progress = {
        "round": round_no,
        "batch": 0,
        "total_batches": 0,
        "percentage": 100.0,
        "label": f"Round {round_no} (100%)",
    }

    emit_event(
        "metrics_updated",
        round_no=round_no,
        elapsed_seconds=elapsed_seconds,
        estimated_total_seconds=estimated_total_seconds,
        estimated_remaining_seconds=estimated_remaining_seconds,
        counters={
            "posts": total_posts,
            "comments": total_comments,
            "reactions": total_reactions,
            "active_authors": active_authors,
            "post_dislikes": total_dislike_count,
            "comment_votes": comment_like_count + comment_dislike_count,
        },
        top_threads=top_threads,
        discussion_momentum={
            "approval_delta": round(net_reaction / max(1, total_reactions), 4),
            "dominant_stance": dominant_stance,
            "likes": total_like_count,
            "dislikes": total_dislike_count,
        },
        round_progress=round_progress,
        round_progress_label=round_progress["label"],
        metrics={
            "posts": total_posts,
            "comments": total_comments,
            "reactions": total_reactions,
            "active_authors": active_authors,
            "post_dislikes": total_dislike_count,
            "comment_votes": comment_like_count + comment_dislike_count,
            "top_thread_title": top_threads[0]["title"] if top_threads else None,
            "round_progress": round_progress,
            "round_progress_label": round_progress["label"],
        },
    )


if __name__ == "__main__":
    main()
