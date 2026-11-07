"""Results view: metrics, per-document tabs, review highlighting and downloads."""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from docudude.analysis import MAX_SUMMARY_CHARACTERS
from docudude.document import (
    ProcessedDocument,
    confidence_band,
    document_to_text,
    documents_to_json,
)
from docudude.ocr import LOW_CONFIDENCE, PageResult

VERY_LOW_CONFIDENCE = 40.0


def _text_key(workflow: str, document: ProcessedDocument, index: int, page: int) -> str:
    return f"{workflow}_text_{document.run_id}_{index}_{page}"


def _page_texts(workflow: str, document: ProcessedDocument, index: int) -> dict[int, str]:
    """Current (possibly user-edited) text for each page."""
    return {
        page.page: st.session_state.get(_text_key(workflow, document, index, page.page), page.text)
        for page in document.pages
    }


def _highlighted_html(page: PageResult) -> str:
    if not page.lines:  # digital text has no per-word confidence
        return escape(page.text)
    rendered_lines = []
    for line in page.lines:
        words = []
        for word, confidence in line:
            safe = escape(word)
            if confidence < VERY_LOW_CONFIDENCE:
                words.append(f'<mark class="very-low" title="{confidence:.0f}%">{safe}</mark>')
            elif confidence < LOW_CONFIDENCE:
                words.append(f'<mark class="low" title="{confidence:.0f}%">{safe}</mark>')
            else:
                words.append(safe)
        rendered_lines.append(" ".join(words))
    return "\n".join(rendered_lines)


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
def _render_text_tab(workflow: str, document: ProcessedDocument, index: int) -> None:
    multi_page = len(document.pages) > 1
    show_preview = st.toggle(
        "Show original next to text",
        value=True,
        key=f"{workflow}_preview_{document.run_id}_{index}",
    )
    for page in document.pages:
        band, _ = confidence_band(page.confidence)
        container = (
            st.expander(f"Page {page.page} · {page.method} · {band}", expanded=page.page == 1)
            if multi_page
            else st.container()
        )
        with container:
            if show_preview and page.preview:
                image_col, text_col = st.columns(2, gap="medium")
                image_col.image(page.preview, width="stretch")
            else:
                text_col = st.container()
            text_col.text_area(
                f"Extracted text, page {page.page}",
                value=page.text,
                height=520 if show_preview and page.preview else 360,
                key=_text_key(workflow, document, index, page.page),
                label_visibility="collapsed",
                placeholder="No text was found on this page.",
            )
    st.caption("You can edit the text; downloads include your edits.")


def _render_review_tab(document: ProcessedDocument) -> None:
    uncertain = sum(page.low_confidence_words for page in document.pages)
    if not any(page.lines for page in document.pages):
        st.info("This document used embedded digital text, so there is nothing to review.")
        return
    if uncertain:
        st.markdown(
            f"**{uncertain} word(s)** were read with low confidence. "
            '<mark style="background:#ffd8a8;padding:0 3px;border-radius:3px">orange</mark> '
            f"= below {LOW_CONFIDENCE:.0f}%, "
            '<mark style="background:#ffb3b0;padding:0 3px;border-radius:3px">red</mark> '
            f"= below {VERY_LOW_CONFIDENCE:.0f}%. Hover a word to see its score, then "
            "compare it with the original and correct it in the Text tab.",
            unsafe_allow_html=True,
        )
    else:
        st.success("Every word was read with good confidence.", icon="✅")

    parts = []
    for page in document.pages:
        if len(document.pages) > 1:
            parts.append(f'<span class="page-sep">— Page {page.page} —</span>')
        parts.append(_highlighted_html(page))
    st.markdown(f'<div class="review-text">{"".join(parts)}</div>', unsafe_allow_html=True)


def _render_analysis_tab(document: ProcessedDocument) -> None:
    if document.analysis_error:
        st.error(f"AI analysis failed: {document.analysis_error}", icon="⚠️")
        return
    analysis = document.analysis
    if analysis is None:
        st.info("AI analysis was not run for this document.")
        return

    type_col, title_col = st.columns([1, 2])
    type_col.markdown(f"**Document type**  \n{escape(analysis.document_type)}")
    if analysis.title:
        title_col.markdown(f"**Title**  \n{escape(analysis.title)}")

    st.markdown("**Summary**")
    st.markdown(f'<div class="summary-box">{escape(analysis.summary)}</div>', unsafe_allow_html=True)
    st.caption(f"{len(analysis.summary)}/{MAX_SUMMARY_CHARACTERS} characters")
    if analysis.unverified_numbers:
        st.warning(
            "These numbers in the summary do not appear in the extracted text, so "
            f"check them: {', '.join(analysis.unverified_numbers)}",
            icon="🔎",
        )

    if analysis.key_fields:
        total = len(analysis.key_fields)
        st.markdown(f"**Key fields** · {analysis.verified_count} of {total} found in the text")
        st.dataframe(
            [
                {
                    "Status": "✅ Found" if item.verified else "⚠️ Check",
                    "Field": item.label,
                    "Value": item.value,
                    "Source line": item.source_text,
                }
                for item in analysis.key_fields
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "Status": st.column_config.TextColumn(width="small"),
                "Field": st.column_config.TextColumn(width="medium"),
                "Value": st.column_config.TextColumn(width="medium"),
                "Source line": st.column_config.TextColumn(width="large"),
            },
        )
        if analysis.verified_count < total:
            st.caption(
                "⚠️ Check = the value could not be found word-for-word in the "
                "extracted text. It may be reformatted or wrong; verify it against "
                "the original."
            )

    if analysis.issues:
        st.markdown("**Reliability notes**")
        st.markdown("\n".join(f"- {escape(issue)}" for issue in analysis.issues))

    details = [f"Model: {analysis.model}"]
    if analysis.sections_analysed > 1:
        details.append(f"analysed in {analysis.sections_analysed} sections")
    if analysis.truncated:
        details.append("very long document: only the first part was analysed")
    st.caption(
        " · ".join(details)
        + ". AI output can be wrong; verify important names, dates and amounts."
    )


