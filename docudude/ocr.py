"""Text extraction from PDFs and images using PyMuPDF and Tesseract."""

from __future__ import annotations

import io
import os
import re
import shutil
import unicodedata
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from statistics import median
from typing import Any

import numpy as np
import pymupdf
import pytesseract
from PIL import Image, ImageSequence

from docudude.preprocessing import prepare_for_ocr

# Tesseract spawns one process per call; we parallelise across pages instead
# of letting each process start its own OpenMP threads.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

LOW_CONFIDENCE = 60.0  # words below this are highlighted for review
MAX_WORKERS = max(1, min(4, (os.cpu_count() or 2) - 1))
PREVIEW_DPI = 90
MAX_PREVIEW_PAGES = 50

ACCURACY_MODES = {
    # mode -> preprocessing variants tried; the most confident result wins
    "fast": ("gray",),
    "balanced": ("gray", "binary"),
    "best": ("gray", "binary", "original"),
}
VARIANT_LABELS = {
    "gray": "Normalised grayscale",
    "binary": "Adaptive black & white",
    "original": "Unfiltered",
}


# --------------------------------------------------------------------------
# Tesseract discovery
# --------------------------------------------------------------------------
def _find_tesseract() -> str | None:
    candidates = [
        os.environ.get("TESSERACT_CMD", ""),
        shutil.which("tesseract") or "",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"
        ),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


_TESSERACT_PATH = _find_tesseract()
if _TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH


def tesseract_status() -> tuple[bool, str]:
    """(available, version-or-error) for display in the UI."""
    try:
        return True, str(pytesseract.get_tesseract_version())
    except Exception as error:  # noqa: BLE001 - surfaced to the user
        return False, str(error)


def available_languages() -> list[str]:
    try:
        languages = pytesseract.get_languages(config="")
    except Exception:  # noqa: BLE001
        return ["eng"]
    return sorted(lang for lang in languages if lang not in {"osd", "equ"}) or ["eng"]


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class OcrSettings:
    language: str = "eng"
    page_segmentation_mode: int = 3
    accuracy_mode: str = "balanced"
    dpi: int = 300
    enhance: bool = True
    auto_rotate: bool = True
    deskew: bool = True
    preserve_layout: bool = True
    ocr_pdf_pages: bool = True
    force_ocr: bool = False


@dataclass
class PageResult:
    page: int
    method: str  # "Digital text" or "OCR"
    text: str
    confidence: float | None = None
    word_count: int = 0
    low_confidence_words: int = 0
    # Per-line (word, confidence) pairs, used to highlight uncertain words.
    lines: list[list[tuple[str, float]]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    preview: bytes | None = None


@dataclass
class _OcrPass:
    text: str
    confidence: float | None
    score: float
    word_count: int
    low_confidence_words: int
    lines: list[list[tuple[str, float]]]


# --------------------------------------------------------------------------
# Text clean-up
# --------------------------------------------------------------------------
_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u00a0": " ",
    "\u200b": "",
}


def clean_text(text: str) -> str:
    for source, target in _LIGATURES.items():
        text = text.replace(source, target)
    text = "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
    )
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_language(language: str) -> str:
    language = language.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*", language):
        raise ValueError(
            "Enter a valid Tesseract language code, for example 'eng' or 'eng+fra'."
        )
    return language


