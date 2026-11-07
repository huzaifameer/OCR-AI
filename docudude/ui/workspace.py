"""The upload → settings → run workspace shared by both workflows."""

from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st

from docudude.analysis import analyze_document
from docudude.config import (
    ACCURACY_MODE_HELP,
    ACCURACY_MODE_LABELS,
    DEFAULT_MODEL,
    OLLAMA_CLOUD_MODELS,
    PAGE_SEGMENTATION_MODES,
    SUPPORTED_TYPES,
    get_setting,
)
from docudude.ocr import (
    OcrSettings,
    PageResult,
    available_languages,
    extract_image,
    extract_pdf,
    tesseract_status,
)
from docudude.document import ProcessedDocument
from docudude.ui.layout import render_page_header, render_privacy_notice, section_label
from docudude.ui.results import render_results


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def _state_key(workflow: str, name: str) -> str:
    return f"{workflow}_{name}"


def init_workflow_state(workflow: str) -> None:
    defaults: dict[str, Any] = {
        "uploader_generation": 0,
        "signature": None,
        "documents": [],
    }
    for name, value in defaults.items():
        st.session_state.setdefault(_state_key(workflow, name), value)


def clear_workflow(workflow: str) -> None:
    st.session_state[_state_key(workflow, "documents")] = []
    st.session_state[_state_key(workflow, "signature")] = None
    st.session_state[_state_key(workflow, "uploader_generation")] += 1


# --------------------------------------------------------------------------
# Processing (cached so re-running with the same file and settings is instant)
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=32)
def _extract_cached(
    file_bytes: bytes,
    file_name: str,
    settings: OcrSettings,
    _progress: Any = None,
) -> list[PageResult]:
    if file_name.lower().endswith(".pdf"):
        return extract_pdf(file_bytes, settings, _progress)
    return extract_image(file_bytes, settings, _progress)


def process_files(
    uploaded_files: list[Any],
    settings: OcrSettings,
    *,
    analyze: bool,
    api_key: str,
    model: str,
) -> list[ProcessedDocument]:
    documents: list[ProcessedDocument] = []
    count = len(uploaded_files)
    progress = st.progress(0.0, text="Starting…")
    stage_weight = 0.75 if analyze else 1.0

    for index, uploaded in enumerate(uploaded_files):
        file_bytes = uploaded.getvalue()
        document = ProcessedDocument(
            name=uploaded.name, file_hash=hashlib.sha256(file_bytes).hexdigest()
        )

        def on_page(done: int, total: int, index: int = index, name: str = uploaded.name) -> None:
            fraction = (index + stage_weight * done / max(total, 1)) / count
            progress.progress(
                min(fraction, 1.0), text=f"Reading {name} · page {done} of {total}"
            )

        progress.progress(index / count, text=f"Reading {uploaded.name}…")
        try:
            document.pages = _extract_cached(file_bytes, uploaded.name, settings, on_page)
        except Exception as error:  # noqa: BLE001 - shown to the user
            document.error = str(error)
            documents.append(document)
            continue

        if analyze:
            progress.progress(
                (index + stage_weight) / count, text=f"Analysing {uploaded.name} with AI…"
            )
            try:
                document.analysis = analyze_document(
                    api_key=api_key,
                    model=model,
                    pages=[(page.page, page.text) for page in document.pages],
                    ocr_confidence=document.confidence,
                )
            except Exception as error:  # noqa: BLE001
                document.analysis_error = str(error)

        documents.append(document)

    progress.progress(1.0, text=f"Done · {count} file(s) processed")
    return documents


# --------------------------------------------------------------------------
# Settings panel
# --------------------------------------------------------------------------
def render_settings(workflow: str) -> OcrSettings:
    languages = available_languages()
    default_language = "eng" if "eng" in languages else languages[0]

    accuracy = st.segmented_control(
        "Accuracy mode",
        options=list(ACCURACY_MODE_LABELS),
        format_func=ACCURACY_MODE_LABELS.get,
        default="balanced",
        key=f"{workflow}_accuracy",
        help=ACCURACY_MODE_HELP,
        width="stretch",
    ) or "balanced"

    layout_label = st.selectbox(
        "Page layout",
        options=list(PAGE_SEGMENTATION_MODES),
        key=f"{workflow}_layout",
        help="How text is arranged on the page. Automatic suits most documents; "
        "use Sparse text for receipts, forms and labels.",
    )
    selected_languages = st.multiselect(
        "Document language(s)",
        options=languages,
        default=[default_language],
        key=f"{workflow}_languages",
        help="Only installed Tesseract languages are listed. Pick every language "
        "that appears in the document.",
    )

    with st.expander("Advanced options"):
        enhance = st.toggle(
            "Clean up images before OCR",
            value=True,
            key=f"{workflow}_enhance",
            help="Fixes inverted colours, text size, shadows and uneven lighting.",
        )
        auto_rotate = st.toggle(
            "Auto-rotate sideways/upside-down pages",
            value=True,
            key=f"{workflow}_rotate",
            disabled=not enhance,
        )
        deskew = st.toggle(
            "Straighten tilted scans",
            value=True,
            key=f"{workflow}_deskew",
            disabled=not enhance,
        )
        preserve_layout = st.toggle(
            "Keep column spacing (tables, invoices)",
            value=True,
            key=f"{workflow}_spacing",
            help="Keeps wide gaps between words so table columns stay aligned.",
        )
        ocr_pdf = st.toggle(
            "OCR scanned PDF pages",
            value=True,
            key=f"{workflow}_ocr_pdf",
            help="If off, PDFs use only their embedded digital text.",
        )
        force_ocr = st.toggle(
            "Always OCR PDF pages (ignore embedded text)",
            value=False,
            key=f"{workflow}_force_ocr",
            disabled=not ocr_pdf,
            help="Use when a PDF's embedded text is wrong or incomplete.",
        )
        dpi = st.select_slider(
            "PDF render resolution (DPI)",
            options=[200, 250, 300, 350, 400],
            value=300,
            key=f"{workflow}_dpi",
            help="Higher values help very small print but take longer.",
        )

    return OcrSettings(
        language="+".join(selected_languages or [default_language]),
        page_segmentation_mode=PAGE_SEGMENTATION_MODES[layout_label],
        accuracy_mode=accuracy,
        dpi=dpi,
        enhance=enhance,
        auto_rotate=auto_rotate and enhance,
        deskew=deskew and enhance,
        preserve_layout=preserve_layout,
        ocr_pdf_pages=ocr_pdf,
        force_ocr=force_ocr and ocr_pdf,
    )


