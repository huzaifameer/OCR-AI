import io

import numpy as np
import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont

from docudude.ocr import OcrSettings, _looks_garbled, clean_text, extract_pdf, ocr_image, tesseract_status
from docudude.preprocessing import estimate_skew, is_inverted

TEXT = "Invoice number INV-2024-0387\nTotal due LKR 3,516.99\nThank you for your business"


def _render(size=28) -> Image.Image:
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default(size=size)
    image = Image.new("L", (900, 260), 255)
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(TEXT.split("\n")):
        draw.text((40, 40 + index * size * 1.7), line, font=font, fill=0)
    return image


def test_clean_text_expands_ligatures_and_strips_controls():
    assert clean_text("\ufb01nal\x00 text \n\n\n\nend") == "final text\n\nend"


def test_garbled_detection():
    assert _looks_garbled("(cid:12)(cid:15)(cid:3)")
    assert _looks_garbled("\ufffd\ufffd\ufffd ab")
    assert not _looks_garbled("A normal sentence with 12 words.")


def test_skew_estimation_recovers_rotation():
    image = _render().rotate(4, expand=True, fillcolor=255, resample=Image.BICUBIC)
    assert estimate_skew(np.array(image)) == pytest.approx(-4, abs=0.5)
    assert estimate_skew(np.array(_render())) == 0.0


def test_inversion_detection():
    assert is_inverted(255 - np.array(_render()))
    assert not is_inverted(np.array(_render()))


tesseract = pytest.mark.skipif(not tesseract_status()[0], reason="Tesseract not installed")


@tesseract
@pytest.mark.parametrize(
    "transform",
    [
        lambda im: im,
        lambda im: im.rotate(180),
        lambda im: Image.fromarray(255 - np.array(im)),
        lambda im: im.rotate(3, expand=True, fillcolor=255, resample=Image.BICUBIC),
    ],
    ids=["clean", "upside-down", "inverted", "skewed"],
)
def test_ocr_reads_degraded_images(transform):
    result = ocr_image(transform(_render()), OcrSettings(accuracy_mode="fast"))
    assert "INV-2024-0387" in result.text
    assert "3,516.99" in result.text
    assert result.confidence and result.confidence > 80


@tesseract
def test_pdf_uses_embedded_text_and_ocrs_scans():
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Embedded digital text on page one.")
    scanned = document.new_page()
    buffer = io.BytesIO()
    _render().save(buffer, "PNG")
    scanned.insert_image(scanned.rect, stream=buffer.getvalue())

    pages = extract_pdf(document.tobytes(), OcrSettings(accuracy_mode="fast"))
    assert [page.method for page in pages] == ["Digital text", "OCR"]
    assert "Embedded digital text" in pages[0].text
    assert "INV-2024-0387" in pages[1].text
    assert all(page.preview for page in pages)
