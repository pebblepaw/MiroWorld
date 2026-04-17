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

    _NOISE_TAGS = {"script", "style", "noscript", "header", "nav", "footer", "aside", "form", "button", "svg"}
    _NOISE_HINTS = (
        "advert",
        "banner",
        "breadcrumb",
        "comment",
        "consent",
        "cookie",
        "donate",
        "donation",
        "footer",
        "menu",
        "nav",
        "newsletter",
        "popover",
        "promo",
        "related",
        "republish",
        "share",
        "sidebar",
        "signup",
        "social",
        "subscribe",
        "toolbar",
    )

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
            body_text = self._extract_soup_text(soup)
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

    def _extract_soup_text(self, soup: Any) -> str:
        for element in soup.find_all(self._NOISE_TAGS):
            element.decompose()

        for element in soup.find_all(True):
            attrs = getattr(element, "attrs", None)
            if not isinstance(attrs, dict):
                continue
            attr_tokens = [
                str(attrs.get("id") or "").strip().lower(),
                *(str(item).strip().lower() for item in (attrs.get("class") or []) if str(item).strip()),
                str(attrs.get("role") or "").strip().lower(),
                str(attrs.get("aria-label") or "").strip().lower(),
            ]
            if any(self._token_matches_noise_hint(token) for token in attr_tokens):
                element.decompose()

        content_root = self._select_content_root(soup)
        text = content_root.get_text(" ", strip=True) if content_root is not None else ""
        return re.sub(r"\s+", " ", text).strip()

    def _select_content_root(self, soup: Any) -> Any:
        selectors = ("article", "main", "[role='main']", ".article", ".story-body", ".post-content")
        for selector in selectors:
            candidate = soup.select_one(selector)
            if candidate is not None and self._content_score(candidate) > 200:
                return candidate

        candidates: list[tuple[int, Any]] = []
        for candidate in soup.find_all(["section", "div"]):
            score = self._content_score(candidate)
            if score > 0:
                candidates.append((score, candidate))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]
        return soup.body or soup

    def _content_score(self, node: Any) -> int:
        parts: list[str] = []
        for child in node.find_all(["h1", "h2", "h3", "p", "li"], recursive=True):
            text = child.get_text(" ", strip=True)
            if text:
                parts.append(text)
        if not parts:
            fallback = node.get_text(" ", strip=True)
            return len(re.sub(r"\s+", " ", fallback).strip())
        return sum(len(part) for part in parts)

    def _token_matches_noise_hint(self, token: str) -> bool:
        clean = str(token or "").strip().lower()
        if not clean:
            return False
        for hint in self._NOISE_HINTS:
            if clean == hint:
                return True
            if clean.startswith(f"{hint}-") or clean.startswith(f"{hint}_"):
                return True
        return False
