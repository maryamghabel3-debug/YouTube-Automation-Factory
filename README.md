# 🏭 YouTube Automation Factory

سیستم واقعی (نه mock) برای ساخت خودکار ویدیوهای یوتیوب با فوتیج/عکس رایگان stock + روایت اصیل + صدای TTS + زیرنویس خودکار + آپلود خودکار.

## 🎯 فلسفه
به‌جای تولید کل ویدیو با هوش مصنوعی (که گرون و پرمحدودیت است)، این فکتوری از **فوتیج/عکس رایگان و مجاز-تجاری** (Pexels، Pixabay) به‌عنوان پس‌زمینه بصری یک **روایت اصیل و اصلی** استفاده می‌کند — دقیقاً همان روشی که بسیاری از کانال‌های فیس‌لس موفق یوتیوب استفاده می‌کنند.

## ✅ وضعیت: کاملاً کارکننده (نه اسکلت/بلوپرینت)
هر جزء این پروژه **واقعاً اجرا می‌شود** و خروجی واقعی تولید می‌کند:

| جزء | وضعیت |
|---|---|
| 🔍 NicheAnalyzer | ✅ موضوعات واقعی از Reddit + Google Trends + فیلتر امنیتی محتوای حساس |
| 🏆 CompetitorAnalyzer | ✅ تحلیل ویدیوهای واقعاً پربازدید همین نیچ قبل از نوشتن اسکریپت (الگوی هوک/ریتم، نه کپی محتوا) |
| ✍️ ScriptWriter | ✅ اسکریپت اصیل با زنجیره‌ی ۶ ارائه‌دهنده‌ی هوش مصنوعی رایگان (Groq/Gemini/Kimi K2/OpenRouter/DeepSeek/Moonshot، هرکدوم موجود بود) + fallback آفلاین |
| 🗣 VoiceEngine | ✅ صدای واقعی با edge-tts + زمان‌بندی دقیق کلمه‌به‌کلمه |
| 🎥 StockFootageFetcher | ✅ فوتیج/عکس واقعی از Pexels/Pixabay + امتیازدهی کیفیت واقعی (رزولوشن/نسبت‌ابعاد/تناسب‌زمانی/ارتباط موضوعی، نه انتخاب تصادفی) |
| 🎞 VideoAssembler | ✅ رندر واقعی با FFmpeg: افکت Ken Burns + زیرنویس حک‌شده + میکس صدا |
| 🖼 ThumbnailMaker | ✅ کاور واقعی ۱۲۸۰×۷۲۰ از فریم فوتیج + متن پرکنتراست (بدون نیاز به AI تصویر) |
| 🎞 ShortsMaker | ✅ تولید خودکار ۲-۳ کلیپ Shorts عمودی از هر ویدیوی بلند (بر اساس تشخیص هوک با AI) |
| 🧠 ChannelMemory | ✅ حافظه‌ی دائمی هر کانال — هر ویدیوی ساخته‌شده ثبت می‌شه، جلوگیری از تکرار موضوع |
| 💬 CommentEngager | ✅ جواب خودکار و اختصاصی به کامنت‌های تازه (بلافاصله بعد از آپلود + هر ۴ ساعت) |
| 📤 AutoPublisher | ✅ آپلود واقعی با YouTube Data API v3 (OAuth2) + ست‌کردن تامبنیل سفارشی + کپشن با CTA تعامل‌محور |
| 📊 PerformanceAnalyzer | ✅ آمار واقعی بازدید/لایک از YouTube API |
| 🛡 UsageGuard + ScheduleGuard | ✅ سقف هزینه‌ی روزانه/ماهانه هوش مصنوعی + اجرای واقعی طبق `upload_frequency` |

همه با **۸۴ تست خودکار** پوشش داده شده‌اند (`tests/test_factory.py`) که شامل یک تست end-to-end واقعی (اجرای کامل ffmpeg + edge-tts + تولید تامبنیل و Shorts) است.

جزئیات بیشتر: `docs/HIGH-VIEW-STRATEGY.md` (تحلیل رقبا/تامبنیل/Shorts)، `docs/LLM-PROVIDERS-2026.md` (ارائه‌دهنده‌های هوش مصنوعی + سقف هزینه)، و `docs/YOUTUBE-GROWTH-AND-ENGAGEMENT.md` (تحقیق کامل رشد/درآمد یوتیوب + معیار کیفیت فوتیج).

## 💰 هزینه: تقریباً $۰ در ماه
تمام سرویس‌های استفاده‌شده رایگان و بدون نیاز به کارت بانکی بین‌المللی هستند (فقط ثبت‌نام ایمیلی).

## 🤖 کنترل کامل از تلگرام — بدون باز کردن گیت‌هاب

از این به بعد کل چرخه کار (اضافه کردن کانال جدید، وصل کردن اکانت یوتیوب، ساخت ویدیوی تستی، دریافت نتیجه) از طریق چت با یک بات تلگرام مستقل (`scripts/factory_bot.py`، جدا از بات پروژه elina-radman) انجام می‌شه:

