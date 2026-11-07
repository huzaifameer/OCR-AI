"""Image preparation that makes scans and photos easier for Tesseract to read.

The pipeline follows Tesseract's own quality guidance:

1. Fix EXIF rotation and convert to grayscale.
2. Invert light-on-dark images (Tesseract expects dark text on light paper).
3. Rescale so typical character height is ~30 px, the size Tesseract reads best.
4. Correct page orientation (90/180/270 degrees) with Tesseract OSD.
5. Correct small skew angles with a projection-profile search.
6. Flatten uneven lighting/shadows (background division).
7. Optionally binarize with an adaptive threshold for noisy or low-contrast scans.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps

TARGET_TEXT_HEIGHT = 30.0  # median connected-component height, in pixels
MAX_SIDE = 7000  # keep memory and Tesseract runtime bounded


@dataclass
class PreparedImage:
    """A cleaned grayscale page plus the variants used for multi-pass OCR."""

    gray: np.ndarray  # normalised grayscale page
    notes: list[str] = field(default_factory=list)
    _binary: np.ndarray | None = None
    _original: np.ndarray | None = None

    def variant(self, name: str) -> np.ndarray:
        if name == "binary":
            if self._binary is None:
                self._binary = adaptive_binarize(self.gray)
            return self._binary
        if name == "original" and self._original is not None:
            return self._original
        return self.gray


def pil_to_gray(image: Image.Image) -> np.ndarray:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        # Flatten transparency on white so transparent areas don't turn black.
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image)
    return np.array(image.convert("L"))


def _odd(value: float, minimum: int = 3) -> int:
    value = max(minimum, int(round(value)))
    return value if value % 2 else value + 1


def _text_mask(gray: np.ndarray) -> np.ndarray:
    """Mask where text (dark) pixels are 255.

    Uses a local (adaptive) threshold so shadows and uneven lighting are not
    mistaken for text, and a median blur so sensor noise is not either.
    """
    smoothed = cv2.medianBlur(gray, 3)
    block = _odd(min(gray.shape[:2]) / 25, minimum=31)
    mask = cv2.adaptiveThreshold(
        smoothed, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 15
    )
    return mask


def is_inverted(gray: np.ndarray) -> bool:
    """True when the page looks like light text on a dark background.

    The background dominates any page, so its typical brightness decides.
    """
    small = _downscale(gray, 1000)
    return float(np.median(small)) < 100


def _downscale(gray: np.ndarray, max_side: int) -> np.ndarray:
    longest = max(gray.shape[:2])
    if longest <= max_side:
        return gray
    scale = max_side / longest
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def estimate_text_height(gray: np.ndarray) -> float | None:
    """Median height of character-like connected components, in pixels."""
    longest = max(gray.shape[:2])
    factor = 1.0
    if longest > 3000:
        factor = 3000 / longest
        gray = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)

    mask = _text_mask(gray)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count < 2:
        return None
    heights = stats[1:, cv2.CC_STAT_HEIGHT].astype(float)
    widths = stats[1:, cv2.CC_STAT_WIDTH].astype(float)
    areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
    char_like = (
        (heights >= 4)
        & (heights <= gray.shape[0] * 0.08)
        & (widths <= heights * 2.5)
        & (areas >= 6)
    )
    if char_like.sum() < 15:
        return None
    return float(np.median(heights[char_like])) / factor


def rescale_for_ocr(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Resize so the median character height is close to TARGET_TEXT_HEIGHT."""
    text_height = estimate_text_height(gray)
    longest = max(gray.shape[:2])
    if text_height is None:
        # Fall back to a size heuristic when no text-like shapes are found.
        if longest < 1500:
            scale = min(2.5, 2000 / longest)
        else:
            scale = 1.0
    elif text_height < TARGET_TEXT_HEIGHT * 0.75:
        scale = min(3.0, TARGET_TEXT_HEIGHT / text_height)
    elif text_height > TARGET_TEXT_HEIGHT * 2.2:
        scale = max(0.4, (TARGET_TEXT_HEIGHT * 1.4) / text_height)
    else:
        scale = 1.0

    scale = min(scale, MAX_SIDE / longest)
    if abs(scale - 1.0) < 0.08:
        return gray, 1.0
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=interpolation)
    return resized, scale


