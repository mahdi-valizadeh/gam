"""خواندن (OCR) و خلاصه‌سازی نامه با Claude."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import anthropic

from .config import Settings
from .models import Letter, LetterSummary
from .ocr import IMAGE_EXT, ocr_letter

log = logging.getLogger(__name__)

SYSTEM = """شما دستیار اداری یک مدیر محصول در شرکت تامین ICT هستید.
نامه‌های اداری فارسی (معمولاً اسکن‌شده) از سامانه‌ی اتوماسیون اداری «گام» به شما داده می‌شود.
کارتان:
1. متن نامه را کامل و دقیق بخوانید (در صورت تصویر بودن، OCR کنید) و در transcript بنویسید.
2. نوع ارجاعی که به کاربر خورده را مشخص کنید (مثلاً «جهت اقدام»، «جهت اطلاع»، «جهت بررسی و اظهارنظر»، «جهت پیگیری»، «جهت هماهنگی»).
   اگر اطلاعات ارجاع جداگانه داده شده، اولویت با آن است.
3. یک خلاصه‌ی ۲ تا ۳ جمله‌ای فارسی بنویسید: موضوع، فرستنده، درخواست اصلی.
4. اقدامی که از کاربر خواسته شده را مشخص کنید؛ اگر صرفاً اطلاع‌رسانی است بنویسید «اقدامی لازم نیست».
5. اولویت: «فوری»، «بالا»، «عادی» یا «کم». مهلت را اگر در نامه آمده بنویسید، وگرنه رشته‌ی خالی.
هیچ اطلاعاتی از خودتان اضافه نکنید؛ اگر بخشی ناخوانا بود صریحاً بگویید."""

SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"},
        "referral_type": {"type": "string"},
        "summary": {"type": "string"},
        "action_required": {"type": "string"},
        "priority": {"type": "string", "enum": ["فوری", "بالا", "عادی", "کم"]},
        "deadline": {"type": "string"},
    },
    "required": ["transcript", "referral_type", "summary", "action_required", "priority", "deadline"],
    "additionalProperties": False,
}

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}


def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")


def _file_blocks(files: list[Path]) -> list[dict]:
    blocks: list[dict] = []
    for f in files:
        suffix = f.suffix.lower()
        if suffix in MEDIA_TYPES:
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": MEDIA_TYPES[suffix], "data": _b64(f)}})
        elif suffix == ".pdf":
            blocks.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": _b64(f)}})
    return blocks


def _metadata(letter: Letter) -> str:
    return (
        f"شماره نامه: {letter.letter_number}\n"
        f"موضوع (از کارتابل): {letter.subject}\n"
        f"فرستنده: {letter.sender}\n"
        f"تاریخ: {letter.date}\n"
        f"نوع ارجاع (از کارتابل): {letter.referral_type}\n"
        f"اطلاعات ارجاع / پی‌نوشت: {letter.referral_note}\n"
    )


class Summarizer:
    def __init__(self, settings: Settings):
        self.client = anthropic.Anthropic()
        self.model = settings.get("summary.model", "claude-opus-5-5")
        self.effort = settings.get("summary.effort", "medium")
        self.engine = settings.get("ocr.engine", "claude")
        self.lang = settings.get("ocr.tesseract_lang", "fas+eng")

    def summarize(self, letter: Letter) -> LetterSummary:
        files = letter.images + letter.attachments
        content: list[dict] = []
        ocr_text = ""

        if self.engine == "tesseract":
            ocr_text = ocr_letter([f for f in files if f.suffix.lower() in IMAGE_EXT | {".pdf"}], self.lang)
            text_part = f"متن OCR شده‌ی نامه:\n{ocr_text}"
        else:
            content.extend(_file_blocks(files))
            text_part = "تصویر/فایل نامه در بالا آمده است."

        if letter.body_text:
            text_part += f"\n\nمتن قابل استخراج از صفحه:\n{letter.body_text}"
        content.append({"type": "text", "text": f"{_metadata(letter)}\n{text_part}"})

        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

        if response.stop_reason == "refusal":
            log.warning("Claude نامه‌ی %s را پردازش نکرد", letter.subject)
            return LetterSummary(letter, "پردازش نشد (refusal)", letter.referral_type, "دستی بررسی شود", "عادی", "", ocr_text)
        if response.stop_reason == "max_tokens":
            log.warning("پاسخ نامه‌ی %s ناقص ماند", letter.subject)

        text = next((b.text for b in response.content if b.type == "text"), "{}")
        data = json.loads(text)
        return LetterSummary(
            letter=letter,
            summary=data["summary"],
            referral_type=data["referral_type"],
            action_required=data["action_required"],
            priority=data["priority"],
            deadline=data["deadline"],
            ocr_text=ocr_text or data["transcript"],
        )
