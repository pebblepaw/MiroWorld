from pathlib import Path


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
    assert "Policy thread kickoff {index + 1}: {summary_excerpt}" in source


def test_policy_kickoff_is_limited_to_single_seed_post():
    source = _runner_script_text()

    assert "seed_agents = [agent for _, agent in env.agent_graph.get_agents()][: min(1, len(profiles))]" in source


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
