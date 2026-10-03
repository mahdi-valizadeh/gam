from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Letter:
    letter_number: str = ""
    subject: str = ""
    sender: str = ""
    date: str = ""
    referral_type: str = ""
    referral_note: str = ""
    body_text: str = ""
    images: list[Path] = field(default_factory=list)
    attachments: list[Path] = field(default_factory=list)

    @property
    def key(self) -> str:
        """شناسه‌ی پایدار برای جلوگیری از پردازش دوباره."""
        base = self.letter_number or f"{self.subject}|{self.sender}|{self.date}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


@dataclass
class LetterSummary:
    letter: Letter
    summary: str
    referral_type: str
    action_required: str
    priority: str
    deadline: str
    ocr_text: str = ""

    def to_row(self) -> dict:
        row = {k: v for k, v in asdict(self.letter).items() if k not in ("images", "attachments", "body_text")}
        row.update(
            key=self.letter.key,
            summary=self.summary,
            referral_type=self.referral_type or self.letter.referral_type,
            action_required=self.action_required,
            priority=self.priority,
            deadline=self.deadline,
        )
        return row
