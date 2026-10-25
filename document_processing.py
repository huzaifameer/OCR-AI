import io
import os
import re
from collections import defaultdict
from collections.abc import Callable
from statistics import mean
from typing import Any, TypedDict

import pymupdf
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class ExtractionResult(TypedDict):
    page: int
    method: str
    text: str
    confidence: float | None


_DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_tesseract_path = os.environ.get("TESSERACT_CMD", _DEFAULT_TESSERACT_PATH)
if os.path.isfile(_tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path


def _validate_language(language: str) -> str:
    language = language.strip()
    if not re.fullmatch(r"[A-Za-z0-9_+-]+", language):
        raise ValueError(
            "Enter a valid Tesseract language code, for example 'eng' or "
            "'eng+fra'."
        )
    return language


def _prepare_image(image: Image.Image, improve_quality: bool) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if not improve_quality:
        return image

    grayscale = ImageOps.grayscale(image)
    longest_side = max(grayscale.size)
    if longest_side < 1800:
        scale = min(2.0, 1800 / longest_side)
        grayscale = grayscale.resize(
            (
                round(grayscale.width * scale),
                round(grayscale.height * scale),
            ),
            Image.Resampling.LANCZOS,
        )
    elif longest_side > 4000:
        scale = 4000 / longest_side
        grayscale = grayscale.resize(
            (
                round(grayscale.width * scale),
                round(grayscale.height * scale),
            ),
            Image.Resampling.LANCZOS,
        )

    grayscale = ImageOps.autocontrast(grayscale)
    grayscale = ImageEnhance.Contrast(grayscale).enhance(1.35)
    grayscale = grayscale.filter(
        ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3)
    )
    return grayscale.convert("RGB")


def _run_ocr(
    image: Image.Image,
    language: str,
    page_segmentation_mode: int,
) -> tuple[str, float | None]:
    data: dict[str, Any] = pytesseract.image_to_data(
        image,
        lang=language,
        config=f"--oem 3 --psm {page_segmentation_mode}",
        output_type=pytesseract.Output.DICT,
    )

    lines: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    confidences: list[float] = []
    for index, raw_word in enumerate(data["text"]):
        word = raw_word.strip()
        if not word:
            continue

        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            continue
        if confidence < 0:
            continue

        line_key = (
            str(data["block_num"][index]),
            str(data["par_num"][index]),
            str(data["line_num"][index]),
        )
        lines[line_key].append(word)
        confidences.append(confidence)

    text = "\n".join(" ".join(words) for words in lines.values()).strip()
    confidence_score = round(mean(confidences), 1) if confidences else None
    return text, confidence_score


def extract_pdf(
    pdf_bytes: bytes,
    use_ocr: bool = True,
    language: str = "eng",
    page_segmentation_mode: int = 3,
    dpi: int = 300,
    improve_quality: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[ExtractionResult]:
    """Extract embedded text and OCR scanned PDF pages."""
    if use_ocr:
        language = _validate_language(language)
    results: list[ExtractionResult] = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        page_count = len(document)
        for page_number, page in enumerate(document, start=1):
            if progress_callback is not None:
                progress_callback(page_number, page_count)

            text = page.get_text("text").strip()
            method = "Digital PDF text extraction"
            confidence = None

            if use_ocr and len(text) < 30:
                try:
                    scale = dpi / 72
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(scale, scale),
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                    )
                    page_image = Image.frombytes(
                        "RGB",
                        (pixmap.width, pixmap.height),
                        pixmap.samples,
                    )
                    page_image = _prepare_image(page_image, improve_quality)
                    ocr_text, confidence = _run_ocr(
                        page_image,
                        language,
                        page_segmentation_mode,
                    )
                except Exception as error:
                    raise RuntimeError(
                        "OCR failed for PDF page "
                        f"{page_number}. Check that Tesseract and the "
                        f"'{language}' language data are installed. "
                        f"Details: {error}"
                    ) from error

                if ocr_text:
                    text = ocr_text
                    method = "OCR (Tesseract)"
                else:
                    confidence = None

            results.append({
                "page": page_number,
                "method": method,
                "text": text,
                "confidence": confidence,
            })

    return results


def extract_image(
    image_bytes: bytes,
    language: str = "eng",
    page_segmentation_mode: int = 6,
    improve_quality: bool = True,
) -> list[ExtractionResult]:
    """Extract text and an estimated Tesseract confidence from an image."""
    language = _validate_language(language)
    try:
        with Image.open(io.BytesIO(image_bytes)) as source_image:
            image = _prepare_image(source_image, improve_quality)
        text, confidence = _run_ocr(image, language, page_segmentation_mode)
    except Exception as error:
        raise RuntimeError(
            "Could not run image OCR. Check that Tesseract and the "
            f"'{language}' language data are installed. "
            f"Details: {error}"
        ) from error

    return [{
        "page": 1,
        "method": "OCR (Tesseract)",
        "text": text,
        "confidence": confidence,
    }]
