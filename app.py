import datetime
import hashlib
import os
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

from document_processing import extract_image, extract_pdf
from ollama_enrichment import (
    MAX_DESCRIPTION_CHARACTERS,
    generate_document_insights,
)


load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)

WHATSAPP_URL = "https://wa.me/94774322192"
APP_NAME = "DocuDude"
APP_LOGO_PATH = Path(__file__).resolve().with_name(
    "DocuDude_ Your Friendly Scan Sidekick.png"
)
SUPPORTED_IMAGES = ["png", "jpg", "jpeg", "tiff", "bmp"]
OLLAMA_CLOUD_MODELS = [
    "beam",
    "gemma4:31b",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "nemotron-3-nano:30b",
    "nemotron-3-super",
    "nemotron-3-ultra",
]
PAGE_SEGMENTATION_MODES = {
    "Automatic page layout": 3,
    "Single block of text": 6,
    "Sparse or scattered text": 11,
}
WORKFLOWS = ("extract", "analyze")
APP_PAGES = ["Home", "Text extraction", "AI analysis"]


# --------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------
PAGE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --ink: #14283a;
  --muted: #566a7b;
  --line: #e2e9ee;
  --brand: #0f766e;
  --brand-dark: #0b5c56;
  --surface: #ffffff;
  --page: #f6f8fa;
}

html, body, .stApp, [class*="css"] {
  font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}
html, body { overflow-x: hidden; }
.stApp { background: var(--page); color: var(--ink); overflow-x: hidden; }
* { box-sizing: border-box; }

/* Hide Streamlit chrome so the app reads as a normal website */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stHeader"], [data-testid="stSidebar"],
[data-testid="collapsedControl"] { display: none !important; }

/* One centred column; every section lives inside it (no full-bleed tricks) */
.block-container {
  max-width: 1120px;
  width: 100%;
  margin: 0 auto;
  padding: 0 1.25rem 5rem !important;
}

/* ---------- Top navigation bar ---------- */
.st-key-navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(246,248,250,.96); backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  padding: .5rem 0;
  margin-bottom: .5rem;
}
.st-key-navbar [data-testid="stHorizontalBlock"] {
  align-items: center; flex-wrap: nowrap !important; gap: .5rem;
}
.st-key-navbar [data-testid="stColumn"] { min-width: 0 !important; }
.brand-logo { width: 76px; height: 76px; object-fit: contain; flex: none; }

.st-key-nav_home button,
.st-key-nav_text_extraction button,
.st-key-nav_ai_analysis button {
  width: 100%; min-height: 40px; padding: .45rem .6rem; border-radius: 9px;
  white-space: nowrap; font-weight: 650;
  transition: background .15s ease, border-color .15s ease, color .15s ease;
}
.st-key-nav_home button:not([kind="primary"]),
.st-key-nav_text_extraction button:not([kind="primary"]),
.st-key-nav_ai_analysis button:not([kind="primary"]) {
  color: var(--muted); background: transparent; border-color: transparent;
}
.st-key-nav_home button:not([kind="primary"]):hover,
.st-key-nav_text_extraction button:not([kind="primary"]):hover,
.st-key-nav_ai_analysis button:not([kind="primary"]):hover {
  color: var(--brand-dark); background: #eaf2f1; border-color: #d5e8e5;
}

