from __future__ import annotations

from io import BytesIO
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

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
    if suffix in TEXT_EXTENSIONS or not suffix:
        return _parse_text_like(suffix, payload)
    if suffix in {".pdf", ".docx"}:
        try:
            return _parse_with_markitdown(filename, payload)
        except Exception:
            if suffix == ".pdf":
                return _parse_pdf(payload)
            return _parse_docx(payload)
    return _parse_with_markitdown(filename, payload)


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


def _parse_with_markitdown(filename: str, payload: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    client = _get_markitdown_client()
    with NamedTemporaryFile(delete=False, suffix=suffix or ".bin") as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    try:
        result = client.convert(str(temp_path))
        text = _extract_markitdown_text(result)
        return _normalize_text(text)
    finally:
        temp_path.unlink(missing_ok=True)


def _get_markitdown_client():
    try:
        from markitdown import MarkItDown
    except ImportError as exc:  # pragma: no cover - exercised via integration environments
        raise RuntimeError("MarkItDown is required for this document type but is not installed.") from exc
    return MarkItDown()


def _extract_markitdown_text(result: object) -> str:
    if isinstance(result, str):
        return result

    for attribute in ("text_content", "markdown", "plain_text", "text", "content"):
        value = getattr(result, attribute, None)
        if isinstance(value, str) and value.strip():
            return value

    raise ValueError("MarkItDown did not return readable text content.")


def _normalize_text(text: str) -> str:
    normalized = text.replace("\x00", " ")
    normalized = re.sub(r"\r\n?", "\n", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("No readable text could be extracted from the uploaded file.")
    return normalized
