"""دستیار کارتابل گام.

دستورها:
  python -m gam_assistant inspect        ذخیره‌ی HTML و اسکرین‌شات صفحات برای تنظیم selectorها
  python -m gam_assistant run            ورود، خواندن نامه‌های نخوانده، خلاصه‌سازی و ساخت گزارش
  python -m gam_assistant report         ساخت دوباره‌ی گزارش از نامه‌های ذخیره‌شده
  python -m gam_assistant done KEY...    علامت‌گذاری نامه به‌عنوان رسیدگی‌شده (از لیست حذف می‌شود)
  python -m gam_assistant summarize-file FILE...   خلاصه‌ی یک فایل نامه (تصویر/PDF) بدون ورود به گام
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_settings
from .report import load_state, remember, save_state, write_reports


def _pending_rows(state: dict) -> list[dict]:
    return [row for row in state.values() if not row.get("done")]


def cmd_inspect(settings) -> None:
    from .browser import inspect, open_browser

    with open_browser(settings) as page:
        dump = inspect(page, settings)
    print(f"فایل‌ها در {dump} ذخیره شد. این فایل‌ها را (بعد از حذف اطلاعات محرمانه) برای تنظیم selectorها بفرستید.")


def cmd_run(settings) -> None:
    from .browser import collect_unread, login, open_browser, open_inbox
    from .summarize import Summarizer

    state_path = Path(settings.get("output.state_file", "output/state.json"))
    state = load_state(state_path)
    summarizer = Summarizer(settings)

    with open_browser(settings) as page:
        login(page, settings)
        open_inbox(page, settings)
        letters = collect_unread(page, settings, skip_keys=set(state))

    logging.info("%d نامه‌ی جدید برای خلاصه‌سازی", len(letters))
    for i, letter in enumerate(letters, start=1):
        logging.info("[%d/%d] %s", i, len(letters), letter.subject)
        try:
            remember(state, summarizer.summarize(letter))
        except Exception:
            logging.exception("خطا در خلاصه‌سازی %s", letter.subject)
        save_state(state_path, state)

    _report(settings, state)


def cmd_report(settings) -> None:
    state = load_state(Path(settings.get("output.state_file", "output/state.json")))
    _report(settings, state)


def cmd_done(settings, keys: list[str]) -> None:
    state_path = Path(settings.get("output.state_file", "output/state.json"))
    state = load_state(state_path)
    for key in keys:
        if key in state:
            state[key]["done"] = True
        else:
            print(f"کلید {key} پیدا نشد")
    save_state(state_path, state)
    _report(settings, state)


def cmd_summarize_file(settings, files: list[str]) -> None:
    from .models import Letter
    from .summarize import Summarizer

    summarizer = Summarizer(settings)
    for f in files:
        path = Path(f)
        letter = Letter(subject=path.stem)
        (letter.attachments if path.suffix.lower() == ".pdf" else letter.images).append(path)
        s = summarizer.summarize(letter)
        print(f"\n# {path.name}\nنوع ارجاع: {s.referral_type}\nاولویت: {s.priority}\n"
              f"خلاصه: {s.summary}\nاقدام لازم: {s.action_required}\nمهلت: {s.deadline or '-'}")


def _report(settings, state: dict) -> None:
    rows = _pending_rows(state)
    html_path, xlsx_path = write_reports(rows, settings.output_dir)
    print(f"{len(rows)} نامه در لیست.\nگزارش: {html_path}\nاکسل: {xlsx_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="gam_assistant", description="دستیار کارتابل گام")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inspect")
    sub.add_parser("run")
    sub.add_parser("report")
    done = sub.add_parser("done")
    done.add_argument("keys", nargs="+")
    sf = sub.add_parser("summarize-file")
    sf.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(message)s")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "summarize-file":
        from .config import Settings
        import yaml
        from dotenv import load_dotenv

        load_dotenv()
        raw = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
        cmd_summarize_file(Settings(raw=raw or {}, username="", password=""), args.files)
        return

    settings = load_settings(args.config)
    {
        "inspect": lambda: cmd_inspect(settings),
        "run": lambda: cmd_run(settings),
        "report": lambda: cmd_report(settings),
        "done": lambda: cmd_done(settings, args.keys),
    }[args.cmd]()


if __name__ == "__main__":
    main()