# --------------------------------------------------------------------------
# OCR core
# --------------------------------------------------------------------------
def _run_tesseract(image: np.ndarray, settings: OcrSettings, preserve_layout: bool) -> _OcrPass:
    data: dict[str, Any] = pytesseract.image_to_data(
        image,
        lang=settings.language,
        config=(
            f"--oem 3 --psm {settings.page_segmentation_mode} "
            "-c preserve_interword_spaces=1"
        ),
        output_type=pytesseract.Output.DICT,
    )

    # Group words by block/paragraph/line, keeping position for spacing.
    lines: dict[tuple[int, int, int], list[tuple[str, float, int, int]]] = {}
    char_widths: list[float] = []
    for index, raw in enumerate(data["text"]):
        word = (raw or "").strip()
        if not word:
            continue
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            continue
        if confidence < 0:
            continue
        if confidence < 50 and len(word) <= 2 and not any(ch.isalnum() for ch in word):
            continue  # specks and smudges read as stray symbols ("~", "|", "©")
        left, width = int(data["left"][index]), int(data["width"][index])
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        lines.setdefault(key, []).append((word, confidence, left, width))
        char_widths.append(width / max(1, len(word)))

    char_width = median(char_widths) if char_widths else 10.0
    output_lines: list[str] = []
    line_words: list[list[tuple[str, float]]] = []
    previous_paragraph: tuple[int, int] | None = None
    weighted_conf = 0.0
    total_chars = 0
    score = 0.0
    low_conf = 0

    for (block, paragraph, _), words in lines.items():
        words.sort(key=lambda item: item[2])
        if previous_paragraph is not None and previous_paragraph != (block, paragraph):
            output_lines.append("")  # blank line between paragraphs/blocks
            line_words.append([])
        previous_paragraph = (block, paragraph)

        parts: list[str] = []
        for position, (word, confidence, left, width) in enumerate(words):
            if position:
                previous = words[position - 1]
                gap = left - (previous[2] + previous[3])
                spaces = 1
                if preserve_layout and gap > char_width * 2.5:
                    spaces = min(12, max(2, round(gap / char_width)))
                parts.append(" " * spaces)
            parts.append(word)

            length = len(word)
            weighted_conf += confidence * length
            total_chars += length
            score += length * (confidence / 100) ** 2
            if confidence < LOW_CONFIDENCE:
                low_conf += 1
        output_lines.append("".join(parts))
        line_words.append([(word, round(conf, 1)) for word, conf, _, _ in words])

    word_total = sum(len(words) for words in lines.values())
    return _OcrPass(
        text=clean_text("\n".join(output_lines)),
        confidence=round(weighted_conf / total_chars, 1) if total_chars else None,
        score=score,
        word_count=word_total,
        low_confidence_words=low_conf,
        lines=line_words,
    )


def ocr_image(image: Image.Image, settings: OcrSettings) -> PageResult:
    """OCR one page image, trying several preprocessing variants."""
    prepared = prepare_for_ocr(
        image,
        enhance=settings.enhance,
        auto_rotate=settings.auto_rotate,
        deskew=settings.deskew,
    )
    variants = ACCURACY_MODES.get(settings.accuracy_mode, ACCURACY_MODES["balanced"])
    if not settings.enhance:
        variants = ("gray",)

    best_variant = variants[0]
    best: _OcrPass | None = None
    for variant in variants:
        result = _run_tesseract(prepared.variant(variant), settings, settings.preserve_layout)
        if best is None or result.score > best.score:
            best, best_variant = result, variant
        # A near-perfect first pass is good enough; skip the extra work.
        if best.confidence is not None and best.confidence >= 96 and best.word_count >= 5:
            break

    assert best is not None
    notes = list(prepared.notes)
    if len(variants) > 1 and best.text:
        notes.append(f"Best pass: {VARIANT_LABELS[best_variant]}")
    return PageResult(
        page=1,
        method="OCR",
        text=best.text,
        confidence=best.confidence,
        word_count=best.word_count,
        low_confidence_words=best.low_confidence_words,
        lines=best.lines,
        notes=notes,
    )


def _make_preview(image: Image.Image) -> bytes:
    preview = image.convert("RGB")
    preview.thumbnail((1100, 1400))
    buffer = io.BytesIO()
    preview.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# PDF helpers
# --------------------------------------------------------------------------
def _looks_garbled(text: str) -> bool:
    """Detect broken embedded text (missing font maps, (cid:..) codes, etc.)."""
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return True
    bad = compact.count("\ufffd") + len(re.findall(r"\(cid:\d+\)", text)) * 6
    alnum = sum(ch.isalnum() for ch in compact)
    return bad / len(compact) > 0.03 or alnum / len(compact) < 0.35


def _image_coverage(page: pymupdf.Page) -> float:
    page_area = abs(page.rect)
    if not page_area:
        return 0.0
    covered = 0.0
    for info in page.get_image_info():
        rect = pymupdf.Rect(info["bbox"]) & page.rect
        covered += abs(rect)
    return min(1.0, covered / page_area)


