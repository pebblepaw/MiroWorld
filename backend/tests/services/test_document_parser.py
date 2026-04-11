from __future__ import annotations

from miroworld.services import document_parser


def test_extract_document_text_uses_markitdown_for_pptx(monkeypatch, tmp_path) -> None:
    class _Result:
        text_content = "Slide 1\n\nKey findings"

    class _Client:
        def __init__(self) -> None:
            self.paths: list[str] = []

        def convert(self, path: str) -> _Result:
            self.paths.append(path)
            return _Result()

    client = _Client()
    monkeypatch.setattr(document_parser, "_get_markitdown_client", lambda: client)

    text = document_parser.extract_document_text("deck.pptx", b"fake-pptx")

    assert text == "Slide 1\n\nKey findings"
    assert client.paths and client.paths[0].endswith(".pptx")


def test_extract_document_text_preserves_text_like_normalization() -> None:
    text = document_parser.extract_document_text("policy.html", b"<h1>Policy</h1><p>Line 1</p>")

    assert text == "Policy Line 1"


def test_extract_document_text_falls_back_when_markitdown_returns_repr_like_result(monkeypatch) -> None:
    class _Result:
        def __str__(self) -> str:
            return "DocumentConverterResult(markitdown)"

    class _Client:
        def convert(self, path: str) -> _Result:
            del path
            return _Result()

    monkeypatch.setattr(document_parser, "_get_markitdown_client", lambda: _Client())
    monkeypatch.setattr(document_parser, "_parse_pdf", lambda payload: "PDF fallback text")

    text = document_parser.extract_document_text("policy.pdf", b"fake-pdf")

    assert text == "PDF fallback text"
