# Вход в Work Day: Google, TikTok, логин и пароль

Приложение умеет три способа входа. Они независимы: можно не входить никуда и работать
на демо-данных, можно привязать только Google, можно завести аккаунт почтой и паролем.

| Способ | Что даёт | Что запрашивает |
|---|---|---|
| Google (OAuth 2.0 + PKCE) | id канала, название, подписчики, просмотры, удержание — из вашего же канала | `youtube.readonly`, `yt-analytics.readonly` |
| TikTok (Login Kit v2, без SDK) | аватар, ник, `open_id`, подписчики, список роликов | `user.info.basic`, `video.list`, `user.info.stats` (последний — по одобрению) |
| Логин и пароль | аккаунт устройства или облачный аккаунт Firebase | — |

## Чего здесь нет намеренно

- Ни одного scope на публикацию, удаление, редактирование и управление комментариями —
  ни у Google, ни у TikTok. Список прав зашит в `GoogleOAuth.SCOPES` и
  `TikTokOAuth.BASIC_SCOPES`; тест `AuthTest` падает, если туда попадёт слово
  `upload`/`publish`/`update`/`delete`.
- Нет автопостинга и «накрутки»: вход нужен только чтобы **читать** ваши цифры.
  Публикация остаётся ручной — приложение готовит материал и кладёт его в очередь,
  а выкладывает его человек (см. `SafetyPolicy`).
- Токены не уезжают ни в какой наш сервер — его нет. Обмен `code → token` идёт
  с устройства напрямую в `oauth2.googleapis.com` / `open.tiktokapis.com`.

## Поток

```
AuthScreen ──beginLink(provider)──► PendingOAuth { verifier, state, expiresAt } (5 мин)
    │                                     │
    └── Custom Tabs → accounts.google.com  │  code_challenge = BASE64URL(SHA256(verifier))
                    / www.tiktok.com       │
                                           ▼
        https://ваш.pages/auth-callback/  (страница докидывает query в workdayauth://)
                                           ▼
        OAuthRedirectActivity → AuthRepository.completeRedirect(uri)
                                           │  state сверен ДО любого сетевого запроса
                                           ▼
        token exchange → SecureStore (EncryptedSharedPreferences, ключ в Keystore)
                                           ▼
        Session (plain JSON) — только человекочитаемое: email, имя канала, scope, срок
```

Сессия и клиенты лежат в `auth_session.json` и `auth_clients.json` в приватном
`filesDir` приложения: ни один из файлов не читается извне, и ни в одном нет ни токена,
ни пароля, ни хеша.

## 1. Google: что нажать в консоли

