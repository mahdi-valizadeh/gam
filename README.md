# دستیار کارتابل گام (gam-inbox-assistant)

ابزاری که روی **سیستم کاری خودتان** (داخل شبکه‌ی سازمان) اجرا می‌شود و:

1. وارد اتوماسیون اداری «گام» می‌شود.
2. نامه‌های نخوانده‌ی کارتابل را یکی‌یکی باز می‌کند.
3. نوع ارجاع، ارجاع‌دهنده و پی‌نوشت ارجاع را برمی‌دارد.
4. تصویر یا PDF نامه را OCR می‌کند: یا Claude مستقیم از روی تصویر می‌خواند، یا Tesseract محلی.
5. با Claude یک خلاصه‌ی کوتاه می‌سازد و اقدام لازم، اولویت و مهلت را درمی‌آورد.
6. لیست نامه‌های رسیدگی‌نشده را به‌صورت **صفحه‌ی HTML راست‌به‌چپ** و **فایل Excel** تحویل می‌دهد.

> ⚠️ **تذکر مهم:** در بیشتر اتوماسیون‌ها باز کردن نامه آن را «خوانده‌شده» علامت می‌زند. به همین دلیل
> این ابزار لیست خودش را نگه می‌دارد (`output/state.json`) و هر نامه تا وقتی با دستور `done` علامت نزنید در گزارش می‌ماند.

> 🔒 **امنیت:** رمز عبور فقط در فایل `.env` روی سیستم خودتان ذخیره می‌شود و در git نمی‌رود.
> متن و تصویر نامه‌ها برای OCR و خلاصه‌سازی به API شرکت Anthropic ارسال می‌شود؛ قبل از استفاده
> از واحد امنیت فناوری اطلاعات تأیید بگیرید. با `ocr.engine: tesseract` فقط متن OCR‌شده ارسال می‌شود، نه تصویر.

## نصب (یک بار)

```bash
python -m venv .venv
.venv\Scripts\activate            # ویندوز   (لینوکس/مک: source .venv/bin/activate)
pip install -r requirements.txt
playwright install chromium       # یا در config.yaml مقدار browser.channel را "msedge" بگذارید
copy config.example.yaml config.yaml   # لینوکس/مک: cp
copy .env.example .env
```

بعد فایل `.env` را پر کنید:

```
GAM_USERNAME=نام کاربری گام
GAM_PASSWORD=رمز گام
ANTHROPIC_API_KEY=کلید API از console.anthropic.com
```

برای OCR محلی (اختیاری): [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) را با بسته‌ی زبان فارسی (`fas`) و
[Poppler](https://github.com/oschwartz10612/poppler-windows) را برای PDF نصب کنید.

## تنظیم selectorها (یک بار)

ساختار HTML صفحات گام را از بیرون شبکه نمی‌شد دید، پس selectorهای `config.yaml` حدسی هستند. برای تنظیمشان:

```bash
python -m gam_assistant inspect
```

مرورگر باز می‌شود. وارد شوید، به کارتابل بروید و یک نامه را باز کنید. از هر مرحله HTML و اسکرین‌شات در
`output/inspect/` ذخیره می‌شود. با این فایل‌ها (بعد از حذف اطلاعات محرمانه) selectorهای بخش `gam.inbox` و `gam.letter` را اصلاح کنید.
می‌توانید این فایل‌ها را به Claude بدهید تا selectorها را برایتان بنویسد.

## استفاده‌ی روزانه

```bash
python -m gam_assistant run          # خواندن و خلاصه‌ی نامه‌های نخوانده‌ی جدید + ساخت گزارش
python -m gam_assistant report       # ساخت دوباره‌ی گزارش بدون ورود به گام
python -m gam_assistant done <KEY>   # حذف نامه‌ی رسیدگی‌شده از لیست (KEY در state.json)
python -m gam_assistant summarize-file scan.pdf   # خلاصه‌ی یک فایل نامه بدون ورود به گام
```

خروجی: `output/unread-YYYYMMDD-HHMM.html` و `.xlsx`، مرتب‌شده بر اساس اولویت (فوری ← کم).

## ساختار

| فایل | کار |
|---|---|
| `gam_assistant/browser.py` | ورود، کارتابل، باز کردن نامه، اسکرین‌شات و دانلود پیوست (Playwright) |
| `gam_assistant/ocr.py` | OCR محلی با Tesseract |
| `gam_assistant/summarize.py` | OCR و خلاصه با Claude (خروجی ساختاریافته‌ی JSON) |
| `gam_assistant/report.py` | گزارش HTML و Excel و نگه‌داری وضعیت |
| `config.example.yaml` | آدرس‌ها، selectorها، موتور OCR، مدل |

## قدم‌های بعدی

- اجرای خودکار هر صبح با Task Scheduler ویندوز (`python -m gam_assistant run`)
- ارسال خلاصه به پیام‌رسان داخلی یا ایمیل
- دسته‌بندی نامه‌ها بر اساس پروژه یا تیم، برای تقسیم کار بین اعضای تیم
