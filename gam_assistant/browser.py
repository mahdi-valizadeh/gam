"""ورود به گام و جمع‌آوری نامه‌های نخوانده با Playwright."""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, Frame, Locator, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .config import Settings
from .models import Letter

log = logging.getLogger(__name__)


@contextmanager
def open_browser(settings: Settings) -> Iterator[Page]:
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=settings.get("browser.headless", False),
            slow_mo=settings.get("browser.slow_mo_ms", 0),
            executable_path=settings.get("browser.executable_path") or None,
            channel=settings.get("browser.channel") or None,
        )
        context = browser.new_context(locale="fa-IR", accept_downloads=True)
        context.set_default_timeout(settings.get("browser.timeout_ms", 30000))
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()


def login(page: Page, settings: Settings) -> None:
    page.goto(settings.get("gam.login_url"))
    sel = settings.get("gam.login")
    page.locator(sel["username_selector"]).first.fill(settings.username)
    page.locator(sel["password_selector"]).first.fill(settings.password)
    page.locator(sel["submit_selector"]).first.click()
    try:
        page.wait_for_selector(sel["logged_in_selector"])
    except PlaywrightTimeout as exc:
        raise SystemExit(
            "ورود ناموفق بود یا selector مربوط به صفحه‌ی بعد از ورود درست نیست "
            "(gam.login.logged_in_selector). اگر کپچا دارد، browser.headless را false بگذارید "
            "و کپچا را دستی وارد کنید."
        ) from exc
    log.info("ورود موفق")


def open_inbox(page: Page, settings: Settings) -> None:
    inbox_url = settings.get("gam.inbox_url")
    if inbox_url:
        page.goto(inbox_url)
    for step in settings.get("gam.inbox.open_steps", []) or []:
        page.locator(step).first.click()
    page.wait_for_load_state("networkidle")


def _text(scope: Page | Frame | Locator, selector: str) -> str:
    if not selector:
        return ""
    loc = scope.locator(selector)
    if loc.count() == 0:
        return ""
    return re.sub(r"\s+", " ", loc.first.inner_text()).strip()


def _inbox_frame(page: Page, row_selector: str) -> Page | Frame:
    """کارتابل‌های قدیمی معمولاً داخل iframe هستند؛ فریمی که ردیف‌ها را دارد پیدا می‌کنیم."""
    if page.locator(row_selector).count():
        return page
    for frame in page.frames:
        try:
            if frame.locator(row_selector).count():
                return frame
        except Exception:  # فریم‌های cross-origin
            continue
    return page


def collect_unread(page: Page, settings: Settings, skip_keys: set[str]) -> list[Letter]:
    inbox = settings.get("gam.inbox")
    letter_cfg = settings.get("gam.letter")
    out_dir = settings.output_dir / "letters"
    out_dir.mkdir(parents=True, exist_ok=True)
    max_letters = int(inbox.get("max_letters", 50))
    letters: list[Letter] = []

    while len(letters) < max_letters:
        scope = _inbox_frame(page, inbox["row_selector"])
        row_sel = inbox.get("unread_row_selector") or inbox["row_selector"]
        rows = scope.locator(row_sel)
        count = rows.count()
        log.info("%d ردیف نخوانده در این صفحه", count)

        for i in range(count):
            if len(letters) >= max_letters:
                break
            scope = _inbox_frame(page, inbox["row_selector"])
            row = scope.locator(row_sel).nth(i)
            cols = inbox["columns"]
            letter = Letter(**{name: _text(row, sel) for name, sel in cols.items()})
            if letter.key in skip_keys:
                log.info("قبلاً پردازش شده: %s", letter.subject)
                continue
            _read_letter(page, row, letter, letter_cfg, inbox, out_dir)
            letters.append(letter)

        next_sel = inbox.get("next_page_selector")
        if not next_sel:
            break
        nxt = _inbox_frame(page, inbox["row_selector"]).locator(next_sel)
        if nxt.count() == 0 or not nxt.first.is_enabled():
            break
        nxt.first.click()
        page.wait_for_load_state("networkidle")

    return letters


def _read_letter(page: Page, row: Locator, letter: Letter, cfg: dict, inbox: dict, out_dir: Path) -> None:
    target = row.locator(inbox["open_letter_selector"]).first
    if cfg.get("opens_in_popup"):
        with page.expect_popup() as popup_info:
            target.click()
        view = popup_info.value
    else:
        target.click()
        view = page
    view.wait_for_load_state("networkidle")

    letter_dir = out_dir / letter.key
    letter_dir.mkdir(parents=True, exist_ok=True)

    letter.referral_note = _text(view, cfg.get("referral_info_selector", ""))
    body = view.locator(cfg["body_selector"]).first if view.locator(cfg["body_selector"]).count() else None
    if body is not None:
        try:
            letter.body_text = body.inner_text().strip()
        except Exception:
            pass
        shot = letter_dir / "body.png"
        body.screenshot(path=str(shot))
    else:
        shot = letter_dir / "page.png"
        view.screenshot(path=str(shot), full_page=True)
    letter.images.append(shot)

    _download_attachments(view, cfg.get("attachment_selector", ""), letter, letter_dir)
    _close_letter(page, view, cfg)


def _download_attachments(view: Page, selector: str, letter: Letter, letter_dir: Path) -> None:
    if not selector:
        return
    links = view.locator(selector)
    for i in range(links.count()):
        try:
            with view.expect_download() as dl_info:
                links.nth(i).click()
            dl = dl_info.value
            dest = letter_dir / dl.suggested_filename
            dl.save_as(str(dest))
            letter.attachments.append(dest)
        except PlaywrightTimeout:
            log.warning("دانلود پیوست %d انجام نشد", i + 1)


def _close_letter(page: Page, view: Page, cfg: dict) -> None:
    if view is not page:
        view.close()
        return
    close_sel = cfg.get("close_selector")
    if close_sel and page.locator(close_sel).count():
        page.locator(close_sel).first.click()
    else:
        page.go_back()
    page.wait_for_load_state("networkidle")


def inspect(page: Page, settings: Settings) -> Path:
    """برای تنظیم selectorها: از هر صفحه HTML و اسکرین‌شات ذخیره می‌کند."""
    dump = settings.output_dir / "inspect"
    dump.mkdir(parents=True, exist_ok=True)

    def save(name: str) -> None:
        page.screenshot(path=str(dump / f"{name}.png"), full_page=True)
        (dump / f"{name}.html").write_text(page.content(), encoding="utf-8")
        for idx, frame in enumerate(page.frames[1:], start=1):
            try:
                (dump / f"{name}.frame{idx}.html").write_text(frame.content(), encoding="utf-8")
            except Exception:
                pass

    page.goto(settings.get("gam.login_url"))
    save("01-login")
    input("وارد شوید و به کارتابل نامه‌های نخوانده بروید، بعد Enter بزنید... ")
    save("02-inbox")
    input("یک نامه را باز کنید و Enter بزنید... ")
    save("03-letter")
    return dump
