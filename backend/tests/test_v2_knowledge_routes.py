from pathlib import Path

from fastapi.testclient import TestClient

from mckainsey.config import Settings, get_settings
from mckainsey.main import app


client = TestClient(app)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _settings(tmp_path: Path, countries_dir: Path, prompts_dir: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
    )


def test_v2_scrape_route_returns_scraped_payload(monkeypatch):
    def fake_scrape(self, url: str):  # noqa: ANN001
        assert url == "https://example.com/policy"
        return {
            "url": url,
            "title": "Policy Update",
            "text": "Policy update body text for residents.",
            "length": 38,
        }

    monkeypatch.setattr("mckainsey.api.routes_console.ScrapeService.scrape", fake_scrape)
    response = client.post(
        "/api/v2/console/session/session-a/scrape",
        json={"url": "https://example.com/policy"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Policy Update"
    assert body["length"] == 38
    assert "residents" in body["text"]


def test_v2_scrape_route_returns_400_for_invalid_url():
    response = client.post(
        "/api/v2/console/session/session-a/scrape",
        json={"url": "not-a-url"},
    )

    assert response.status_code == 400, response.text
    assert "invalid url" in response.text.lower()


def test_v2_knowledge_process_merges_documents_and_uses_yaml_guiding_prompt(monkeypatch, tmp_path):
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
guiding_prompt: "Use this default guiding prompt from YAML."
agent_personality_modifiers: []
checkpoint_questions: []
report_sections: []
""".strip(),
    )

    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path, countries_dir, prompts_dir)
    calls: list[dict[str, str | None]] = []

    async def fake_process_document(
        self,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        guiding_prompt: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
    ):
        del live_mode
        calls.append(
            {
                "simulation_id": simulation_id,
                "source_path": source_path,
                "guiding_prompt": guiding_prompt,
                "demographic_focus": demographic_focus,
            }
        )
        suffix = "a" if source_path and "a" in source_path else "b"
        return {
            "simulation_id": simulation_id,
            "document_id": f"doc-{suffix}",
            "document": {
                "document_id": f"doc-{suffix}",
                "source_path": source_path,
                "text_length": len(document_text),
                "paragraph_count": 1,
            },
            "summary": f"Summary {suffix.upper()}",
            "guiding_prompt": guiding_prompt,
            "entity_nodes": [
                {
                    "id": f"policy-{suffix}",
                    "label": f"Policy {suffix.upper()}",
                    "type": "policy",
                }
            ],
            "relationship_edges": [
                {
                    "source": f"policy-{suffix}",
                    "target": "group-seniors",
                    "type": "targets",
                    "label": "Targets seniors",
                }
            ],
            "entity_type_counts": {"policy": 1},
            "graph_origin": "test",
            "processing_logs": [f"processed-{suffix}"],
            "demographic_focus_summary": demographic_focus,
        }

    monkeypatch.setattr("mckainsey.services.console_service.LightRAGService.process_document", fake_process_document)
    try:
        created = client.post(
            "/api/v2/session/create",
            json={
                "country": "singapore",
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "api_key": "test-key",
                "use_case": "policy-review",
                "session_id": "session-merge-1",
            },
        )
        assert created.status_code == 200, created.text

        response = client.post(
            "/api/v2/console/session/session-merge-1/knowledge/process",
            json={
                "documents": [
                    {"document_text": "Document A policy content.", "source_path": "inline-a.md"},
                    {"document_text": "Document B policy content.", "source_path": "inline-b.md"},
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["guiding_prompt"] == "Use this default guiding prompt from YAML."
    assert len(calls) == 2
    assert calls[0]["guiding_prompt"] == "Use this default guiding prompt from YAML."
    assert len(body["document"]["sources"]) == 2
    assert len(body["entity_nodes"]) == 2
    assert len(body["relationship_edges"]) == 2
    assert "Summary A" in body["summary"]
    assert "Summary B" in body["summary"]