/* ---------- Hero / headings ---------- */
.hero { padding: 3.6rem 0 2.2rem; max-width: 760px; }
.hero-kicker { margin: 0 0 .7rem; color: var(--brand); font-size: .78rem;
               font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.hero h1 { font-size: 3rem; line-height: 1.1; font-weight: 800; letter-spacing: -.025em;
           color: var(--ink); margin: 0 0 1rem; }
.hero p { font-size: 1.15rem; line-height: 1.65; color: var(--muted); margin: 0; max-width: 620px; }
.page-head { padding: 2rem 0 1.2rem; }
.page-head h2 { font-size: 2rem; font-weight: 800; letter-spacing: -.02em; margin: 0 0 .4rem; color: var(--ink); }
.page-head p { margin: 0; color: var(--muted); font-size: 1.02rem; max-width: 640px; line-height: 1.6; }

/* ---------- Cards / widgets ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 12px; border-color: var(--line); background: var(--surface);
  box-shadow: 0 1px 2px rgba(20,40,58,.04);
}
[data-testid="stMetric"] {
  background: var(--surface); padding: .9rem 1.1rem;
  border: 1px solid var(--line); border-radius: 12px;
}
[data-testid="stMetricLabel"] p { color: var(--muted); font-size: .85rem; }
[data-testid="stFileUploader"] section {
  background: var(--surface); border: 1.5px dashed #9bb7bf; border-radius: 12px; padding: 1.2rem;
}
[data-testid="stExpander"] { border-radius: 12px; border-color: var(--line); background: var(--surface); }
.stButton > button, .stDownloadButton > button { border-radius: 8px; font-weight: 600; padding: .55rem 1rem; }
.stButton > button[kind="primary"] { background: var(--brand); border-color: var(--brand); }
.stButton > button[kind="primary"]:hover { background: var(--brand-dark); border-color: var(--brand-dark); }

.section-title { font-size: 1.5rem; font-weight: 800; letter-spacing: -.015em; margin: 2.6rem 0 1rem; }
.step { background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
        padding: 1.2rem 1.3rem; height: 100%; }
.step h4 { margin: 0 0 .35rem; font-size: 1.02rem; color: var(--ink); }
.step p { margin: 0; color: var(--muted); font-size: .94rem; line-height: 1.55; }
.step-num { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%;
            background: #e3f3f1; color: var(--brand-dark); font-weight: 700; font-size: .85rem; margin-bottom: .7rem; }
.notice { margin-top: 2.6rem; padding: 1.3rem 1.5rem; border-radius: 12px;
          background: #eaf4f3; border: 1px solid #cfe5e2; color: #25494a; line-height: 1.6; font-size: .95rem; }
.notice a { color: var(--brand-dark); font-weight: 700; text-decoration: none; }
.notice a:hover { text-decoration: underline; }

/* ---------- Footer ---------- */
.st-key-site_footer {
  margin-top: 4rem; padding: 2.2rem 2rem 1.2rem;
  background: var(--ink); border-radius: 16px; color: #c4d2dd;
}
.st-key-site_footer p, .st-key-site_footer li, .st-key-site_footer span { color: #c4d2dd; font-size: .92rem; }
.st-key-site_footer .footer-brand { color: #fff; font-weight: 800; font-size: 1.1rem; margin-bottom: .5rem; }
.st-key-site_footer .footer-heading { color: #fff; font-weight: 700; font-size: .95rem; margin-bottom: .6rem; }
.st-key-site_footer .footer-text { line-height: 1.6; margin: 0; }
.st-key-site_footer ul { list-style: none; margin: 0; padding: 0; }
.st-key-site_footer li { margin: 0 0 .35rem; }
.st-key-site_footer a { color: #8ee0d6; text-decoration: none; font-weight: 600; }
.st-key-site_footer a:hover { text-decoration: underline; }
.st-key-site_footer button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: #c4d2dd !important; padding: .15rem 0 !important; min-height: 0 !important;
  justify-content: flex-start; width: auto;
}
.st-key-site_footer button p { color: inherit !important; font-weight: 500; }
.st-key-site_footer button:hover p { color: #8ee0d6 !important; text-decoration: underline; }
.footer-bottom {
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: .5rem;
  margin-top: 1.4rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.14);
  font-size: .85rem; color: #98aab8;
}
.footer-bottom span { color: #98aab8 !important; font-size: .85rem !important; }

.whatsapp-float {
  position: fixed; right: 22px; bottom: 22px; z-index: 1000; display: inline-flex; align-items: center;
  height: 52px; min-width: 52px; padding: 0 14px; border-radius: 26px; background: #20a86b; color: #fff !important;
  text-decoration: none !important; font-weight: 700; box-shadow: 0 8px 24px rgba(18,101,68,.3);
  transition: background .18s ease, gap .18s ease; gap: 0;
}
.whatsapp-float:hover { background: #168653; gap: 8px; }
.whatsapp-icon { font-size: 1.4rem; line-height: 1; }
.whatsapp-label { max-width: 0; overflow: hidden; white-space: nowrap; opacity: 0;
                  transition: max-width .2s ease, opacity .15s ease; }
.whatsapp-float:hover .whatsapp-label { max-width: 180px; opacity: 1; }

@media (max-width: 760px) {
  .block-container { padding-left: .9rem !important; padding-right: .9rem !important; }
  .hero { padding: 2rem 0 1.4rem; }
  .hero h1 { font-size: 2.1rem; }
  .page-head h2 { font-size: 1.6rem; }
  .brand-logo { width: 60px; height: 60px; }
  .st-key-nav_home button,
  .st-key-nav_text_extraction button,
  .st-key-nav_ai_analysis button { padding: .4rem .2rem; font-size: .72rem; min-height: 36px; }
  .st-key-site_footer { padding: 1.5rem 1.2rem 1rem; }
  .whatsapp-float { right: 14px; bottom: 14px; }
}
</style>
"""


# --------------------------------------------------------------------------
# State / helpers
# --------------------------------------------------------------------------
def initialize_state() -> None:
    if "navigation" not in st.session_state:
        st.session_state["navigation"] = "Home"
    for workflow in WORKFLOWS:
        defaults: dict[str, Any] = {
            f"{workflow}_uploader_generation": 0,
            f"{workflow}_active_signature": None,
            f"{workflow}_documents": [],
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value


def navigate_to(page: str) -> None:
    st.session_state["navigation"] = page


def clear_workflow(workflow: str) -> None:
    st.session_state[f"{workflow}_documents"] = []
    st.session_state[f"{workflow}_active_signature"] = None
    st.session_state[f"{workflow}_uploader_generation"] += 1


def get_ollama_setting(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except StreamlitSecretNotFoundError:
        return default


def get_upload_signature(uploaded_files: list[Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            uploaded_file.name,
            hashlib.sha256(uploaded_file.getvalue()).hexdigest(),
        )
        for uploaded_file in uploaded_files
    )


def build_document_text(document: dict[str, Any]) -> str:
    if document["error"]:
        return (
            f"--- {document['name']} ---\n"
            f"Extraction failed: {document['error']}"
        )

    pages = "\n\n".join(
        f"--- Page {page['page']} ({page['method']}) ---\n{page['text']}"
        for page in document["pages"]
    )
    sections = [f"Document: {document['name']}", pages]
    insights = document.get("ai_insights")
    if insights:
        sections.append(
            "AI description "
            f"({len(insights['description'])}/{MAX_DESCRIPTION_CHARACTERS} "
            "characters):\n"
            f"{insights['description']}"
        )
    return "\n\n".join(section for section in sections if section)


def build_download_text(documents: list[dict[str, Any]]) -> str:
    return "\n\n".join(build_document_text(document) for document in documents)


# --------------------------------------------------------------------------
# Processing (unchanged logic)
# --------------------------------------------------------------------------
def extract_uploaded_documents(
    uploaded_files: list[Any],
    *,
    use_ocr: bool,
    language: str,
    page_segmentation_mode: int,
    dpi: int,
    improve_quality: bool,
    analyze_with_ai: bool,
    api_key: str,
    model_name: str,
    progress: Any,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    file_count = len(uploaded_files)

    for index, uploaded_file in enumerate(uploaded_files, start=1):
        progress.progress(
            (index - 1) / file_count,
            text=f"Reading {uploaded_file.name} ({index}/{file_count})",
        )
        try:
            file_bytes = uploaded_file.getvalue()
            extension = uploaded_file.name.lower().rsplit(".", 1)[-1]
            if extension == "pdf":

                def update_page_progress(page_number: int, page_count: int) -> None:
                    overall_progress = (
                        index - 1 + page_number / page_count
                    ) / file_count
                    progress.progress(
                        overall_progress,
                        text=(
                            f"Reading {uploaded_file.name}: "
                            f"page {page_number}/{page_count}"
                        ),
                    )

                pages = extract_pdf(
                    file_bytes,
                    use_ocr=use_ocr,
                    language=language,
                    page_segmentation_mode=page_segmentation_mode,
                    dpi=dpi,
                    improve_quality=improve_quality,
                    progress_callback=update_page_progress,
                )
            else:
                pages = extract_image(
                    file_bytes,
                    language=language,
                    page_segmentation_mode=page_segmentation_mode,
                    improve_quality=improve_quality,
                )
        except Exception as error:
            documents.append({
                "name": uploaded_file.name,
                "pages": [],
                "error": str(error),
                "ai_error": None,
                "ai_insights": None,
                "analysis_note": "",
            })
            continue

        document: dict[str, Any] = {
            "name": uploaded_file.name,
            "pages": pages,
            "error": None,
            "ai_error": None,
            "ai_insights": None,
            "analysis_note": "",
        }
        if analyze_with_ai:
            ocr_text = "\n\n".join(
                f"Page {page['page']}:\n{page['text']}"
                for page in pages
            )
            if not api_key:
                document["ai_error"] = (
                    "Ollama API key is missing. Add OLLAMA_API_KEY to .env "
                    "and restart the app."
                )
            elif not ocr_text.strip():
                document["ai_error"] = (
                    "No text was extracted, so the model cannot describe "
                    "this document."
                )
            else:
                if len(ocr_text) > 60000:
                    document["analysis_note"] = (
                        "AI analysis used the first 60,000 OCR characters. "
                        "The full extracted text is still available."
                    )
                progress.progress(
                    (index - 1 + 0.9) / file_count,
                    text=f"Analyzing extracted text with {model_name}",
                )
                try:
                    document["ai_insights"] = generate_document_insights(
                        api_key=api_key,
                        model=model_name,
                        ocr_text=ocr_text,
                    )
                except Exception as error:
                    document["ai_error"] = str(error)

        documents.append(document)
        progress.progress(
            index / file_count,
            text=f"Finished {uploaded_file.name} ({index}/{file_count})",
        )

    return documents


# --------------------------------------------------------------------------
# Layout pieces
# --------------------------------------------------------------------------
def render_navbar() -> str:
    current_page = st.session_state["navigation"]
    with st.container(key="navbar"):
        brand_col, nav_col = st.columns([1, 7], vertical_alignment="center")
        brand_col.image(str(APP_LOGO_PATH), width=76)
        with nav_col:
            for column, page in zip(st.columns(3, gap="small"), APP_PAGES):
                column.button(
                    page,
                    type="primary" if page == current_page else "secondary",
                    use_container_width=True,
                    key=f"nav_{page.lower().replace(' ', '_')}",
                    on_click=navigate_to,
                    args=(page,),
                )
    return st.session_state["navigation"]


def render_footer() -> None:
    year = datetime.date.today().year
    with st.container(key="site_footer"):
        about, pages, formats, contact = st.columns([3, 2, 2, 3], gap="large")

        about.markdown(
            f'<div class="footer-brand">{APP_NAME}</div>'
            '<p class="footer-text">Extract English text from images and PDFs. '
            "OCR runs locally, and AI summaries are optional.</p>",
            unsafe_allow_html=True,
        )

        with pages:
            st.markdown('<div class="footer-heading">Pages</div>', unsafe_allow_html=True)
            for page in APP_PAGES:
                st.button(
                    page,
                    key=f"footer_{page.lower().replace(' ', '_')}",
                    on_click=navigate_to,
                    args=(page,),
                )

        formats.markdown(
            '<div class="footer-heading">Supported files</div>'
            "<ul><li>PDF (text and scanned)</li><li>PNG, JPG, JPEG</li>"
            "<li>TIFF, BMP</li></ul>",
            unsafe_allow_html=True,
        )

        contact.markdown(
            '<div class="footer-heading">Contact</div>'
            '<p class="footer-text">Questions or feedback?<br>'
            f'<a href="{WHATSAPP_URL}" target="_blank" rel="noopener noreferrer">'
            "WhatsApp +94 77 432 2192</a></p>"
            '<p class="footer-text">AI analysis sends text to Ollama Cloud only '
            "after you give consent.</p>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="footer-bottom"><span>© {year} {APP_NAME}. '
            "All rights reserved.</span><span>Developed by Huzaifa Ameer</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <a class="whatsapp-float" href="{WHATSAPP_URL}" target="_blank"
           rel="noopener noreferrer" aria-label="Contact Huzaifa Ameer on WhatsApp"
           title="WhatsApp Huzaifa Ameer: +94 77 432 2192">
          <span class="whatsapp-icon">💬</span>
          <span class="whatsapp-label">Chat with Huzaifa</span>
        </a>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    st.markdown(
        """
        <section class="hero">
          <div class="hero-kicker">DocuDude · Your document OCR tool</div>
          <h1>Turn images and PDFs into text you can use.</h1>
          <p>Upload a scan, photo, or PDF and get editable English text in seconds.
          Add an AI summary when you want a quick overview of what the document says.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    extract_column, analyze_column = st.columns(2, gap="large")
    with extract_column:
        with st.container(border=True):
            st.markdown("### 📝 Text extraction")
            st.write(
                "Convert one or more images and PDFs into editable text. "
                "OCR runs locally on your device."
            )
            st.button(
                "Extract text",
                type="primary",
                use_container_width=True,
                key="home_open_extract",
                on_click=navigate_to,
                args=("Text extraction",),
            )

    with analyze_column:
        with st.container(border=True):
            st.markdown("### ✨ Extract and analyze")
            st.write(
                "Extract the text, then get a short description of the "
                "document from an Ollama model."
            )
            st.button(
                "Analyze a document",
                type="primary",
                use_container_width=True,
                key="home_open_analysis",
                on_click=navigate_to,
                args=("AI analysis",),
            )

    st.markdown('<div class="section-title">How it works</div>', unsafe_allow_html=True)
    steps = [
        ("Upload", "Add PNG, JPG, TIFF, BMP, or PDF files. You can upload several at once."),
        ("Extract", "Tesseract reads the text on your device. Scanned pages are enhanced first."),
        ("Review and download", "Check the text against the original, then download it as a .txt file."),
    ]
    for column, (number, (title, text)) in zip(
        st.columns(3, gap="medium"), enumerate(steps, start=1)
    ):
        column.markdown(
            f'<div class="step"><span class="step-num">{number}</span>'
            f"<h4>{title}</h4><p>{text}</p></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="notice">
          AI analysis sends only the extracted text to Ollama Cloud, and only after
          you give consent. Descriptions are limited to 750 characters. Always check
          important details against the source document.
          Questions? <a href="{WHATSAPP_URL}" target="_blank"
          rel="noopener noreferrer">Message Huzaifa Ameer on WhatsApp</a>.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_settings() -> dict[str, Any]:
    with st.expander("⚙️ Extraction settings", expanded=False):
        left, right = st.columns(2, gap="large")
        with left:
            use_ocr = st.checkbox(
                "OCR scanned PDF pages",
                value=True,
                help="If disabled, PDFs use embedded text only.",
            )
            improve_quality = st.checkbox(
                "Enhance low-quality scans",
                value=True,
                help="Correct orientation, boost contrast, sharpen, and resize scans.",
            )
            language = st.text_input(
                "Tesseract language",
                value="eng",
                help="Use an installed language code. English is the default.",
            )
        with right:
            psm_label = st.selectbox(
                "Page layout",
                options=list(PAGE_SEGMENTATION_MODES),
                index=0,
                help="Choose a layout suited to the page's text arrangement.",
            )
            dpi = st.slider(
                "Scanned PDF resolution (DPI)",
                min_value=200,
                max_value=400,
                value=300,
                step=50,
                help="Higher DPI can help small print, but takes longer to process.",
            )
        st.caption(
            "Tesseract runs locally. Only the AI workflow sends extracted text "
            "to Ollama Cloud, after consent."
        )
    return {
        "use_ocr": use_ocr,
        "language": language,
        "page_segmentation_mode": PAGE_SEGMENTATION_MODES[psm_label],
        "dpi": dpi,
        "improve_quality": improve_quality,
    }


def render_results(
    workflow: str,
    documents: list[dict[str, Any]],
    signature: object,
) -> None:
    if not documents:
        return

    successful = [document for document in documents if not document["error"]]
    pages = [page for document in successful for page in document["pages"]]
    confidences = [
        page["confidence"]
        for page in pages
        if page["confidence"] is not None
    ]
    metrics = st.columns(4)
    metrics[0].metric("Documents", len(documents))
    metrics[1].metric("Pages", len(pages))
    metrics[2].metric(
        "Characters",
        f"{sum(len(page['text']) for page in pages):,}",
    )
    metrics[3].metric(
        "Average OCR confidence",
        f"{sum(confidences) / len(confidences):.1f}%"
        if confidences
        else "N/A",
        help="Tesseract's estimate, not a guarantee of text correctness.",
    )

    signature_key = hashlib.sha256(
        repr(signature).encode("utf-8")
    ).hexdigest()[:12]
    for document_index, document in enumerate(documents):
        if document["error"]:
            st.error(f"Could not process {document['name']}: {document['error']}")
            continue

        document_pages = document["pages"]
        character_count = sum(len(page["text"]) for page in document_pages)
        with st.container(border=True):
            st.markdown(f"#### 📄 {document['name']}")
            st.caption(
                f"{len(document_pages)} page(s) · "
                f"{character_count:,} extracted characters"
            )

            if workflow == "analyze":
                if document["ai_error"]:
                    st.warning(f"AI analysis unavailable: {document['ai_error']}")
                elif document["ai_insights"]:
                    description = document["ai_insights"]["description"]
                    st.markdown("**Document description**")
                    st.info(description)
                    st.caption(
                        f"{len(description)}/{MAX_DESCRIPTION_CHARACTERS} "
                        "characters · generated from extracted OCR text"
                    )
                    st.caption(
                        "AI-generated content can be incorrect. Verify important "
                        "names, dates, numbers, and amounts against the source."
                    )
                    if document["analysis_note"]:
                        st.caption(document["analysis_note"])

            for page_index, page in enumerate(document_pages, start=1):
                with st.expander(
                    f"Page {page['page']} · {page['method']}",
                    expanded=len(document_pages) == 1,
                ):
                    if page["confidence"] is not None:
                        st.caption(
                            f"Estimated OCR confidence: "
                            f"{page['confidence']:.1f}%"
                        )
                    st.text_area(
                        "Extracted text",
                        value=page["text"],
                        height=220,
                        key=(
                            f"{workflow}_text_{signature_key}_"
                            f"{document_index}_{page_index}"
                        ),
                    )

            st.download_button(
                f"Download {document['name']} results",
                data=build_document_text(document),
                file_name=f"{Path(document['name']).name}.txt",
                mime="text/plain",
                key=f"{workflow}_download_{signature_key}_{document_index}",
            )

    st.download_button(
        "Download all results",
        data=build_download_text(documents),
        file_name=(
            "extracted_text.txt"
            if workflow == "extract"
            else "document_analysis.txt"
        ),
        mime="text/plain",
        use_container_width=True,
        key=f"{workflow}_download_all_{signature_key}",
    )


def render_workflow(
    workflow: str,
    *,
    ocr_settings: dict[str, Any],
    api_key: str,
    model_name: str,
) -> None:
    analyze_with_ai = workflow == "analyze"
    if analyze_with_ai:
        st.markdown(
            """
            <div class="page-head">
              <h2>Extract, understand, and summarize</h2>
              <p>First extract the document text, then ask Ollama to describe
              the content using only that extracted text.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        model_col, status_col = st.columns([2, 3])
        model_index = OLLAMA_CLOUD_MODELS.index(model_name)
        selected_model = model_col.selectbox(
            "Ollama Cloud model",
            options=OLLAMA_CLOUD_MODELS,
            index=model_index,
            key="analysis_model",
            help="Your selected model must be available to your Ollama account.",
        )
        if api_key:
            status_col.success("Ollama API key found in your local configuration.")
        else:
            status_col.warning(
                "Add your API key to the project .env file, then restart the app."
            )
        consent = st.checkbox(
            "I agree to send extracted text to Ollama Cloud for analysis.",
            value=False,
            key="analysis_consent",
            help=(
                "The original image/PDF is not sent. OCR text may contain "
                "sensitive data; only continue if you are allowed to share it."
            ),
        )
        if not consent:
            st.caption("AI analysis is off until you give consent.")
    else:
        selected_model = model_name
        consent = False
        st.markdown(
            """
            <div class="page-head">
              <h2>Turn images and PDFs into editable text</h2>
              <p>Extract English text locally with Tesseract. No document
              content is sent to an AI service on this page.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    uploader_key = (
        f"{workflow}_uploader_"
        f"{st.session_state[f'{workflow}_uploader_generation']}"
    )
    st.file_uploader(
        "Choose image or PDF files",
        type=["pdf", *SUPPORTED_IMAGES],
        accept_multiple_files=True,
        key=uploader_key,
        help="Supported images: PNG, JPG, TIFF, BMP. Multiple files are supported.",
    )
    uploaded_files = st.session_state.get(uploader_key) or []

    if uploaded_files:
        st.caption(
            f"{len(uploaded_files)} file(s) ready · "
            f"{sum(uploaded_file.size for uploaded_file in uploaded_files) / 1024:.1f} KB"
        )
        with st.expander("Review selected files", expanded=False):
            for uploaded_file in uploaded_files:
                st.write(f"• {uploaded_file.name} · {uploaded_file.size / 1024:.1f} KB")

    workflow_signature = (
        get_upload_signature(uploaded_files),
        ocr_settings["use_ocr"],
        ocr_settings["language"],
        ocr_settings["page_segmentation_mode"],
        ocr_settings["dpi"],
        ocr_settings["improve_quality"],
        selected_model if analyze_with_ai else "",
        consent if analyze_with_ai else False,
    )
    signature_key = f"{workflow}_active_signature"
    documents_key = f"{workflow}_documents"
    if workflow_signature != st.session_state[signature_key]:
        st.session_state[documents_key] = []
        st.session_state[signature_key] = workflow_signature

    action_column, clear_column, _ = st.columns([2, 1, 5])
    process_clicked = action_column.button(
        "✨ Extract and analyze" if analyze_with_ai else "📝 Extract text",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_files or (analyze_with_ai and not consent),
        key=f"{workflow}_process",
    )
    clear_column.button(
        "Clear",
        use_container_width=True,
        disabled=not uploaded_files and not st.session_state[documents_key],
        on_click=clear_workflow,
        args=(workflow,),
        key=f"{workflow}_clear",
    )

    if process_clicked:
        progress = st.progress(0, text="Starting document processing...")
        documents = extract_uploaded_documents(
            uploaded_files,
            use_ocr=ocr_settings["use_ocr"],
            language=ocr_settings["language"],
            page_segmentation_mode=ocr_settings["page_segmentation_mode"],
            dpi=ocr_settings["dpi"],
            improve_quality=ocr_settings["improve_quality"],
            analyze_with_ai=analyze_with_ai and consent,
            api_key=api_key,
            model_name=selected_model,
            progress=progress,
        )
        st.session_state[documents_key] = documents
        progress.progress(1.0, text="All files processed.")

    documents = st.session_state[documents_key]
    if documents:
        st.divider()
        st.subheader("Results")
        st.caption(
            "Review extracted text against the original. OCR confidence is an "
            "estimate and does not guarantee correctness."
        )
        render_results(workflow, documents, workflow_signature)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon=APP_LOGO_PATH.read_bytes(),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    initialize_state()
    api_key = get_ollama_setting("OLLAMA_API_KEY")
    default_model = get_ollama_setting("OLLAMA_MODEL", "gemma4:31b")
    if default_model not in OLLAMA_CLOUD_MODELS:
        default_model = "gemma4:31b"

    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    navigation = render_navbar()

    if navigation == "Home":
        render_home()
    elif navigation == "Text extraction":
        render_workflow(
            "extract",
            ocr_settings=render_settings(),
            api_key=api_key,
            model_name=default_model,
        )
    else:
        render_workflow(
            "analyze",
            ocr_settings=render_settings(),
            api_key=api_key,
            model_name=default_model,
        )

    render_footer()


if __name__ == "__main__":
    main()