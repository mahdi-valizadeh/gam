"""OCR محلی با Tesseract (زبان فارسی). فقط وقتی ocr.engine = tesseract باشد استفاده می‌شود."""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}


def ocr_file(path: Path, lang: str = "fas+eng") -> str:
    import pytesseract
    from PIL import Image

    suffix = path.suffix.lower()
    if suffix in IMAGE_EXT:
        return pytesseract.image_to_string(Image.open(path), lang=lang)
    if suffix == ".pdf":
        from pdf2image import convert_from_path

        pages = convert_from_path(str(path), dpi=300)
        return "\n\n".join(pytesseract.image_to_string(p, lang=lang) for p in pages)
    log.info("فرمت پشتیبانی نمی‌شود برای OCR: %s", path.name)
    return ""


def ocr_letter(files: list[Path], lang: str) -> str:
    parts = []
    for f in files:
        text = ocr_file(f, lang).strip()
        if text:
            parts.append(f"--- {f.name} ---\n{text}")
    return "\n\n".join(parts)
