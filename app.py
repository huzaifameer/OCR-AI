import hashlib
from typing import Any

import streamlit as st

from document_processing import extract_image, extract_pdf


SUPPORTED_IMAGES = ["png", "jpg", "jpeg", "tiff", "bmp"]
PAGE_SEGMENTATION_MODES = {
    "Automatic page layout": 3,
    "Single block of text": 6,
    "Sparse or scattered text": 11,
}
SESSION_DEFAULTS: dict[str, Any] = {
    "uploader_generation": 0,
    "active_upload_signature": None,
    "extracted_documents": [],
}


def clear_documents() -> None:
    """Clear extracted text and reset the upload control."""
    st.session_state["extracted_documents"] = []
    st.session_state["active_upload_signature"] = None
    st.session_state["uploader_generation"] += 1


def get_upload_signature(uploaded_files: list[Any]) -> tuple[tuple[str, str], ...]:
    """Identify the selected uploads, including replacements with the same name."""
    return tuple(
        (
            uploaded_file.name,
            hashlib.sha256(uploaded_file.getvalue()).hexdigest(),
        )
        for uploaded_file in uploaded_files
    )


def build_combined_text(documents: list[dict[str, Any]]) -> str:
    sections = []
    for document in documents:
        if document["error"]:
            sections.append(
                f"--- {document['name']} ---\n"
                f"Extraction failed: {document['error']}"
            )
            continue

        pages = "\n\n".join(
            f"Page {page['page']} — {page['method']}\n{page['text']}"
            for page in document["pages"]
        )
        sections.append(f"--- {document['name']} ---\n{pages}")

    return "\n\n".join(sections)


