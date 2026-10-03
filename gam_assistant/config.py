from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class Settings:
    raw: dict[str, Any]
    username: str
    password: str

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def output_dir(self) -> Path:
        path = Path(self.get("output.dir", "output"))
        path.mkdir(parents=True, exist_ok=True)
        return path


def load_settings(config_path: str = "config.yaml") -> Settings:
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        raise SystemExit(
            f"فایل تنظیمات {config_path} پیدا نشد. config.example.yaml را به config.yaml کپی کنید."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    username = os.environ.get("GAM_USERNAME", "")
    password = os.environ.get("GAM_PASSWORD", "")
    if not username or not password:
        raise SystemExit("GAM_USERNAME و GAM_PASSWORD را در فایل .env تنظیم کنید.")
    return Settings(raw=raw, username=username, password=password)
