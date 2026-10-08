# Сборка APK

В песочнице, где писался код, нет JDK и Android SDK, поэтому сборка не проверялась машиной.
Ниже — порядок действий и список мест, которые обычно правятся после первого Sync.

## 1. Инструменты

* Android Studio Ladybug (2024.2) или новее — вместе с ней JDK 17 и Android SDK.
* Нужные пакеты SDK: Platform Tools, **Android 35 (SDK 35)**, Build-Tools 35.0.0.
* В `android/` нет `gradle-wrapper.jar` (бинарники в репозиторий не коммитим) и `local.properties`.
  Проще всего дать Studio сгенерировать обёртку: *File → Sync Project with Gradle Files*,
  либо из каталога `android/`: `gradle wrapper --gradle-version 8.9`.

## 2. Первый запуск

```bash
cd android
./gradlew :app:testDebugUnitTest      # домен и парсер: планирование, риск-модель, офлайн-движок, CSV
./gradlew :app:assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug                # на подключённый телефон (adb devices)
```

Release: `./gradlew :app:assembleRelease` после того, как в `app/build.gradle.kts` добавлен
`signingConfig` (ключ держать вне репозитория).

## 3. Что проверить после Sync

1. **Версии.** В `android/build.gradle.kts` — AGP 8.7.3 / Kotlin 2.0.21; в `app/build.gradle.kts` —
   Compose BOM 2024.10.01, compileSdk 35. Если Studio предложит апгрейд — соглашаться и перепроверить
   `androidx.compose.material3.*`: в `material3 1.3` `LinearProgressIndicator(progress = { … })` —
   лямбда-перегрузка (в коде используется она).
2. **Иконки.** `ic_launcher` объявлен только как adaptive-icon (`mipmap-anydpi-v26`), минимальный API 26 —
   этого достаточно. Для Play Console понадобится растровый вариант, генерируется
   *New → Image Asset* поверх `res/drawable/ic_launcher_foreground.xml`.
3. **Строка версии/namespace** — `work.day.app`; перед публикацией в Google Play замени `applicationId`
   на свой домен.
4. **`enableEdgeToEdge()`** требует `androidx.activity:activity-compose:1.9+` (уже в зависимостях).

## 4. Подключение модели и площадок

* Настройки → «Модель для генерации»: вкл/выкл, `baseURL` (OpenAI-совместимый), ключ, имя модели, кнопка
  «Проверить». Без ключа всё работает на офлайн-движке, тексты помечаются как шаблонные.
* ID канала YouTube (UC…) + ключ **YouTube Data API v3** с правами только на чтение → «Подтянуть статистику».
  Для продакшена лучше OAuth (Consent → `https://www.googleapis.com/auth/yt-analytics.readonly`),
  тогда в аналитику попадут удержание и источники трафика, а не только публичные счётчики.
* TikTok: официальных read-only API для сторонних приложений нет — цифры вставляются CSV из
  TikTok Studio → Analytics (парсер терпим к «;»/«»,» и к датам `дд.мм.гггг`).
