"""Processed-document model and export helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field

from docudude.analysis import DocumentAnalysis
from docudude.ocr import PageResult


@dataclass
class ProcessedDocument:
    name: str
    file_hash: str
    pages: list[PageResult] = field(default_factory=list)
    error: str | None = None
    analysis: DocumentAnalysis | None = None
    analysis_error: str | None = None
    # Unique per processing run, so widget state never leaks between runs.
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def confidence(self) -> float | None:
        """Word-count-weighted OCR confidence across OCR'd pages."""
        weighted = [
            (page.confidence, page.word_count)
            for page in self.pages
            if page.confidence is not None and page.word_count
        ]
        total = sum(words for _, words in weighted)
        if not total:
            return None
        return round(sum(conf * words for conf, words in weighted) / total, 1)

    @property
    def word_count(self) -> int:
        return sum(page.word_count for page in self.pages)


def confidence_band(confidence: float | None) -> tuple[str, str]:
    """(label, css-class) describing an OCR confidence value."""
    if confidence is None:
        return "Digital text", "badge-neutral"
    if confidence >= 90:
        return f"High confidence · {confidence:.0f}%", "badge-good"
    if confidence >= 75:
        return f"Review suggested · {confidence:.0f}%", "badge-fair"
    return f"Low confidence · {confidence:.0f}%", "badge-poor"


def document_to_text(document: ProcessedDocument, page_texts: dict[int, str]) -> str:
    """Plain-text export. ``page_texts`` holds the (possibly edited) page text."""
    lines = [f"Document: {document.name}"]
    if document.error:
        lines.append(f"Extraction failed: {document.error}")
        return "\n".join(lines)

    analysis = document.analysis
    if analysis:
        lines += ["", "=== AI analysis ===", f"Type: {analysis.document_type}"]
        if analysis.title:
            lines.append(f"Title: {analysis.title}")
        lines += ["", "Summary:", analysis.summary]
        if analysis.key_fields:
            lines += ["", "Key fields:"]
            for item in analysis.key_fields:
                status = "" if item.verified else "  [NOT FOUND IN TEXT - verify]"
                lines.append(f"- {item.label}: {item.value}{status}")
        if analysis.issues:
            lines += ["", "Notes:"] + [f"- {issue}" for issue in analysis.issues]

    lines += ["", "=== Extracted text ==="]
    for page in document.pages:
        label = page.method
        if page.confidence is not None:
            label += f", confidence {page.confidence:.0f}%"
        lines += ["", f"--- Page {page.page} ({label}) ---", page_texts.get(page.page, page.text)]
    return "\n".join(lines).strip() + "\n"


def document_to_dict(document: ProcessedDocument, page_texts: dict[int, str]) -> dict:
    return {
        "name": document.name,
        "sha256": document.file_hash,
        "error": document.error,
        "ocr_confidence": document.confidence,
        "pages": [
            {
                "page": page.page,
                "method": page.method,
                "confidence": page.confidence,
                "word_count": page.word_count,
                "low_confidence_words": page.low_confidence_words,
                "processing": page.notes,
                "text": page_texts.get(page.page, page.text),
            }
            for page in document.pages
        ],
        "analysis": asdict(document.analysis) if document.analysis else None,
        "analysis_error": document.analysis_error,
    }


def documents_to_json(items: list[tuple[ProcessedDocument, dict[int, str]]]) -> str:
    return json.dumps(
        [document_to_dict(document, texts) for document, texts in items],
        ensure_ascii=False,
        indent=2,
    )
