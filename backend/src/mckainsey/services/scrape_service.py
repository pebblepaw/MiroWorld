from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import requests

try:  # pragma: no cover - exercised indirectly when available
    from bs4 import BeautifulSoup
except Exception:  # noqa: BLE001
    BeautifulSoup = None


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:  # noqa: D401
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:  # noqa: D401
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:  # noqa: D401
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return " ".join(self._chunks)


class ScrapeService:
    """Fetch and extract lightweight article text for document upload."""

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = max(1, int(timeout_seconds))

    def validate_url(self, url: str) -> str:
        cleaned = str(url or "").strip()
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url!r}")
        return cleaned

    def scrape(self, url: str) -> dict[str, Any]:
        validated = self.validate_url(url)
        response = requests.get(validated, timeout=self.timeout_seconds)
        response.raise_for_status()
        return self._extract(response.text, validated)

    def _extract(self, html: str, url: str) -> dict[str, Any]:
        title = ""
        body_text = ""

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(" ", strip=True)
            body = soup.body or soup
            body_text = body.get_text(" ", strip=True)
        else:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
            if title_match:
                title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            parser = _TextCollector()
            parser.feed(html)
            body_text = parser.text()

        text = body_text.strip()
        if title:
            normalized_body = body_text.strip()
            if not normalized_body:
                text = title
            elif not normalized_body.lower().startswith(title.lower()):
                text = " ".join(part for part in [title, normalized_body] if part).strip()
            else:
                text = normalized_body
        return {
            "url": url,
            "title": title,
            "text": text,
            "length": len(text),
        }
