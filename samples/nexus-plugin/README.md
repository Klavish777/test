# Пример плагина

`acme.xiaomi.plugin.json` — манифест модуля производителя со всеми поддерживаемыми полями.
Приложение читает файлы `*.plugin.json` из каталога плагинов
(`%LOCALAPPDATA%\NexusFirmwareStudio\plugins`).

Порядок подготовки:

1. Соберите библиотеку с типом, реализующим `NexusFirmware.Core.Plugins.INexusPlugin`.
2. Положите рядом `Acme.Nexus.Xiaomi.dll` и манифест, укажите реальный `sha256`:
   `Get-FileHash Acme.Nexus.Xiaomi.dll -Algorithm SHA256`.
3. Подпишите манифест (необязательно, но обязательно для модулей с `canWriteDevice: true`):
   ```
   openssl dgst -sha256 -sign publisher.key -out Acme.Nexus.Xiaomi.dll.sig manifest-payload.txt
   ```
   где `manifest-payload.txt` содержит строку `id|version|sha256|publisher` в нижнем регистре хэша,
   а `.sig` сохранён в base64.
4. Добавьте издателя в «Плагины → Доверенные издатели» и (для проверки подписи) его открытый ключ
   PEM в хранилище (`publisher_key`).

Без совпадения SHA-256, без доверенного издателя или при выключенной загрузке плагинов модуль не
будет загружен — это ожидаемое поведение, а не ошибка.
