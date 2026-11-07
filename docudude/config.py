"""App-wide constants and configuration lookup."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

APP_NAME = "DocuDude"
APP_TAGLINE = "Your friendly scan sidekick"
APP_LOGO_PATH = PROJECT_ROOT / "DocuDude_ Your Friendly Scan Sidekick.png"
AUTHOR = "Huzaifa Ameer"
WHATSAPP_URL = "https://wa.me/94774322192"
WHATSAPP_DISPLAY = "+94 77 432 2192"

SUPPORTED_IMAGES = ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"]
SUPPORTED_TYPES = ["pdf", *SUPPORTED_IMAGES]

PAGES = {
    "home": "Home",
    "extract": "Text extraction",
    "analyze": "AI analysis",
}

OLLAMA_CLOUD_MODELS = [
    "gemma4:31b",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "nemotron-3-super",
    "nemotron-3-ultra",
    "nemotron-3-nano:30b",
    "beam",
]
DEFAULT_MODEL = "gemma4:31b"

PAGE_SEGMENTATION_MODES = {
    "Automatic (documents, multi-column)": 3,
    "Single column of text": 4,
    "Single uniform block": 6,
    "Sparse text (receipts, forms, labels)": 11,
}

ACCURACY_MODE_LABELS = {
    "fast": "Fast",
    "balanced": "Balanced",
    "best": "Best",
}
ACCURACY_MODE_HELP = (
    "Fast runs one OCR pass. Balanced also tries a black-and-white version of "
    "the page and keeps the more confident result. Best adds a third pass and is "
    "slowest; use it for poor scans and photos."
)


def get_setting(name: str, default: str = "") -> str:
    """Read a setting from the environment / .env first, then Streamlit secrets."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except (StreamlitSecretNotFoundError, FileNotFoundError):
        return default