def _render_page(page: pymupdf.Page, dpi: int) -> Image.Image:
    scale = dpi / 72
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False
    )
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _ocr_error(page_number: int, settings: OcrSettings, error: Exception) -> RuntimeError:
    return RuntimeError(
        f"OCR failed on page {page_number}. Check that Tesseract and the "
        f"'{settings.language}' language data are installed. Details: {error}"
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
ProgressCallback = Callable[[int, int], None]


def extract_pdf(
    pdf_bytes: bytes,
    settings: OcrSettings,
    progress_callback: ProgressCallback | None = None,
) -> list[PageResult]:
    """Use embedded text where it is reliable and OCR everything else."""
    if settings.ocr_pdf_pages:
        validate_language(settings.language)

    results: dict[int, PageResult] = {}
    pending: dict[int, tuple[Future[PageResult], PageResult | None, bytes | None]] = {}
    done_count = 0

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document, ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        page_count = len(document)

        def collect(block: bool) -> None:
            nonlocal done_count
            for number in sorted(pending):
                future, digital, preview = pending[number]
                if not block and not future.done():
                    continue
                try:
                    ocr_result = future.result()
                except Exception as error:  # noqa: BLE001
                    raise _ocr_error(number, settings, error) from error
                ocr_result.page = number
                if digital is not None and len(ocr_result.text) < len(digital.text) * 1.3:
                    # The embedded text was as complete as OCR; keep it.
                    digital.notes.append("Embedded text kept (OCR found no extra text)")
                    ocr_result = digital
                elif not ocr_result.text:
                    ocr_result.notes.append("No readable text found on this page")
                ocr_result.preview = preview
                results[number] = ocr_result
                del pending[number]
                done_count += 1
                if progress_callback:
                    progress_callback(done_count, page_count)
                if block:
                    return

        for number, page in enumerate(document, start=1):
            text = clean_text(page.get_text("text", sort=True))
            preview = (
                _make_preview(_render_page(page, PREVIEW_DPI))
                if number <= MAX_PREVIEW_PAGES
                else None
            )
            garbled = bool(text) and _looks_garbled(text)
            coverage = _image_coverage(page)
            needs_ocr = settings.ocr_pdf_pages and (
                settings.force_ocr
                or len(text) < 30
                or garbled
                or (coverage > 0.5 and len(text) < 800)
            )

            if not needs_ocr:
                results[number] = PageResult(
                    page=number,
                    method="Digital text",
                    text=text,
                    word_count=len(text.split()),
                    preview=preview,
                )
                done_count += 1
                if progress_callback:
                    progress_callback(done_count, page_count)
                continue

            # Keep the embedded text as a fallback only if it is trustworthy.
            fallback = None
            if text and not garbled and not settings.force_ocr:
                fallback = PageResult(
                    page=number,
                    method="Digital text",
                    text=text,
                    word_count=len(text.split()),
                    preview=preview,
                )
            image = _render_page(page, settings.dpi)
            future = executor.submit(ocr_image, image, settings)
            pending[number] = (future, fallback, preview)

            # Bound memory: don't render far ahead of the OCR workers.
            while len(pending) >= MAX_WORKERS * 2:
                collect(block=True)
            collect(block=False)

        while pending:
            collect(block=True)

    return [results[number] for number in sorted(results)]


def extract_image(
    image_bytes: bytes,
    settings: OcrSettings,
    progress_callback: ProgressCallback | None = None,
) -> list[PageResult]:
    """OCR an image file; multi-page TIFFs produce one result per frame."""
    validate_language(settings.language)
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            frames = [frame.copy() for frame in ImageSequence.Iterator(source)]
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"Could not open the image file. Details: {error}") from error

    results: list[PageResult] = []
    for number, frame in enumerate(frames, start=1):
        try:
            result = ocr_image(frame, settings)
        except Exception as error:  # noqa: BLE001
            raise _ocr_error(number, settings, error) from error
        result.page = number
        if number <= MAX_PREVIEW_PAGES:
            result.preview = _make_preview(frame)
        if not result.text:
            result.notes.append("No readable text found on this page")
        results.append(result)
        if progress_callback:
            progress_callback(number, len(frames))
    return results
