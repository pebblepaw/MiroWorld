from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_scrape_service_rejects_invalid_url_without_fetch(monkeypatch):
    from mckainsey.services.scrape_service import ScrapeService

    service = ScrapeService()

    def fake_get(*args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("fetch should not happen for invalid URLs")

    monkeypatch.setattr("mckainsey.services.scrape_service.requests.get", fake_get)

    with pytest.raises(ValueError):
        service.scrape("not-a-url")


def test_scrape_service_extracts_title_text_and_length_from_html(monkeypatch):
    from mckainsey.services.scrape_service import ScrapeService

    html = """
        <html>
          <head><title>Example Article</title></head>
          <body>
            <h1>Example Article</h1>
            <p>Alpha beta.</p>
            <p>Gamma delta.</p>
          </body>
        </html>
    """

    def fake_get(url, timeout):
        assert url == "https://example.com/article"
        assert timeout == 15
        return SimpleNamespace(
            status_code=200,
            text=html,
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr("mckainsey.services.scrape_service.requests.get", fake_get)

    service = ScrapeService(timeout_seconds=15)
    result = service.scrape("https://example.com/article")

    assert result["title"] == "Example Article"
    assert result["text"] == "Example Article Alpha beta. Gamma delta."
    assert result["length"] == len(result["text"])
