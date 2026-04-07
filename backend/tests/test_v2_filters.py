from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from mckainsey.config import Settings, get_settings
from mckainsey.main import app
from mckainsey.services.console_service import ConsoleService
from mckainsey.services.persona_relevance_service import PersonaRelevanceService


client = TestClient(app)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_singapore_parquet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    try:
        conn.execute(
            f"""
            COPY (
                SELECT * FROM (
                    VALUES
                        (24, 'Woodlands', 'Teacher', 'Female'),
                        (44, 'Yishun', 'Engineer', 'Male'),
                        (35, 'Woodlands', 'Nurse', 'Female')
                ) AS t(age, planning_area, occupation, sex)
            )
            TO '{path}'
            (FORMAT PARQUET)
            """
        )
    finally:
        conn.close()


def _write_usa_parquet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    try:
        conn.execute(
            f"""
            COPY (
                SELECT * FROM (
                    VALUES
                        (29, 'California', 'Engineer', 'Female', 'Hispanic'),
                        (51, 'Texas', 'Teacher', 'Male', 'White'),
                        (39, 'California', 'Nurse', 'Female', 'Black')
                ) AS t(age, state, occupation, gender, ethnicity)
            )
            TO '{path}'
            (FORMAT PARQUET)
            """
        )
    finally:
        conn.close()


def _settings(tmp_path: Path, countries_dir: Path, prompts_dir: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
    )


def test_v2_filters_endpoint_reads_country_dataset_schema(monkeypatch, tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"
    sg_parquet = tmp_path / "datasets" / "sg.parquet"
    us_parquet = tmp_path / "datasets" / "us.parquet"
    _write_singapore_parquet(sg_parquet)
    _write_usa_parquet(us_parquet)

    _write(
        countries_dir / "singapore.yaml",
        f"""
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "{sg_parquet}"
available: true
filter_fields:
  - field: "age"
    type: "range"
    label: "Age Range"
    default_min: 20
    default_max: 65
  - field: "planning_area"
    type: "multi-select-chips"
    label: "Planning Area"
  - field: "occupation"
    type: "dropdown"
    label: "Occupation"
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
        f"""
name: "United States"
code: "us"
flag_emoji: "🇺🇸"
dataset_path: "{us_parquet}"
available: true
filter_fields:
  - field: "age"
    type: "range"
    label: "Age Range"
    default_min: 18
    default_max: 70
  - field: "state"
    type: "multi-select-chips"
    label: "State"
  - field: "ethnicity"
    type: "dropdown"
    label: "Ethnicity"
geo_json_path: "/tmp/us.geo.json"
map_center: [39.8, -98.5]
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
description: "Policy reviews"
guiding_prompt: "Prompt"
agent_personality_modifiers: []
checkpoint_questions: []
report_sections: []
""".strip(),
    )

    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path, countries_dir, prompts_dir)
    try:
        created = client.post(
            "/api/v2/session/create",
            json={
                "country": "singapore",
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "api_key": "test-key",
                "use_case": "policy-review",
                "session_id": "session-filters-1",
            },
        )
        assert created.status_code == 200, created.text

        singapore_filters = client.get("/api/v2/console/session/session-filters-1/filters")
        assert singapore_filters.status_code == 200, singapore_filters.text
        sg_fields = {row["field"]: row for row in singapore_filters.json()["filters"]}
        assert sg_fields["age"]["min"] == 24
        assert sg_fields["age"]["max"] == 44
        assert sg_fields["planning_area"]["options"] == ["Woodlands", "Yishun"]
        assert sg_fields["occupation"]["options"] == ["Engineer", "Nurse", "Teacher"]

        updated = client.patch(
            "/api/v2/session/session-filters-1/config",
            json={"country": "usa"},
        )
        assert updated.status_code == 200, updated.text

        usa_filters = client.get("/api/v2/console/session/session-filters-1/filters")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert usa_filters.status_code == 200, usa_filters.text
    us_fields = {row["field"]: row for row in usa_filters.json()["filters"]}
    assert us_fields["state"]["options"] == ["California", "Texas"]
    assert us_fields["ethnicity"]["options"] == ["Black", "Hispanic", "White"]


def test_v2_filters_endpoint_resolves_country_dataset_to_local_shards(monkeypatch, tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"

    _write(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "backend/data/nemotron/singapore_nemotron_cc.parquet"
available: true
filter_fields:
  - field: "age"
    type: "range"
    label: "Age Range"
    default_min: 20
    default_max: 65
  - field: "planning_area"
    type: "multi-select-chips"
    label: "Planning Area"
  - field: "occupation"
    type: "dropdown"
    label: "Occupation"
  - field: "gender"
    type: "single-select-chips"
    label: "Gender"
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
description: "Policy reviews"
guiding_prompt: "Prompt"
agent_personality_modifiers: []
checkpoint_questions: []
report_sections: []
""".strip(),
    )

    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path, countries_dir, prompts_dir)
    try:
        created = client.post(
            "/api/v2/session/create",
            json={
                "country": "singapore",
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "api_key": "test-key",
                "use_case": "policy-review",
                "mode": "demo",
                "session_id": "session-missing-filters",
            },
        )
        assert created.status_code == 200, created.text

        filters = client.get("/api/v2/console/session/session-missing-filters/filters")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert filters.status_code == 200, filters.text
    body = filters.json()
    fields = {row["field"]: row for row in body["filters"]}
    assert body["country"] == "singapore"
    assert fields["age"]["min"] == 18
    assert fields["age"]["max"] == 108
    assert fields["planning_area"]["options"]
    assert fields["occupation"]["options"]
    assert fields["gender"]["options"] == ["Female", "Male"]


