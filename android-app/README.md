# Android App - شکار سهام - مثل اپ فراز
این اپ اندروید مثل اپ فراز یک WebView wrapper است.

## روش ساخت (برای استفاده شخصی)

### روش 1: PWA - ساده (مثل فراز)
1. سایت رو روی https دیپلوی کن
2. روی اندروید با Chrome باز کن
3. منو -> Add to Home Screen -> نصب میشه مثل اپ نیتیو

### روش 2: Capacitor
npm install -g @capacitor/cli
npx cap add android
npx cap copy
# Build APK in Android Studio

### روش 3: TWA - مثل فراز
bubblewrap init --manifest https://your-site.com/manifest.json
bubblewrap build

برای استفاده شخصی، روش 1 (PWA) کافیه.
