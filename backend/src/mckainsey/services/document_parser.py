from __future__ import annotations

from io import BytesIO
import json
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
}


def extract_document_text(filename: str, payload: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(payload)
    if suffix == ".docx":
        return _parse_docx(payload)
    if suffix in TEXT_EXTENSIONS or not suffix:
        return _parse_text_like(suffix, payload)
    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")


def _parse_pdf(payload: bytes) -> str:
    reader = PdfReader(BytesIO(payload))
    parts = [page.extract_text() or "" for page in reader.pages]
    return _normalize_text("\n".join(parts))


def _parse_docx(payload: bytes) -> str:
    doc = Document(BytesIO(payload))
    parts = [paragraph.text for paragraph in doc.paragraphs]
    return _normalize_text("\n".join(parts))


def _parse_text_like(suffix: str, payload: bytes) -> str:
    text = payload.decode("utf-8", errors="ignore")
    if suffix == ".json":
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    if suffix in {".html", ".htm"}:
        text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_text(text)


def _normalize_text(text: str) -> str:
    normalized = text.replace("\x00", " ")
    normalized = re.sub(r"\r\n?", "\n", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("No readable text could be extracted from the uploaded file.")
    return normalized
