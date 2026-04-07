from __future__ import annotations


class FakeConfigService:
    def get_checkpoint_questions(self, use_case):
        return [
            {
                "metric_name": "approval_rate",
                "type": "scale",
                "threshold": 7,
                "threshold_direction": "gte",
                "display_label": "Approval Rate",
            },
            {
                "metric_name": "net_sentiment",
                "type": "scale",
                "display_label": "Net Sentiment",
            },
            {
                "metric_name": "estimated_conversion",
                "type": "yes-no",
                "display_label": "Estimated Conversion",
            },
        ]


class FakeConfigUseCaseOnly:
    def get_use_case(self, use_case):
        del use_case
        return {
            "checkpoint_questions": [
                {
                    "metric_name": "approval_rate",
                    "type": "scale",
                    "threshold": 7,
                    "threshold_direction": "gte",
                    "display_label": "Approval Rate",
                },
                {
                    "metric_name": "net_sentiment",
                    "type": "scale",
                    "display_label": "Net Sentiment",
                },
            ]
        }


def test_metrics_service_handles_empty_inputs():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigService())

    dynamic = service.compute_dynamic_metrics([], "policy_review")
    polarization = service.compute_polarization_timeseries({}, "planning_area")
    opinion_flow = service.compute_opinion_flow([])
    influence = service.compute_influence([])
    selected = service.select_group_chat_agents([], [], "supporter", top_n=3)

    assert dynamic == {
        "approval_rate": {"value": 0.0, "unit": "%", "label": "Approval Rate"},
        "net_sentiment": {"value": 0.0, "unit": "/10", "label": "Net Sentiment"},
        "estimated_conversion": {"value": 0.0, "unit": "%", "label": "Estimated Conversion"},
    }
    assert polarization == []
    assert opinion_flow == {
        "initial": {"supporter": 0, "neutral": 0, "dissenter": 0},
        "final": {"supporter": 0, "neutral": 0, "dissenter": 0},
        "flows": [],
    }
    assert influence == {
        "top_influencers": [],
        "leaders": [],
        "items": [],
        "nodes": [],
        "edges": [],
        "total_nodes": 0,
        "total_edges": 0,
    }
    assert selected == []


def test_metrics_service_computes_polarization_extremes_and_stance_buckets():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigService())
    identical_agents = [
        {"persona": {"planning_area": "North"}, "opinion_post": 3},
        {"persona": {"planning_area": "North"}, "opinion_post": 3},
        {"persona": {"planning_area": "South"}, "opinion_post": 3},
    ]
    bimodal_agents = [
        {"persona": {"planning_area": "North"}, "opinion_post": 1},
        {"persona": {"planning_area": "North"}, "opinion_post": 1},
        {"persona": {"planning_area": "South"}, "opinion_post": 10},
        {"persona": {"planning_area": "South"}, "opinion_post": 10},
    ]
    opinion_flow_agents = [
        {"opinion_pre": 1, "opinion_post": 4},
        {"opinion_pre": 5, "opinion_post": 6},
        {"opinion_pre": 7, "opinion_post": 10},
    ]

    polarization_identical = service.compute_group_polarization(identical_agents, "planning_area")
    polarization_bimodal = service.compute_group_polarization(bimodal_agents, "planning_area")
    opinion_flow = service.compute_opinion_flow(opinion_flow_agents)
    supporters = service.select_group_chat_agents(
        [
            {"id": "a1", "persona": {"planning_area": "North"}, "opinion_post": 4},
            {"id": "a2", "persona": {"planning_area": "North"}, "opinion_post": 6},
            {"id": "a3", "persona": {"planning_area": "South"}, "opinion_post": 8},
        ],
        [],
        "supporter",
        top_n=10,
    )
    dissenters = service.select_group_chat_agents(
        [
            {"id": "a1", "persona": {"planning_area": "North"}, "opinion_post": 4},
            {"id": "a2", "persona": {"planning_area": "North"}, "opinion_post": 6},
            {"id": "a3", "persona": {"planning_area": "South"}, "opinion_post": 8},
        ],
        [],
        "dissenter",
        top_n=10,
    )
    dynamic = service.compute_dynamic_metrics(
        [
            {"checkpoint_approval_rate": 8, "checkpoint_net_sentiment": 6, "checkpoint_estimated_conversion": "yes"},
            {"checkpoint_approval_rate": 9, "checkpoint_net_sentiment": 7, "checkpoint_estimated_conversion": "no"},
            {"checkpoint_approval_rate": 4, "checkpoint_net_sentiment": 3, "checkpoint_estimated_conversion": "yes"},
        ],
        "policy_review",
    )

    assert polarization_identical["polarization_index"] == 0.0
    assert polarization_bimodal["polarization_index"] == 1.0
    assert opinion_flow["initial"] == {"supporter": 1, "neutral": 1, "dissenter": 1}
    assert opinion_flow["final"] == {"supporter": 1, "neutral": 1, "dissenter": 1}
    assert sum(opinion_flow["initial"].values()) == 3
    assert sum(opinion_flow["final"].values()) == 3
    assert {item["agent_id"] for item in supporters} == {"a3"}
    assert {item["agent_id"] for item in dissenters} == {"a1"}
    assert dynamic["approval_rate"]["value"] == 66.7
    assert dynamic["net_sentiment"]["value"] == 5.3
    assert dynamic["estimated_conversion"]["value"] == 66.7