def test_console_service_sampling_flow_passes_dynamic_sampling_keys(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    service.store.upsert_console_session(
        session_id="session-dynamic-1",
        mode="live",
        status="knowledge_ready",
        model_provider="ollama",
        model_name="qwen3:4b-instruct-2507-q4_K_M",
        embed_model_name="nomic-embed-text",
        api_key="ollama",
        base_url="http://127.0.0.1:11434/v1/",
    )
    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda session_id: {"summary": "Policy context", "entity_nodes": [], "relationship_edges": []},
    )
    monkeypatch.setattr(
        PersonaRelevanceService,
        "parse_sampling_instructions",
        lambda self, instructions, knowledge_artifact=None, live_mode=False: {
            "hard_filters": {"ethnicity": ["hispanic"]},
            "soft_boosts": {},
            "soft_penalties": {},
            "exclusions": {},
            "distribution_targets": {},
            "notes_for_ui": [],
            "source": "test",
        },
    )

    captured: dict[str, object] = {}

    def fake_query_candidates(**kwargs):
        captured.update(kwargs)
        return [{"age": 33, "planning_area": "Woodlands", "occupation": "Teacher", "ethnicity": "hispanic"}]

    monkeypatch.setattr(service.sampler, "query_candidates", fake_query_candidates)
    monkeypatch.setattr(
        PersonaRelevanceService,
        "build_population_artifact",
        lambda self, *args, **kwargs: {
            "session_id": "session-dynamic-1",
            "candidate_count": 1,
            "sample_count": 1,
            "sample_mode": kwargs["sample_mode"],
            "sample_seed": kwargs["seed"],
            "parsed_sampling_instructions": kwargs["parsed_sampling_instructions"],
            "coverage": {},
            "sampled_personas": [],
            "agent_graph": {"nodes": [], "links": []},
            "representativeness": {"status": "narrow"},
            "selection_diagnostics": {},
        },
    )

    class Req:
        agent_count = 100
        sample_mode = "affected_groups"
        sampling_instructions = "Target Hispanic residents in HDB flats."
        seed = 99
        min_age = None
        max_age = None
        planning_areas: list[str] = []
        dynamic_filters = {"ethnicity": ["hispanic"], "housing_type": ["HDB"]}

        def model_dump(self):
            return {
                "agent_count": self.agent_count,
                "sample_mode": self.sample_mode,
                "sampling_instructions": self.sampling_instructions,
                "seed": self.seed,
                "min_age": self.min_age,
                "max_age": self.max_age,
                "planning_areas": self.planning_areas,
                "dynamic_filters": self.dynamic_filters,
            }

    artifact = service.preview_population("session-dynamic-1", Req())

    assert artifact["sample_seed"] == 99
    assert "extra_filters" in captured
    assert captured["extra_filters"] == {
        "ethnicity": ["hispanic"],
        "housing_type": ["HDB"],
    }


def test_v2_session_create_live_mode_returns_structured_error_for_ollama_validation_failure(monkeypatch, tmp_path):
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
description: "Policy reviews"
guiding_prompt: "Prompt"
agent_personality_modifiers: []
checkpoint_questions: []
report_sections: []
""".strip(),
    )

    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path, countries_dir, prompts_dir)
    monkeypatch.setattr(
        "mckainsey.services.console_service.ensure_ollama_models_available",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Ollama runtime unavailable")),
    )
    try:
        response = client.post(
            "/api/v2/session/create",
            json={
                "country": "singapore",
                "provider": "ollama",
                "model": "qwen3:4b-instruct-2507-q4_K_M",
                "use_case": "policy-review",
                "mode": "live",
                "session_id": "session-live-error",
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 502, response.text
    assert "Session creation failed" in response.text
    assert "Ollama runtime unavailable" in response.text


def test_v2_token_usage_estimate_and_runtime_endpoints():
    created = client.post(
        "/api/v2/console/session",
        json={
            "session_id": "session-token-1",
            "mode": "live",
            "model_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "test-key",
        },
    )
    assert created.status_code == 200, created.text

    estimate = client.get("/api/v2/token-usage/session-token-1/estimate?agents=10&rounds=3")
    assert estimate.status_code == 200, estimate.text
    estimate_payload = estimate.json()
    assert estimate_payload["model"] == "gpt-4o"
    assert estimate_payload["with_caching_usd"] == estimate_payload["without_caching_usd"]
    assert estimate_payload["savings_pct"] == 0

    runtime = client.get("/api/v2/token-usage/session-token-1")
    assert runtime.status_code == 200, runtime.text
    runtime_payload = runtime.json()
    assert runtime_payload["model"] == "gpt-4o"
    assert runtime_payload["total_input_tokens"] == 0
    assert runtime_payload["total_output_tokens"] == 0