```
/newchannel        ← نیچ + زبان + اسم کانال رو بپرس و ثبت کن
/oauth <id>        ← اتصال واقعی به یوتیوب (بدون مرورگر روی سرور؛ فقط یک لینک+کد که خودتون تأیید می‌کنید)
/testvideo <id>    ← ساخت یک ویدیوی تستی (بدون آپلود) و ارسال نتیجه
/makevideo <id>    ← ساخت + آپلود واقعی
/channels /status /pause /resume /remove /runall /help
```

راه‌اندازی این بات: `docs/YOUTUBE-OAUTH-SETUP.md` (بخش «راه‌اندازی خود بات»).

ویدیوهای ساخته‌شده، بسته به حجم، مستقیم توی تلگرام ارسال می‌شن یا (اگه حجمشون زیاد باشه، یا صراحتاً بخواید) به‌صورت لینک دانلود دائمی روی **GitHub Releases** آپلود می‌شن.

## 🚀 شروع سریع (روش دستی/خط‌فرمان، به‌عنوان جایگزین بات)

```bash
pip install -r requirements.txt
# ffmpeg باید نصب باشه: sudo apt-get install ffmpeg

# ۱. یک کانال ثبت کن
python core/channel_spawner.py

# ۲. یک‌بار OAuth یوتیوب رو تنظیم کن (راهنما: docs/YOUTUBE-OAUTH-SETUP.md)
python scripts/setup_youtube_oauth.py

# ۳. فکتوری رو اجرا کن (بدون آپلود، فقط تست ساخت ویدیو)
SKIP_UPLOAD=1 TARGET_MINUTES=2 python main.py

# ۴. اجرای کامل با آپلود واقعی
python main.py
```

برای اجرای خودکار روزانه، ورک‌فلوی `.github/workflows/run-factory.yml` رو با کلیدهای لازم در GitHub Secrets فعال کنید — راهنمای کامل در `docs/YOUTUBE-OAUTH-SETUP.md`.

## 🗂 ساختار

```
YouTube-Automation-Factory/
├── main.py                        ← ارکستریتور اصلی (The CEO)
├── core/
│   ├── content_config.py          ← نیچ‌ها، صداها، تنظیمات مشترک
│   ├── niche_analyzer.py          ← موضوع‌یابی واقعی (Reddit) + فیلتر امنیتی
│   ├── script_writer.py           ← اسکریپت‌نویسی با Gemini
│   ├── voice_engine.py            ← صدا با edge-tts + زمان‌بندی کلمه
│   ├── stock_footage_fetcher.py   ← فوتیج/عکس از Pexels/Pixabay
│   ├── video_assembler.py         ← رندر نهایی با FFmpeg
│   ├── video_factory.py           ← اتصال همه اجزا به هم
│   ├── channel_spawner.py         ← ثبت/مدیریت کانال (شامل pause/resume/remove)
│   ├── auto_publisher.py          ← آپلود واقعی به یوتیوب (OAuth2)
│   ├── performance_analyzer.py    ← آمار واقعی بازدید/عملکرد
│   ├── oauth_device.py            ← اتصال یوتیوب بدون مرورگر روی سرور (device flow)
│   ├── gh_secrets.py              ← نوشتن خودکار GitHub Secrets (رمزنگاری‌شده)
│   ├── gh_release.py              ← تحویل ویدیو به‌صورت لینک دانلود (GitHub Release)
│   ├── gh_actions.py              ← اجرای فوری فکتوری از راه دور (workflow_dispatch)
│   ├── workflow_editor.py         ← افزودن خودکار سکرت جدید به فایل ورک‌فلو
│   ├── pending_setups.py          ← وضعیت اتصال‌های یوتیوب در حال انتظار
│   └── telegram_notify.py         ← اطلاع‌رسانی نتیجه به تلگرام
├── channels/database.json         ← دیتابیس کانال‌های فعال
├── scripts/
│   ├── factory_bot.py             ← بات تلگرام کنترل‌پنل فکتوری (روش اصلی)
│   ├── add_channel_wizard.py      ← ویزارد خط‌فرمان (جایگزین بات)
│   └── setup_youtube_oauth.py     ← تنظیم دستی OAuth (جایگزین بات)
├── docs/YOUTUBE-OAUTH-SETUP.md    ← راهنمای کامل قدم‌به‌قدم
├── docs/ADDING-A-NEW-CHANNEL.md   ← راهنمای اضافه کردن کانال/نیچ/زبان جدید
└── tests/test_factory.py          ← ۲۹ تست خودکار (شامل end-to-end واقعی)
```

## 📄 اسناد بیشتر
- `GAZARESH-BARRASI-CHETOR-EJRA-KONIM.md` — گزارش بررسی نسخه اولیه (بلوپرینت mock)
- `PLAN-VIDEO-BA-FOOTAGE-AMADEH.md` — استراتژی کلی و تحقیق بازار (RPM نیچ‌ها، منابع فوتیج، قوانین یوتیوب)
- `docs/YOUTUBE-OAUTH-SETUP.md` — راه‌اندازی آپلود خودکار + راه‌اندازی بات
- `docs/ADDING-A-NEW-CHANNEL.md` — اضافه کردن کانال/نیچ/زبان جدید

