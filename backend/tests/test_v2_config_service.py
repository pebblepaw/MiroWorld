from pathlib import Path

import pytest

from mckainsey.config import Settings
from mckainsey.services.config_service import ConfigService


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _settings(tmp_path: Path, countries_dir: Path, prompts_dir: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
    )


def test_config_service_loads_valid_yaml_and_supports_use_case_aliases(tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"

    _write(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields:
  - field: "age"
    type: "range"
    label: "Age Range"
geo_json_path: "/tmp/sg.geo.json"
map_center: [1.35, 103.81]
map_zoom: 11
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write(
        prompts_dir / "product-market-research.yaml",
        """
name: "Product & Market Research"
code: "product-market-research"
description: "Simulate product and market research."
guiding_prompt: "Prompt body"
agent_personality_modifiers:
  - "Modifier 1"
checkpoint_questions:
  - question: "Satisfied?"
    type: "scale"
    metric_name: "satisfaction"
    display_label: "Satisfaction"
report_sections:
  - title: "Overview"
    prompt: "Summarize sentiment."
""".strip(),
    )

    service = ConfigService(_settings(tmp_path, countries_dir, prompts_dir))
    country = service.get_country("singapore")
    use_case = service.get_use_case("reviews")

    assert country["code"] == "sg"
    assert country["name"] == "Singapore"
    assert use_case["code"] == "product-market-research"


def test_config_service_missing_country_or_use_case_raises_file_not_found(tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"
    service = ConfigService(_settings(tmp_path, countries_dir, prompts_dir))

    with pytest.raises(FileNotFoundError):
        service.get_country("usa")

    with pytest.raises(FileNotFoundError):
        service.get_use_case("policy-review")


def test_config_service_discovery_skips_invalid_yaml_and_logs_error(tmp_path, caplog):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"

    _write(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields: []
geo_json_path: "/tmp/sg.geo.json"
map_center: [1.35, 103.81]
map_zoom: 11
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write(
        countries_dir / "broken.yaml",
        """
name: "Broken"
code: "xx"
available true
""".strip(),
    )

    service = ConfigService(_settings(tmp_path, countries_dir, prompts_dir))
    with caplog.at_level("ERROR"):
        countries = service.list_countries()

    assert len(countries) == 1
    assert countries[0]["code"] == "sg"
    assert any("broken.yaml" in record.message for record in caplog.records)


def test_config_service_lists_all_countries_and_returns_checkpoint_question_shapes(tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"

    _write(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields: []
geo_json_path: "/tmp/sg.geo.json"
map_center: [1.35, 103.81]
map_zoom: 11
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write(
        countries_dir / "usa.yaml",
        """
name: "United States"
code: "us"
flag_emoji: "🇺🇸"
dataset_path: "/tmp/us.parquet"
available: false
filter_fields: []
geo_json_path: "/tmp/us.geo.json"
map_center: [39.82, -98.57]
map_zoom: 4
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write(
        prompts_dir / "policy-review.yaml",
        """
name: "Policy Review"
code: "policy-review"
description: "Evaluate public sentiment toward a government policy"
guiding_prompt: "Prompt body"
agent_personality_modifiers:
  - "Modifier 1"
checkpoint_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    threshold: 7
    threshold_direction: "gte"
    display_label: "Approval Rate"
    tooltip: "Approval tooltip"
report_sections:
  - title: "Overview"
    prompt: "Summarize sentiment."
""".strip(),
    )

    service = ConfigService(_settings(tmp_path, countries_dir, prompts_dir))

    countries = service.list_countries()
    questions = service.get_checkpoint_questions("policy-review")

    assert {country["code"] for country in countries} == {"sg", "us"}
    assert questions == [
        {
            "question": "Do you approve of this policy? Rate 1-10.",
            "type": "scale",
            "metric_name": "approval_rate",
            "threshold": 7,
            "threshold_direction": "gte",
            "display_label": "Approval Rate",
            "tooltip": "Approval tooltip",
        }
    ]


def test_config_service_returns_personality_modifiers_and_report_sections(tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"

    _write(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields: []
geo_json_path: "/tmp/sg.geo.json"
map_center: [1.35, 103.81]
map_zoom: 11
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write(
        prompts_dir / "policy-review.yaml",
        """
name: "Policy Review"
code: "policy-review"
description: "Evaluate public sentiment toward a government policy"
guiding_prompt: "Prompt body"
agent_personality_modifiers:
  - "Express concern about affordability"
  - "Respond with concrete examples"
checkpoint_questions: []
report_sections:
  - title: "Approval"
    prompt: "Summarize approval trends."
  - title: "Recommendation"
    prompt: "List concrete actions."
""".strip(),
    )

    service = ConfigService(_settings(tmp_path, countries_dir, prompts_dir))

    assert service.get_agent_personality_modifiers("policy-review") == [
        "Express concern about affordability",
        "Respond with concrete examples",
    ]
    assert service.get_report_sections("policy-review") == [
        {"title": "Approval", "prompt": "Summarize approval trends."},
        {"title": "Recommendation", "prompt": "List concrete actions."},
    ]
