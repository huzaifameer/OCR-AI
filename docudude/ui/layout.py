"""Shared page chrome: navigation bar, home page, page headers and footer."""

from __future__ import annotations

import base64
import datetime
from functools import lru_cache
from html import escape

import streamlit as st

from docudude.config import (
    APP_LOGO_PATH,
    APP_NAME,
    APP_TAGLINE,
    AUTHOR,
    PAGES,
    WHATSAPP_DISPLAY,
    WHATSAPP_URL,
)


def navigate_to(page: str) -> None:
    st.session_state["page"] = page


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    try:
        encoded = base64.b64encode(APP_LOGO_PATH.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{encoded}"


def render_navbar() -> str:
    current = st.session_state["page"]
    with st.container(key="navbar"):
        brand_col, nav_col = st.columns([2, 5], vertical_alignment="center")
        logo = _logo_data_uri()
        logo_html = (
            f'<img src="{logo}" alt="" width="54" height="54" '
            'style="object-fit:contain;flex:none">'
            if logo
            else ""
        )
        brand_col.markdown(
            f'<div class="brand">{logo_html}<div class="brand-text">'
            f'<div class="brand-name">{APP_NAME}</div>'
            f'<div class="brand-tag">{APP_TAGLINE}</div></div></div>',
            unsafe_allow_html=True,
        )
        with nav_col:
            for column, (page_id, label) in zip(st.columns(len(PAGES)), PAGES.items()):
                column.button(
                    label,
                    type="primary" if page_id == current else "secondary",
                    width="stretch",
                    key=f"nav_{page_id}",
                    on_click=navigate_to,
                    args=(page_id,),
                )
    return st.session_state["page"]


def render_page_header(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="page-head"><div class="kicker">{escape(kicker)}</div>'
        f"<h2>{escape(title)}</h2><p>{escape(description)}</p></div>",
        unsafe_allow_html=True,
    )


def section_label(number: int, text: str) -> None:
    st.markdown(
        f'<div class="section-label"><span class="num">{number}</span>{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_privacy_notice() -> None:
    st.markdown(
        """
        <div class="notice">
          <strong>Privacy.</strong> DocuDude does not store your files or extracted
          text. Text extraction runs on this server with Tesseract and shares
          nothing with AI services. AI analysis sends only the extracted text (never
          the file itself) to Ollama Cloud, and only after you agree; its data
          handling is governed by that service's policies.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    st.markdown(
        """
        <section class="hero">
          <div class="kicker">DocuDude · Document OCR</div>
          <h1>Turn scans, photos and PDFs into accurate, usable text.</h1>
          <p>Upload a document and get editable text with uncertain words
          highlighted for review. Add AI analysis to identify the document type,
          summarise it, and pull out key facts that are checked against the
          source text.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.markdown("### 📝 Text extraction")
        st.write(
            "Convert images and PDFs into editable text. Pages are automatically "
            "rotated, straightened and cleaned before OCR."
        )
        st.button(
            "Extract text",
            type="primary",
            width="stretch",
            key="home_extract",
            on_click=navigate_to,
            args=("extract",),
        )
    with right, st.container(border=True):
        st.markdown("### ✨ AI analysis")
        st.write(
            "Extract the text, then get the document type, a short summary and "
            "key fields. Each field is verified against the extracted text."
        )
        st.button(
            "Analyze a document",
            type="primary",
            width="stretch",
            key="home_analyze",
            on_click=navigate_to,
            args=("analyze",),
        )

    st.markdown('<div class="section-title">How it works</div>', unsafe_allow_html=True)
    steps = [
        ("Upload", "Add PDF, PNG, JPG, TIFF, BMP or WEBP files. Several files at once are fine."),
        (
            "Clean up and read",
            "Each page is rotated, deskewed, resized and de-shadowed, then read "
            "in one or more OCR passes. The most confident result is kept.",
        ),
        (
            "Review and export",
            "Check highlighted low-confidence words, edit the text, and download "
            "it as TXT or JSON.",
        ),
    ]
    for column, (number, (title, text)) in zip(
        st.columns(3, gap="medium"), enumerate(steps, start=1)
    ):
        column.markdown(
            f'<div class="step"><span class="num">{number}</span>'
            f"<h4>{title}</h4><p>{text}</p></div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Privacy</div>', unsafe_allow_html=True)
    render_privacy_notice()


def render_footer() -> None:
    year = datetime.date.today().year
    with st.container(key="site_footer"):
        about, pages, formats, contact = st.columns([3, 2, 2, 3], gap="large")
        about.markdown(
            f'<div class="footer-brand">{APP_NAME}</div>'
            '<p>Accurate text extraction from images and PDFs, with optional '
            "AI analysis.</p>",
            unsafe_allow_html=True,
        )
        with pages:
            st.markdown('<div class="footer-heading">Pages</div>', unsafe_allow_html=True)
            for page_id, label in PAGES.items():
                st.button(
                    label, key=f"footer_{page_id}", on_click=navigate_to, args=(page_id,)
                )
        formats.markdown(
            '<div class="footer-heading">Supported files</div>'
            "<ul><li>PDF (digital and scanned)</li><li>PNG, JPG, WEBP</li>"
            "<li>TIFF (multi-page), BMP</li></ul>",
            unsafe_allow_html=True,
        )
        contact.markdown(
            '<div class="footer-heading">Contact</div>'
            "<p>Questions or feedback?<br>"
            f'<a href="{WHATSAPP_URL}" target="_blank" rel="noopener noreferrer">'
            f"WhatsApp {WHATSAPP_DISPLAY}</a></p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="footer-bottom"><span>© {year} {APP_NAME}. All rights '
            f"reserved.</span><span>Developed by {AUTHOR}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<a class="whatsapp-float" href="{WHATSAPP_URL}" target="_blank" '
        f'rel="noopener noreferrer" aria-label="Contact {AUTHOR} on WhatsApp" '
        f'title="WhatsApp {AUTHOR}: {WHATSAPP_DISPLAY}">'
        '<span class="whatsapp-icon">💬</span>'
        '<span class="whatsapp-label">Chat with Huzaifa</span></a>',
        unsafe_allow_html=True,
    )
