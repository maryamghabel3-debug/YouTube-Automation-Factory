# 🔐 راه‌اندازی آپلود خودکار یوتیوب (یک‌بار برای همیشه، برای هر کانال)

این مرحله باید **یک‌بار** برای هر کانال یوتیوب (با مرورگر، دستی) انجام بشه. بعدش برای همیشه (روی GitHub Actions، بدون مرورگر) کار می‌کنه.

## چرا این مرحله لازمه؟
کلید ساده (`YOUTUBE_API_KEY`) که از قبل دارید فقط برای *خوندن* اطلاعات عمومی کار می‌کنه (جستجو، آمار). برای *آپلود* ویدیو، یوتیوب به یک هویت واقعی (OAuth2) نیاز داره که یک‌بار تأیید بشه.

## مرحله ۱: ساخت پروژه گوگل کلاود (یک‌بار، برای همه کانال‌ها مشترک)
1. برید به [console.cloud.google.com](https://console.cloud.google.com)
2. یک پروژه جدید بسازید (یا از پروژه‌ای که برای `YOUTUBE_API_KEY` ساختید استفاده کنید)
3. از منو: **APIs & Services → Library** → دنبال `YouTube Data API v3` بگردید → **Enable**

## مرحله ۲: ساخت OAuth Client ID (یک‌بار)
1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. اگه اولین باره، باید **OAuth consent screen** رو تنظیم کنید:
   - User Type: External
   - App name: هرچی (مثلاً "My Video Factory")
   - Scopes: نیازی به اضافه کردن دستی نیست
   - Test users: ایمیل گوگلی که مالک کانال‌های یوتیوبه رو اضافه کنید
3. Application type: **Desktop app**
4. بعد از ساخته شدن، **Client ID** و **Client Secret** رو کپی کنید

### ⚠️ مهم: از حالت Testing به Production ببرید
اگه اپ در حالت "Testing" بمونه، refresh token بعد از ۷ روز منقضی می‌شه. برای همیشگی شدنش:
- **OAuth consent screen → Publish App**

## مرحله ۳: گرفتن Refresh Token برای هر کانال (یک‌بار برای هر کانال)
روی کامپیوتر خودتون (نه سرور، چون به مرورگر نیاز داره):

```bash
cd YouTube-Automation-Factory
pip install -r requirements.txt
python scripts/setup_youtube_oauth.py
```

- Client ID و Client Secret رو که در مرحله ۲ گرفتید وارد کنید
- یک اسم مستعار برای کانال بدید (مثلاً `ELINA` یا `LUXE`)
- مرورگر باز می‌شه؛ با اکانت گوگلی که **مالک همون کانال یوتیوب** هست وارد بشید و اجازه بدید
- در نهایت این خروجی رو می‌گیرید:

```
YOUTUBE_OAUTH_CLIENT_ID = ...
YOUTUBE_OAUTH_CLIENT_SECRET = ...
YOUTUBE_REFRESH_TOKEN_ELINA = ...
```

## مرحله ۴: اضافه کردن به GitHub Secrets
به ریپازیتوری بروید: **Settings → Secrets and variables → Actions → New repository secret**

هر سه مقدار بالا رو اضافه کنید. برای کانال دوم، فقط کافیه دوباره مرحله ۳ رو با اسم مستعار متفاوت (مثلاً `LUXE`) تکرار کنید و `YOUTUBE_REFRESH_TOKEN_LUXE` رو اضافه کنید (Client ID/Secret یکی می‌مونه، چون هر دو کانال از یک پروژه گوگل استفاده می‌کنن).

## مرحله ۵: ثبت کانال در فکتوری
```bash
python core/channel_spawner.py
```
و وقتی از `refresh_token_env` پرسید، دقیقاً همون اسمی که در Secrets گذاشتید رو بدید (مثلاً `YOUTUBE_REFRESH_TOKEN_ELINA`).

---

## 🔑 سایر کلیدهای رایگان مورد نیاز (بدون کارت بانکی)

| سرویس | برای چی | لینک ثبت‌نام |
|---|---|---|
| Pexels | فوتیج/عکس رایگان | https://www.pexels.com/api/ |
| Pixabay | فوتیج/عکس رایگان (پشتیبان) | https://pixabay.com/api/docs/ |
| Gemini | نوشتن اسکریپت اصیل | https://aistudio.google.com |

این‌ها رو هم به‌عنوان `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `GEMINI_API_KEY` در GitHub Secrets اضافه کنید.