def _render_details_tab(document: ProcessedDocument) -> None:
    st.dataframe(
        [
            {
                "Page": page.page,
                "Method": page.method,
                "Confidence": f"{page.confidence:.1f}%" if page.confidence is not None else "—",
                "Words": page.word_count,
                "Uncertain words": page.low_confidence_words if page.lines else "—",
                "Processing": "; ".join(page.notes) or "—",
            }
            for page in document.pages
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Confidence is Tesseract's own estimate, weighted by word length. It is a "
        "guide, not a guarantee that the text is correct."
    )


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def _render_document(workflow: str, document: ProcessedDocument, index: int) -> None:
    with st.container(border=True):
        badges = []
        if not document.error:
            label, css = confidence_band(document.confidence)
            badges.append(f'<span class="badge {css}">{label}</span>')
            badges.append(
                f'<span class="badge badge-neutral">{len(document.pages)} page(s) · '
                f"{document.word_count:,} words</span>"
            )
            if document.analysis:
                badges.append(
                    f'<span class="badge badge-neutral">'
                    f"{escape(document.analysis.document_type)}</span>"
                )
        st.markdown(
            f'<div class="doc-head"><span class="doc-name">📄 {escape(document.name)}'
            f'</span>{"".join(badges)}</div>',
            unsafe_allow_html=True,
        )

        if document.error:
            st.error(f"Could not process this file: {document.error}")
            return

        tab_names = ["📄 Text", "🔍 Review", "ℹ️ Details"]
        if workflow == "analyze":
            tab_names.insert(0, "✨ AI analysis")
        tabs = dict(zip(tab_names, st.tabs(tab_names)))
        if "✨ AI analysis" in tabs:
            with tabs["✨ AI analysis"]:
                _render_analysis_tab(document)
        with tabs["📄 Text"]:
            _render_text_tab(workflow, document, index)
        with tabs["🔍 Review"]:
            _render_review_tab(document)
        with tabs["ℹ️ Details"]:
            _render_details_tab(document)

        texts = _page_texts(workflow, document, index)
        stem = Path(document.name).stem
        txt_col, json_col, _ = st.columns([1, 1, 3])
        txt_col.download_button(
            "⬇ TXT",
            data=document_to_text(document, texts),
            file_name=f"{stem}.txt",
            mime="text/plain",
            width="stretch",
            key=f"{workflow}_txt_{document.run_id}_{index}",
        )
        json_col.download_button(
            "⬇ JSON",
            data=documents_to_json([(document, texts)]),
            file_name=f"{stem}.json",
            mime="application/json",
            width="stretch",
            key=f"{workflow}_json_{document.run_id}_{index}",
        )


def render_results(workflow: str, documents: list[ProcessedDocument]) -> None:
    st.markdown('<div class="section-title">Results</div>', unsafe_allow_html=True)

    ok_documents = [document for document in documents if not document.error]
    pages = [page for document in ok_documents for page in document.pages]
    ocr_pages = [page for page in pages if page.confidence is not None and page.word_count]
    words = sum(page.word_count for page in ocr_pages)
    average = (
        sum(page.confidence * page.word_count for page in ocr_pages) / words if words else None
    )
    metrics = st.columns(5)
    metrics[0].metric("Documents", len(documents))
    metrics[1].metric("Pages", len(pages))
    metrics[2].metric("Words", f"{sum(page.word_count for page in pages):,}")
    metrics[3].metric(
        "OCR confidence",
        f"{average:.1f}%" if average is not None else "N/A",
        help="Tesseract's estimate across OCR pages, weighted by word count.",
    )
    metrics[4].metric(
        "Words to review",
        f"{sum(page.low_confidence_words for page in pages):,}",
        help=f"Words read with less than {LOW_CONFIDENCE:.0f}% confidence.",
    )

    for index, document in enumerate(documents):
        _render_document(workflow, document, index)

    if len(documents) > 1:
        all_texts = [(document, _page_texts(workflow, document, index))
                     for index, document in enumerate(documents)]
        txt_col, json_col = st.columns(2)
        txt_col.download_button(
            "⬇ Download all as TXT",
            data="\n\n".join(document_to_text(doc, texts) for doc, texts in all_texts),
            file_name="docudude_results.txt",
            mime="text/plain",
            width="stretch",
            key=f"{workflow}_all_txt",
        )
        json_col.download_button(
            "⬇ Download all as JSON",
            data=documents_to_json(all_texts),
            file_name="docudude_results.json",
            mime="application/json",
            width="stretch",
            key=f"{workflow}_all_json",
        )