def _render_ai_settings() -> tuple[str, str, bool]:
    api_key = get_setting("OLLAMA_API_KEY")
    configured_model = get_setting("OLLAMA_MODEL", DEFAULT_MODEL)
    models = list(OLLAMA_CLOUD_MODELS)
    if configured_model and configured_model not in models:
        models.insert(0, configured_model)

    model = st.selectbox(
        "AI model",
        options=models,
        index=models.index(configured_model) if configured_model in models else 0,
        key="analyze_model",
        help="Larger models are generally more accurate but slower.",
    )
    if not api_key:
        st.warning(
            "AI analysis is not configured. Add OLLAMA_API_KEY to the .env file "
            "or Streamlit secrets.",
            icon="🔑",
        )
    consent = st.checkbox(
        "I agree to send the extracted text to Ollama Cloud for analysis.",
        value=False,
        key="analysis_consent",
        help="The original file is never sent, only the extracted text.",
    )
    return api_key, model, consent


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
def render_workspace(workflow: str) -> None:
    init_workflow_state(workflow)
    analyze = workflow == "analyze"

    if analyze:
        render_page_header(
            "AI analysis",
            "Extract, verify and summarise",
            "Extract the text, then let AI identify the document type, write a "
            "short summary and pull out key fields. Every field is checked "
            "against the extracted text.",
        )
    else:
        render_page_header(
            "Text extraction",
            "Turn images and PDFs into editable text",
            "Text is read on this server with Tesseract OCR. Nothing is sent to "
            "an AI service on this page.",
        )

    ok, version = tesseract_status()
    if not ok:
        st.error(
            "Tesseract OCR is not installed or could not be found. Install it and, "
            "if needed, set the TESSERACT_CMD environment variable to the "
            f"tesseract executable. Details: {version}",
            icon="⚠️",
        )

    upload_col, settings_col = st.columns([3, 2], gap="medium")
    with upload_col, st.container(border=True):
        section_label(1, "Upload documents")
        uploader_key = (
            f"{workflow}_uploader_"
            f"{st.session_state[_state_key(workflow, 'uploader_generation')]}"
        )
        uploaded_files = st.file_uploader(
            "Choose image or PDF files",
            type=SUPPORTED_TYPES,
            accept_multiple_files=True,
            key=uploader_key,
            label_visibility="collapsed",
        ) or []
        if uploaded_files:
            total_kb = sum(file.size for file in uploaded_files) / 1024
            st.caption(f"{len(uploaded_files)} file(s) selected · {total_kb:,.0f} KB")
        else:
            st.caption("PDF, PNG, JPG, TIFF, BMP or WEBP · multiple files allowed")
        st.markdown(
            "**Tips for the best results**\n"
            "- Scan at 300 DPI, or photograph the page flat, in even light, filling the frame.\n"
            "- Choose *Sparse text* layout for receipts, forms and labels.\n"
            "- Use *Best* accuracy for faded, noisy or low-resolution pages.\n"
            "- Select every language that appears in the document."
        )

    with settings_col, st.container(border=True):
        section_label(2, "Settings")
        settings = render_settings(workflow)
        api_key, model, consent = ("", "", False)
        if analyze:
            st.divider()
            api_key, model, consent = _render_ai_settings()

    # Results are cleared when the files or settings change.
    signature = (
        tuple((file.name, file.file_id) for file in uploaded_files),
        settings,
        model if analyze else "",
    )
    documents_key = _state_key(workflow, "documents")
    if signature != st.session_state[_state_key(workflow, "signature")]:
        st.session_state[documents_key] = []
        st.session_state[_state_key(workflow, "signature")] = signature

    can_run = bool(uploaded_files) and ok and (not analyze or (consent and api_key))
    run_col, clear_col, hint_col = st.columns([2, 1, 4], vertical_alignment="center")
    run_clicked = run_col.button(
        "✨ Extract and analyze" if analyze else "📝 Extract text",
        type="primary",
        width="stretch",
        disabled=not can_run,
        key=f"{workflow}_run",
    )
    clear_col.button(
        "Clear",
        width="stretch",
        disabled=not uploaded_files and not st.session_state[documents_key],
        on_click=clear_workflow,
        args=(workflow,),
        key=f"{workflow}_clear",
    )
    if not uploaded_files:
        hint_col.caption("Upload at least one file to start.")
    elif analyze and not consent:
        hint_col.caption("Tick the consent box to enable AI analysis.")

    if run_clicked:
        st.session_state[documents_key] = process_files(
            uploaded_files, settings, analyze=analyze, api_key=api_key, model=model
        )

    documents = st.session_state[documents_key]
    if documents:
        render_results(workflow, documents)

    if analyze:
        render_privacy_notice()