1. [console.cloud.google.com](https://console.cloud.google.com) → новый проект, например `work-day`.
2. **APIs & Services → Library** → включить **YouTube Data API v3** (и, если нужны
   источники трафика/удержание, **YouTube Analytics API**).
3. **OAuth consent screen**: External, название, support e-mail. На этапе тестирования
   добавьте свой Google-аккаунт в **Test users** — иначе получите `access_denied` /
   «приложение не проверено».
4. **Credentials → Create credentials → OAuth client ID → тип Android**. Да, именно
   Android: у такого клиента нет секрета, и это правильно — в APK секрет не прячут.
   - Package name: `work.day.app.debug` для отладочной сборки (и `work.day.app` для релизной).
   - SHA-1: `tools/assetlinks.sh` напечата both отпечатки вашего ключа сборки.
   - Скопируйте **Client ID** (`…apps.googleusercontent.com`) — он вставляется в приложение.
5. **APIs & Services → Credentials → Create credentials → API key** — для публичных
   запросов YouTube Data API без токена (в приложении это поле «YouTube API key»).
   Ограничьте ключ по `YouTube Data API v3`.

### Про Redirect URI — важно

Google больше не принимает на Android кастомные схемы (`workdayauth://…`) как
зарегистрированный redirect. Нужен https-адрес, который открывается вашим приложением
через App Link. Самый дешёвый способ — GitHub Pages этого репозитория:

1. **Settings → Pages → Source: Deploy from a branch → `main` + `/docs`**. Save.
   Страница `docs/auth-callback/index.html` станет доступна как
   `https://<user>.github.io/auth-callback/`.
2. Заполните отпечаток в `docs/.well-known/assetlinks.json`:
   `tools/assetlinks.sh` печатает готовый `python3 -` сниппет, который подставляет
   `certificate_sha256`. Проверка: `curl -s https://<user>.github.io/.well-known/assetlinks.json`.
3. В `android/gradle.properties` задайте `workday.authCallbackHost` /
   `workday.authCallbackPath`, если домен не `klavish777.github.io` / `/auth-callback/`.
   Они подставляются в `intent-filter android:autoVerify="true"` манифеста — без совпадения
   хоста Android не отдаст приложению ссылку и вы останетесь на белой вкладке браузера.
4. В настройках приложения в поле **Redirect URI** укажите
   `https://<user>.github.io/auth-callback/` — та же строка должна быть в консоли Google
   (у Android-клиента Google редирект выводится из пакета, но сверяет он его строка в строку).

Если Pages лень: локально всё работает и через `workdayauth://` (activity слушает обе
схемы), просто на шаге 4 оставьте значение по умолчанию — удобно для отладки на своём
устройстве, бесполезно для чужого.

## 2. TikTok

1. [developers.tiktok.com](https://developers.tiktok.com) → **Manage apps → Add an app**.
2. Products: **Login Kit** (для входа) и **Display API** (для `video.list`).
3. **Scopes**: `user.info.basic`, `video.list`. `user.info.stats` (подписчики, лайки,
   просмотры) и `video.publish` требуют ревью — публикацию мы не просим никогда, а
   `stats` приложение добавит в запрос автоматически, как только вы его получите,
   если включить переключатель « цифры TikTok» в настройках.
4. **Redirect URI for authorization**: `https://<user>.github.io/auth-callback/`
   (TikTok требует `https`, статический, без параметров — хвостовой `/` решает всё,
   сравнивается байт в байт).
5. Из **Credentials** берёте `Client key` и `Client secret` — в приложение.

⚠️ Компромисс, о котором стоит знать: TikTok обменивает код на токен только с
`client_secret`, а своего сервера у приложения нет. Значит секрет лежит в настройках на
устройстве того, кто это настроил. Для личного инструмента это терпимо ( secret нужен
только для вашего же аккаунта, а чужой аккаунт он не открывает), но публиковать сборку
с заполненным полем «TikTok Client Secret» нельзя. Приложение secret никуда не
экспортирует: `exportAuth()` отдаёт только client id/key.

Без секретов тоже можно: тогда TikTok вернёт `invalid client` на обмене, и вы получите
аккуратную ошибку в тосте вместо тихого отказа.

## 3. Логин и пароль

Два режима, выбор автоматический — по наличию Firebase API-ключа в настройках.

**Локальный режим (по умолчанию).** Пароль не хранится. При регистрации
`PasswordHasher` берёт случайные 16 байт соли, делает PBKDF2-HmacSHA256
210 000 итераций и кладёт в `auth_session.json` только хеш и соль (hex). Вход —
сравнение `MessageDigest.isEqual`, константное по времени. Замок на приложение
включается автоматически.

Что это даёт: содержимое смены не откроется чужим человеком, взявшим телефон.
Что это не даёт: это **не** переносимый аккаунт. Пароль нельзя восстановить (нет почты
для сброса — сбрасывать нечего), переустановка приложения = новый аккаунт, а root-доступ
к файлам устройства снимает и этот замок — он против «покрутить в руках», не против
спецслужбы. Токены провайдеров при этом в Keystore и без пароля не читаются.

**Firebase-режим.** Введите Web API-ключ проекта Firebase и включите
**Authentication → Sign-in method → Email/Password**. Тогда:

- регистрация/вход/обновление токена идут через `identitytoolkit.googleapis.com`
  (`FirebaseAuthRest`), идентификатор — Firebase `localId`;
- есть настоящий сброс пароля (кнопка «Забыли?» → `getOobConfirmationCode`),
  почта помечается как подтверждённая (`emailVerified`);
- пароль не попадает ни в какие файлы приложения — он только в TLS-запросе к Google.

Никакого нашего бэкенда для этого не нужно: REST вызывается с устройства, ключ —
публичный (его разрешено вшивать в клиент, ограничьте его по Android package name
в Google Cloud, чтобы по нему не гоняли чужие скрипты).

## 4. Замок на приложении

`LockScreen` показывается перед любым экраном, если `session.lockEnabled`. Пароль
сверяется **локальным хешем всегда**, даже в Firebase-режиме: сеть в метро не должна быть
условием входа в собственные заметки. `unlock()` поднимает флаг в памяти процесса,
переход в фон его не снимает, перезапуск — снимает.

## 5. Хранение и отзыв

- `SecureStore` = `EncryptedSharedPreferences` (AES-GCM, master key в Android Keystore).
  Если Keystore по какой-то причине недоступен, он деградирует в приватный
  `SharedPreferences`, и **прямо об этом пишет** в настройках («Хранилище токенов: …»).
- `Session` — обычный JSON без секретов: его можно посмотреть, он не страшен.
- `exportAuth()` (настройки → «Экспорт доступов») отдаёт провайдеров, scope и срок
  действия, вырезая `passwordHash`, `passwordSalt` и любые токены.
- «Отвязать» отзывает токен на стороне Google (`oauth2.googleapis.com/revoke`), чистит
  хранилище и убирает `channelId` из профиля. «Выйти» делает то же самое для Google,
  а TikTok-токен просто стирает: отдельного эндпоинта отзыва у TikTok нет, поэтому мёртвый refresh-токен
  проживёт до истечения срока (час-два) — этого достаточно, чтобы доступ не остался
  на чужом телефоне после переустановки.
  Google отдельно чистит `prompt=consent select_account`-сессию — refresh-токен
  перевыпускается только с явного согласия, поэтому «тихий» refresh после отзыва невозможен.

## Типичные ошибки

| Сообщение | Причина |
|---|---|
| `redirect_uri_mismatch` | Redirect URI в консоли, в `gradle.properties` и в настройках приложения различаются (хвостовой `/`, `http` вместо `https`) |
| «нужен браузер (Chrome/Firefox)» | на устройстве нет приложения, открывающего ссылки (Custom Tabs тоже не нашёлся) — поставь браузер и начни вход заново |
| `access_denied` | пользователь нажал «Отмена» или аккаунт не добавлен в Test users |
| `invalid_grant` | код одноразовый: страница вернулась дважды (например, «Назад» в браузере); начните вход заново |
| «state не совпал» | редирект пришёл не от начала этой попытки — вход отклонён намеренно |
| «в настройках не указан Google Client ID» | так и должно быть у свежего приложения: без client id входы отключены, работает «Без входа» |
| цифры TikTok пустые | `user.info.stats` не одобрен; приложение не показывает выдуманные подписчики |

## Как проверить без консоли вообще

1. `./gradlew :app:testDebugUnitTest` — 13 тестов на хеш, PKCE, разбор редиректа,
   реестр аккаунтов и то, что пароль не попадает в JSON.
2. `cd preview && npm test` — те же инварианты на прототипе (браузер, 18 тестов).
3. Установить APK → «Без входа»: все четыре агента работают, цифра под «привязкой»
   помечена как демо-данные.