def test_metrics_service_computes_influence_weighting():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigService())
    agents = [
        {"id": "a1", "persona": {"planning_area": "North"}, "opinion_post": 8},
        {"id": "a2", "persona": {"planning_area": "North"}, "opinion_post": 8},
        {"id": "a3", "persona": {"planning_area": "South"}, "opinion_post": 8},
        {"id": "a4", "persona": {"planning_area": "South"}, "opinion_post": 8},
    ]
    interactions = [
        {"actor_agent_id": "a1", "target_agent_id": "d1", "type": "post", "likes": 10, "dislikes": 0},
        {"actor_agent_id": "a2", "target_agent_id": "d2", "type": "comment", "likes": 0, "dislikes": 0},
        {"actor_agent_id": "a3", "target_agent_id": "d3", "type": "post", "likes": 0, "dislikes": 0},
        {"actor_agent_id": "a4", "target_agent_id": "a3", "type": "post", "likes": 0, "dislikes": 0},
    ]

    engaged = service.select_group_chat_agents(agents, interactions, "engaged", top_n=4)

    assert [item["agent_id"] for item in engaged] == ["a1", "a2", "a3", "a4"]
    assert [item["influence_score"] for item in engaged] == [0.4, 0.3, 0.3, 0.0]


def test_metrics_service_enriches_influence_with_display_fields():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigService())
    interactions = [
        {
            "actor_agent_id": "a1",
            "target_agent_id": "a2",
            "action_type": "create_post",
            "content": "Support the plan and keep rollout simple.",
            "delta": 1.6,
            "likes": 8,
            "dislikes": 1,
        },
        {
            "actor_agent_id": "a1",
            "target_agent_id": "a3",
            "action_type": "comment",
            "content": "We should prioritize affordability and clarity.",
            "delta": 0.6,
            "likes": 3,
            "dislikes": 0,
        },
        {
            "actor_agent_id": "a2",
            "target_agent_id": "a1",
            "action_type": "create_post",
            "content": "The rollout carries too much risk.",
            "delta": -1.4,
            "likes": 2,
            "dislikes": 4,
        },
    ]

    influence = service.compute_influence(interactions)

    assert "leaders" in influence
    assert "items" in influence
    assert influence["leaders"][0]["agent_id"] == "a1"
    assert influence["top_influencers"][0]["score"] == influence["top_influencers"][0]["influence_score"]
    assert influence["top_influencers"][0]["top_post"]["content"].startswith("Support the plan")
    assert influence["top_influencers"][0]["top_view"]
    assert influence["top_influencers"][0]["stance"] in {"supporter", "neutral", "dissenter"}


def test_metrics_service_uses_post_content_for_viewpoint_summaries():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigService())
    interactions = [
        {
            "actor_agent_id": "a1",
            "target_agent_id": "a2",
            "action_type": "create_post",
            "title": "Rollout update",
            "content": "We should keep the rollout simple and focus on affordability.",
            "delta": 1.2,
            "likes": 5,
            "dislikes": 0,
        }
    ]

    influence = service.compute_influence(interactions)

    assert "rollout simple" in influence["top_influencers"][0]["top_view"].lower()
    assert "Rollout update" not in influence["top_influencers"][0]["top_view"]


def test_metrics_service_builds_viral_post_threads_with_nested_comments():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigService())
    agents = [
        {"id": "a1", "persona": {"planning_area": "North"}, "opinion_pre": 3, "opinion_post": 8},
        {"id": "a2", "persona": {"planning_area": "South"}, "opinion_pre": 8, "opinion_post": 3},
        {"id": "a3", "persona": {"planning_area": "West"}, "opinion_pre": 5, "opinion_post": 6},
    ]
    posts = [
        {
            "id": "post-1",
            "actor_agent_id": "a1",
            "action_type": "create_post",
            "content": "Support the plan and highlight the upside.",
            "delta": 1.2,
        },
        {
            "id": "post-2",
            "actor_agent_id": "a2",
            "action_type": "create_post",
            "content": "The rollout feels risky without more safeguards.",
            "delta": -1.5,
        },
    ]
    comments = [
        {
            "id": "comment-1",
            "parent_post_id": "post-1",
            "actor_agent_id": "a3",
            "action_type": "comment",
            "content": "I agree with this framing.",
            "likes": 4,
            "dislikes": 0,
        },
        {
            "id": "comment-2",
            "parent_post_id": "post-1",
            "actor_agent_id": "a2",
            "action_type": "comment",
            "content": "Budget concerns remain unresolved.",
            "likes": 1,
            "dislikes": 3,
        },
        {
            "id": "comment-3",
            "parent_post_id": "post-2",
            "actor_agent_id": "a1",
            "action_type": "comment",
            "content": "This misses the implementation upside.",
            "likes": 2,
            "dislikes": 1,
        },
    ]

    cascades = service.compute_cascades(posts, comments, agents)

    assert isinstance(cascades["viral_posts"], list)
    assert cascades["viral_posts"][0]["post_id"] == "post-1"
    assert cascades["viral_posts"][0]["author"] == "a1"
    assert cascades["viral_posts"][0]["likes"] >= 1
    assert cascades["viral_posts"][0]["dislikes"] >= 0
    assert len(cascades["viral_posts"][0]["comments"]) == 2
    assert {"author", "stance", "content", "likes", "dislikes"}.issubset(cascades["viral_posts"][0]["comments"][0])
    assert isinstance(cascades["cascades"], list)
    assert isinstance(cascades["posts"], list)


def test_metrics_service_reads_checkpoint_questions_from_use_case_payload_when_needed():
    from mckainsey.services.metrics_service import MetricsService

    service = MetricsService(FakeConfigUseCaseOnly())
    agents = [
        {"checkpoint_approval_rate": 8, "checkpoint_net_sentiment": 7},
        {"checkpoint_approval_rate": 6, "checkpoint_net_sentiment": 5},
    ]

    dynamic = service.compute_dynamic_metrics(agents, "policy-review")

    assert dynamic["approval_rate"]["value"] == 50.0
    assert dynamic["net_sentiment"]["value"] == 6.0