def main() -> None:
    st.set_page_config(
        page_title="Image & PDF OCR",
        page_icon="📄",
        layout="wide",
    )

    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default

    st.markdown(
        """
        <style>
        .block-container {max-width: 1240px; padding-top: 1.5rem; padding-bottom: 3rem;}
        .hero {padding: 1.6rem 1.8rem; border-radius: 18px;
               background: linear-gradient(120deg, #102d42, #126b78);
               color: white; margin-bottom: 1.3rem;}
        .hero h1 {margin: 0 0 .35rem 0; font-size: 2rem;}
        .hero p {margin: 0; opacity: .9;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="hero">
          <h1>📄 Image &amp; PDF OCR</h1>
          <p>Extract and review English text from images, scans, and PDF documents.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("OCR settings")
        use_ocr = st.checkbox(
            "OCR scanned PDF pages",
            value=True,
            help="When disabled, PDFs use embedded text only.",
        )
        language = st.text_input(
            "OCR language code",
            value="eng",
            help=(
                "English is the default. You can enter another installed "
                "Tesseract language code if needed."
            ),
        )
        psm_label = st.selectbox(
            "Page layout",
            options=list(PAGE_SEGMENTATION_MODES),
            index=0,
            help="Try a different layout if text order or columns are incorrect.",
        )
        dpi = st.slider(
            "PDF scan resolution (DPI)",
            min_value=200,
            max_value=400,
            value=300,
            step=50,
            help="Higher resolution can improve small text but takes longer.",
        )
        improve_quality = st.checkbox(
            "Enhance low-quality scans",
            value=True,
            help="Correct orientation, boost contrast, sharpen, and resize scans.",
        )
        st.caption(
            "English OCR is selected by default. Other languages require their "
            "Tesseract language data to be installed."
        )

    st.subheader("1 · Add documents")
    st.caption(
        "Upload one or more English-language images or PDFs. Results are shown "
        "separately for each file."
    )
    uploaded_files = st.file_uploader(
        "Choose documents",
        type=["pdf", *SUPPORTED_IMAGES],
        accept_multiple_files=True,
        key=f"uploaded_documents_{st.session_state['uploader_generation']}",
    )

    if uploaded_files:
        st.info(
            f"**{len(uploaded_files)} file(s) selected** · "
            f"{sum(file.size for file in uploaded_files) / 1024:.1f} KB total"
        )

    settings_signature = (
        use_ocr,
        language,
        PAGE_SEGMENTATION_MODES[psm_label],
        dpi,
        improve_quality,
    )
    current_signature = (get_upload_signature(uploaded_files), settings_signature)
    if current_signature != st.session_state["active_upload_signature"]:
        st.session_state["extracted_documents"] = []
        st.session_state["active_upload_signature"] = current_signature

    action_col, clear_col, _ = st.columns([2, 1, 5])
    extract_clicked = action_col.button(
        "✨ Extract text",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_files,
    )
    clear_col.button(
        "🧹 Clear",
        use_container_width=True,
        disabled=not uploaded_files
        and not st.session_state["extracted_documents"],
        on_click=clear_documents,
    )

    if extract_clicked:
        extracted_documents = []
        progress = st.progress(0, text="Preparing documents...")
        for index, uploaded_file in enumerate(uploaded_files, start=1):
            progress.progress(
                (index - 1) / len(uploaded_files),
                text=f"Starting {uploaded_file.name} ({index}/{len(uploaded_files)})",
            )
            try:
                file_bytes = uploaded_file.getvalue()
                extension = uploaded_file.name.lower().rsplit(".", 1)[-1]
                if extension == "pdf":
                    def update_page_progress(page_number: int, page_count: int) -> None:
                        file_progress = page_number / page_count
                        overall_progress = (
                            index - 1 + file_progress
                        ) / len(uploaded_files)
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
                        page_segmentation_mode=PAGE_SEGMENTATION_MODES[psm_label],
                        dpi=dpi,
                        improve_quality=improve_quality,
                        progress_callback=update_page_progress,
                    )
                else:
                    pages = extract_image(
                        file_bytes,
                        language=language,
                        page_segmentation_mode=PAGE_SEGMENTATION_MODES[psm_label],
                        improve_quality=improve_quality,
                    )
                extracted_documents.append({
                    "name": uploaded_file.name,
                    "pages": pages,
                    "error": None,
                })
                progress.progress(
                    index / len(uploaded_files),
                    text=f"Finished {uploaded_file.name} ({index}/{len(uploaded_files)})",
                )
            except Exception as error:
                extracted_documents.append({
                    "name": uploaded_file.name,
                    "pages": [],
                    "error": str(error),
                })

        st.session_state["extracted_documents"] = extracted_documents

    extracted_documents = st.session_state["extracted_documents"]
    if extracted_documents:
        st.divider()
        st.subheader("2 · Review extracted text")
        st.caption(
            "OCR confidence is Tesseract's estimate, not a guarantee of correctness. "
            "Review important names, numbers, dates, and other details against "
            "the original."
        )

        successful_documents = [
            document for document in extracted_documents if not document["error"]
        ]
        all_pages = [
            page for document in successful_documents for page in document["pages"]
        ]
        total_pages = len(all_pages)
        total_characters = sum(len(page["text"]) for page in all_pages)
        ocr_pages = [
            page for page in all_pages if "OCR (Tesseract)" in page["method"]
        ]
        confidence_scores = [
            page["confidence"]
            for page in ocr_pages
            if page["confidence"] is not None
        ]

        metric_columns = st.columns(4)
        metric_columns[0].metric("Documents", len(extracted_documents))
        metric_columns[1].metric("Pages", total_pages)
        metric_columns[2].metric("Extracted characters", total_characters)
        metric_columns[3].metric("Average OCR confidence", (
            f"{sum(confidence_scores) / len(confidence_scores):.1f}%"
            if confidence_scores
            else "N/A"
        ))

        signature_key = hashlib.sha256(
            repr(current_signature).encode("utf-8")
        ).hexdigest()[:12]
        for document_index, document in enumerate(extracted_documents):
            if document["error"]:
                with st.container(border=True):
                    st.error(f"{document['name']}: {document['error']}")
                continue

            document_characters = sum(
                len(page["text"]) for page in document["pages"]
            )
            with st.container(border=True):
                st.markdown(f"#### 🗂️ {document['name']}")
                st.caption(
                    f"{len(document['pages'])} page(s) · "
                    f"{document_characters:,} extracted characters"
                )
                for page_index, page in enumerate(document["pages"], start=1):
                    with st.expander(
                        f"Page {page['page']} · {page['method']}",
                        expanded=True,
                    ):
                        if page["confidence"] is not None:
                            st.caption(
                                "Estimated OCR confidence: "
                                f"{page['confidence']:.1f}%"
                            )
                        elif "OCR (Tesseract)" not in page["method"]:
                            st.caption("Confidence estimate unavailable for digital text.")
                        st.text_area(
                            "Extracted text",
                            value=page["text"],
                            height=220,
                            key=(
                                f"text_{signature_key}_{document_index}_"
                                f"{page_index}"
                            ),
                        )

                document_text = "\n\n".join(
                    f"--- Page {page['page']} ---\n{page['text']}"
                    for page in document["pages"]
                )
                st.download_button(
                    f"Download {document['name']} text",
                    data=document_text,
                    file_name=f"{document['name']}.txt",
                    mime="text/plain",
                    key=f"download_{signature_key}_{document_index}",
                )

        st.download_button(
            "Download all extracted text",
            data=build_combined_text(extracted_documents),
            file_name="extracted_documents.txt",
            mime="text/plain",
            type="primary",
            use_container_width=True,
            key=f"download_all_{signature_key}",
        )

    st.markdown(
        """
        <style>
        .app-footer {text-align: center; color: #718096; font-size: .9rem;
                     padding: 1.25rem 0 .5rem; border-top: 1px solid #e6eaf0;
                     margin-top: 2rem;}
        </style>
        <div class="app-footer">Developed by Huzaifa Ameer</div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