def detect_orientation(gray: np.ndarray) -> int:
    """Degrees (clockwise) the page must be rotated to be upright; 0 if unsure."""
    try:
        osd = pytesseract.image_to_osd(
            _downscale(gray, 2500),
            config="--psm 0 -c min_characters_to_try=10",
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return 0  # not enough text, or OSD data not installed
    rotate = int(osd.get("rotate", 0)) % 360
    confidence = float(osd.get("orientation_conf", 0))
    if rotate in (90, 180, 270) and confidence >= 1.5:
        return rotate
    return 0


def rotate_right_angle(gray: np.ndarray, degrees_clockwise: int) -> np.ndarray:
    codes = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    return cv2.rotate(gray, codes[degrees_clockwise]) if degrees_clockwise in codes else gray


def estimate_skew(gray: np.ndarray, max_angle: float = 10.0) -> float:
    """Angle (degrees, counter-clockwise positive) that makes text lines level.

    Searches for the rotation that maximises the variance of the horizontal
    projection profile, which peaks when text lines are perfectly horizontal.
    """
    small = _downscale(gray, 1200)
    mask = _text_mask(small)
    if mask.mean() < 1:  # blank page
        return 0.0
    height, width = mask.shape
    centre = (width / 2, height / 2)

    def score(angle: float) -> float:
        matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
        rotated = cv2.warpAffine(
            mask, matrix, (width, height), flags=cv2.INTER_NEAREST, borderValue=0
        )
        profile = rotated.sum(axis=1, dtype=np.float64)
        return float(np.var(profile))

    coarse = np.arange(-max_angle, max_angle + 0.01, 1.0)
    best = max(coarse, key=score)
    if abs(best) >= max_angle:
        return 0.0  # peak at the search boundary: not a real skew signal
    fine = np.arange(best - 1.0, best + 1.01, 0.1)
    best = max(fine, key=score)
    # Only trust the angle if it is clearly better than leaving the page alone.
    if score(best) < score(0.0) * 1.05:
        return 0.0
    return float(round(best, 2))


def rotate_by_angle(gray: np.ndarray, angle: float) -> np.ndarray:
    """Rotate without cropping corners; new areas are filled with white."""
    height, width = gray.shape
    centre = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_width = int(height * sin + width * cos)
    new_height = int(height * cos + width * sin)
    matrix[0, 2] += new_width / 2 - centre[0]
    matrix[1, 2] += new_height / 2 - centre[1]
    return cv2.warpAffine(
        gray,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def normalize_background(gray: np.ndarray) -> np.ndarray:
    """Remove shadows/uneven lighting by dividing by an estimated background."""
    kernel = np.ones((7, 7), np.uint8)
    background = cv2.dilate(gray, kernel)
    background = cv2.medianBlur(background, 21)
    normalized = cv2.divide(gray, background, scale=255)
    # Stretch contrast so the darkest text is black and the paper is white.
    low, high = np.percentile(normalized, (1, 99))
    if high - low < 10:
        return normalized
    stretched = np.clip((normalized.astype(np.float32) - low) * 255.0 / (high - low), 0, 255)
    return stretched.astype(np.uint8)


def adaptive_binarize(gray: np.ndarray) -> np.ndarray:
    """Noise-tolerant black/white version of a normalised page."""
    denoised = cv2.medianBlur(gray, 3)
    text_height = estimate_text_height(denoised) or TARGET_TEXT_HEIGHT
    block_size = _odd(text_height * 1.5, minimum=15)
    return cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        12,
    )


def prepare_for_ocr(
    image: Image.Image,
    *,
    enhance: bool = True,
    auto_rotate: bool = True,
    deskew: bool = True,
) -> PreparedImage:
    """Run the full preparation pipeline on a page image."""
    gray = pil_to_gray(image)
    notes: list[str] = []

    if not enhance:
        return PreparedImage(gray=gray, notes=notes)

    if is_inverted(gray):
        gray = cv2.bitwise_not(gray)
        notes.append("Inverted light-on-dark text")

    gray, scale = rescale_for_ocr(gray)
    if scale != 1.0:
        notes.append(f"Rescaled ×{scale:.2f} for optimal text size")

    if auto_rotate:
        rotation = detect_orientation(gray)
        if rotation:
            gray = rotate_right_angle(gray, rotation)
            notes.append(f"Rotated {rotation}° to upright")

    if deskew:
        angle = estimate_skew(gray)
        if abs(angle) >= 0.3:
            gray = rotate_by_angle(gray, angle)
            notes.append(f"Straightened {angle:+.1f}° skew")

    original = gray
    normalized = normalize_background(gray)
    return PreparedImage(gray=normalized, notes=notes, _original=original)
