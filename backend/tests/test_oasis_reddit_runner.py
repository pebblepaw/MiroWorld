import importlib.util
from pathlib import Path
import sys


def _load_runner_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "oasis_reddit_runner.py"
    spec = importlib.util.spec_from_file_location("oasis_reddit_runner_test", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _runner_script_text() -> str:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "oasis_reddit_runner.py"
    return script_path.read_text(encoding="utf-8")


def test_seed_posts_do_not_include_hardcoded_demo_budget_phrase():
    source = _runner_script_text()

    assert "FY2026 budget summary and concerns" not in source
    assert "_build_seed_post_content" in source


def test_seed_post_builder_uses_policy_summary_excerpt():
    source = _runner_script_text()

    assert "summary_excerpt = \" \".join(str(policy_summary or \"\").split()).strip()[:220]" in source
    assert "Policy context for discussion:" in source


def test_seed_posts_are_analysis_question_threads_only_when_questions_exist():
    runner = _load_runner_module()

    seed_posts = runner._resolve_seed_posts(
        "A means-tested public transport subsidy is being proposed for lower-income workers in Singapore.",
        [
            "Do you approve of this subsidy? Rate 1-10.",
            "What concerns do you have about implementation fairness?",
        ],
    )

    assert len(seed_posts) == 2
    assert all(post.startswith("Analysis question ") for post in seed_posts)
    assert all("Policy thread kickoff" not in post for post in seed_posts)
    assert all("Policy context:" in post for post in seed_posts)


def test_seed_posts_fallback_uses_policy_context_without_legacy_kickoff_label():
    runner = _load_runner_module()

    seed_posts = runner._resolve_seed_posts(
        "A CPF top-up enhancement is under review for seniors aged 65+.",
        [],
    )

    assert len(seed_posts) == 1
    assert seed_posts[0].startswith("Policy context for discussion:")
    assert "Policy thread kickoff" not in seed_posts[0]


def test_seed_posts_preserve_policy_context_when_analysis_questions_exist():
    runner = _load_runner_module()

    seed_posts = runner._resolve_seed_posts(
        "The Child LifeSG Credits policy provides a one-off $500 credit for Singapore Citizen children aged 0 to 12 in 2026 for groceries, utilities, and pharmacy items.",
        [
            "Do you approve of this policy? Rate 1-10.",
            "How useful would the $500 Child LifeSG Credits be for your household's day-to-day expenses? Rate 1-10.",
        ],
    )

    assert len(seed_posts) == 2
    assert "Analysis question 1:" in seed_posts[0]
    assert "Child LifeSG Credits" in seed_posts[0]
    assert "Analysis question 2:" in seed_posts[1]
    assert "day-to-day expenses" in seed_posts[1]


def test_first_round_batching_is_single_agent_to_reduce_same_state_comment_clones():
    runner = _load_runner_module()

    assert runner._determine_batch_size(active_agent_count=35, round_no=1) == 1
    assert runner._determine_batch_size(active_agent_count=35, round_no=2) > 1


def test_round_execution_uses_active_agent_batches_with_flush_events():
    source = _runner_script_text()

    assert "active_agents = _get_active_agents_for_round(" in source
    assert "emit_event(\n                \"round_batch_flushed\"" in source


def test_seed_events_are_visible_in_round_one():
    source = _runner_script_text()

    assert 'emit_event("seed_post_created", round_no=1, count=len(seed_actions))' in source


def test_runner_input_supports_controversy_boost_and_progress_payload_fields():
    source = _runner_script_text()

    assert "controversy_boost: float = 0.0" in source
    assert '"round_batch_flushed"' in source
    assert '"percentage": round(' in source
    assert '"label": f"Round ' in source


def test_metrics_payload_tracks_post_dislikes_and_comment_votes():
    source = _runner_script_text()

    assert '"post_dislikes": total_dislike_count' in source
    assert '"comment_votes": comment_like_count + comment_dislike_count' in source
