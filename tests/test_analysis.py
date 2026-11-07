import json

import pytest

from docudude import analysis
from docudude.analysis import (
    analyze_document,
    find_unverified_numbers,
    is_grounded,
    limit_text,
    parse_json_object,
    split_into_sections,
)

OCR_TEXT = (
    "INVOICE No. INV-2024-0387\nDate: 14 March 2024\n"
    "Bill to: Fathima Rizwan\nTotal due LKR 3,516.99"
)


def test_grounding_ignores_spacing_case_and_punctuation():
    assert is_grounded("inv 2024 0387", OCR_TEXT)
    assert is_grounded("3516.99", OCR_TEXT)
    assert not is_grounded("2024-03-14", OCR_TEXT)  # reformatted date
    assert not is_grounded("", OCR_TEXT)


def test_unverified_numbers_flags_invented_values():
    summary = "Invoice INV-2024-0387 for LKR 3,516.99, due 4,000 days later."
    assert find_unverified_numbers(summary, OCR_TEXT) == ["4,000"]


def test_parse_json_handles_fences_and_prose():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Here you go: {"a": 2} hope it helps') == {"a": 2}
    with pytest.raises(ValueError):
        parse_json_object("no json here")


def test_limit_text_prefers_sentence_boundary():
    text = ("This is a sentence. " * 60).strip()
    limited = limit_text(text, 100)
    assert len(limited) <= 100 and limited.endswith(".")


def test_sections_split_on_page_boundaries(monkeypatch):
    monkeypatch.setattr(analysis, "CHUNK_CHARACTERS", 50)
    sections = split_into_sections([(1, "a" * 30), (2, "b" * 30), (3, "c" * 120)])
    assert sections[0].startswith("=== Page 1 ===")
    assert all(len(section) <= 50 for section in sections)
    assert "".join(sections).count("c") == 120


def _fake_response(payload):
    return {"message": {"content": json.dumps(payload)}}


def test_analyze_marks_unverified_fields(monkeypatch):
    payload = {
        "document_type": "Invoice",
        "title": "INVOICE",
        "summary": "Invoice INV-2024-0387 billed to Fathima Rizwan for LKR 3,516.99.",
        "key_fields": [
            {"label": "Invoice number", "value": "INV-2024-0387", "source_text": "INVOICE No. INV-2024-0387"},
            {"label": "Due date", "value": "2024-04-13", "source_text": ""},
            {"label": "Total", "value": "3,516.99", "source_text": "Total due LKR 3,516.99"},
        ],
        "issues": [],
    }
    requests = []
    monkeypatch.setattr(
        analysis, "_post_chat", lambda key, body: requests.append(body) or _fake_response(payload)
    )
    result = analyze_document(api_key="k", model="m", pages=[(1, OCR_TEXT)], ocr_confidence=91)

    assert requests[0]["format"] == analysis.ANALYSIS_SCHEMA
    assert requests[0]["options"]["temperature"] == 0
    assert [f.verified for f in result.key_fields] == [True, True, False]  # unverified last
    assert result.verified_count == 2
    assert result.unverified_numbers == []


def test_analyze_retries_after_invalid_json(monkeypatch):
    replies = iter([
        {"message": {"content": "sorry"}},
        _fake_response({"document_type": "Letter", "title": "", "summary": "A letter.",
                        "key_fields": [], "issues": []}),
    ])
    monkeypatch.setattr(analysis, "_post_chat", lambda key, body: next(replies))
    assert analyze_document(api_key="k", model="m", pages=[(1, "Dear Sir")]).document_type == "Letter"


def test_long_documents_are_analysed_in_sections(monkeypatch):
    monkeypatch.setattr(analysis, "CHUNK_CHARACTERS", 40)
    calls = []

    def fake(key, body):
        calls.append(body)
        return _fake_response({
            "document_type": "Report", "title": "", "summary": f"Part {len(calls)}.",
            "key_fields": [{"label": "Ref", "value": "AB12", "source_text": "AB12"}],
            "issues": [],
        })

    monkeypatch.setattr(analysis, "_post_chat", fake)
    pages = [(1, "Ref AB12 " * 3), (2, "More text here " * 2)]
    result = analyze_document(api_key="k", model="m", pages=pages)
    assert result.sections_analysed == len(calls) - 1 > 1  # sections + one combine call
    assert len(result.key_fields) == 1  # duplicates merged
    assert result.key_fields[0].verified


def test_missing_api_key_is_reported():
    with pytest.raises(analysis.OllamaError):
        analyze_document(api_key=" ", model="m", pages=[(1, "x")])
