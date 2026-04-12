from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


_RUNNER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "oasis_reddit_runner.py"
_SPEC = importlib.util.spec_from_file_location("oasis_reddit_runner", _RUNNER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
_extract_title = _MODULE._extract_title
_resolve_seed_posts = _MODULE._resolve_seed_posts


def test_extract_title_removes_first_person_lead_in_and_surfaces_core_topic() -> None:
    content = (
        "I think the childcare subsidy will help working parents in Tampines, "
        "but the rollout still feels confusing for part-time caregivers."
    )

    title = _extract_title(content)

    assert "childcare subsidy" in title.lower()
    assert "working parents" in title.lower()
    assert not title.lower().startswith("i think")
    assert len(title.split()) <= 8


def test_resolve_seed_posts_preserves_question_titles_and_limits_body_words() -> None:
    seed_posts = _resolve_seed_posts(
        policy_summary=(
            "The policy adds direct fare support for lower-income commuters, expands off-peak discounts, "
            "and funds a simpler mobile sign-up flow for eligible households. "
            "It also increases outreach at neighborhood transport hubs."
        ),
        seed_discussion_threads=["[Will this keep transport affordable?]"],
        country="Singapore",
        seed_profiles=[{"occupation": "Teacher", "planning_area": "Woodlands"}],
    )

    assert len(seed_posts) == 1
    assert seed_posts[0].title == "[Will this keep transport affordable?] (Seeded post)"
    assert len(seed_posts[0].content.split()) <= 100
    assert "Community prompt:" not in seed_posts[0].content
    assert "Policy brief:" not in seed_posts[0].content
    assert "**" not in seed_posts[0].content
    assert "woodlands" in seed_posts[0].content.lower()
