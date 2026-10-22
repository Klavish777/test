# Apple Flash Studio v2.0 — перепрошивка и восстановление iPhone, iPad и MacBook на Windows 10/11

**Apple Flash Studio v2.0** — самостоятельное настольное приложение для Windows 10/11 (x64) на русском языке со встроенным внутрь `.exe` реальным движком `pymobiledevice3` и библиотекой `libusb-1.0.dll` для обнаружения по USB, управления режимами Recovery/DFU и перепрошивки **iPhone**, **iPad** и **MacBook** (Apple Silicon M1–M4 и Intel T2) локальными файлами `.ipsw`.

![Главная страница Apple Flash Studio](screenshots/apple_01_dashboard.png)

---

## Основные возможности v2.0

1. **Трёхуровневое автоопределение реальных устройств Apple по USB (каждые 2.5 сек)**
   - **Уровень 1 (`usbmuxd` + `lockdownd`)**: чтение модели, версии iOS/iPadOS, процессора, серийного номера и ECID без навязчивых окон «Доверять этому компьютеру?».
   - **Уровень 2 (`IRecv` + встроенный `libusb-1.0.dll`)**: прямое чтение чипа `CPID`, ревизии платы `BDID` и `ECID` в режимах **Recovery** и **DFU** со сверкой по базе **340+ официальных моделей Apple**.
   - **Уровень 3 (нативный `Win32 SetupAPI` на C/ctypes, `< 2 мс`)**: мгновенно обнаруживает подключённый к USB кабель `VID_05AC` даже на чистой Windows, где ещё не установлен драйвер Apple USB, и подсказывает кнопку установки в 1 клик.

2. **Простой и понятный интерфейс без фейковых макетов**
   - Чистый запуск без виртуальных устройств `[МАКЕТ]` и без демонстрационных `DEMO_*.ipsw`.
   - Слева — карточка реального подключённого устройства и кнопки **«Перевести в Recovery»**, **«Выйти из режима Recovery»**, **«Перезагрузить»**.
   - Справа — выбор локального файла `.ipsw` (кнопкой или перетаскиванием мышью Drag & Drop), мгновенная проверка `BuildManifest.plist` без распаковки архива и запуск прошивки.

3. **Реальная прошивка встроенным движком `pymobiledevice3`**
   - **Обновить систему (сохранить данные)** — обновление системы без удаления фото и настроек.
   - **Чистая перепрошивка со сбросом (стереть данные)** — устранение бутлупа и сброс забытого код-пароля экрана (автоматически переводит заблокированный паролем телефон в Recovery перед прошивкой).
   - **Оживить MacBook (Revive DFU)** — восстановление контроллера Apple Silicon M1–M4 и чипа T2 без удаления пользовательских данных macOS.
   - Живой прогресс записи системного раздела в МБ/ГБ и подробный журнал этапов на русском языке.

4. **Интерактивный тренажёр DFU / Recovery с секундомером**
   - Пошаговый таймер удержания кнопок для всех поколений iPhone (Face ID, SE 2/3, 8),
     iPad (с кнопкой Home и без кнопки Home) и MacBook.
   - Встроенная **карта сервисных DFU-портов USB-C** для всех моделей MacBook Air и MacBook Pro
     (включая исключение для MacBook Pro 14" на базовом чипе M3 `Mac15,3`).

5. **Диагностика драйверов Windows и журнал операций**
   - Проверка службы `AppleMobileDeviceService`, модуля `pymobiledevice3`, бинарных утилит
     `idevicerestore.exe` / `irecovery.exe` и рекомендации по привязке `WinUSB` (через Zadig)
     для работы с DFU на Windows.
   - Полный SQLite-журнал всех запусков с экспортом текстовых отчётов `.txt`.

---

## Скриншоты интерфейса

| Мастер прошивки (.ipsw) | Локальная библиотека IPSW |
|---|---|
| ![Мастер прошивки](screenshots/apple_02_flash_wizard.png) | ![Библиотека IPSW](screenshots/apple_03_ipsw_library.png) |

| Тренажёр DFU и карта портов MacBook | Диагностика драйверов Windows |
|---|---|
| ![Тренажёр DFU](screenshots/apple_04_dfu_assistant.png) | ![Драйверы Windows](screenshots/apple_05_windows_drivers.png) |

---

## Быстрый запуск на Windows 10/11

### Вариант 1. Запуск в один клик из исходников

```powershell
run_apple_flash.bat
```

Скрипт автоматически создаёт виртуальное окружение `.venv`, устанавливает `PySide6` и
`pymobiledevice3`, после чего открывает графическое окно **Apple Flash Studio**.

### Вариант 2. Сборка готового `AppleFlashStudio.exe` и установщика Windows

```powershell
scripts\build_apple_flash_windows.bat
```

Или через PowerShell с указанием версии:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_apple_flash_windows.ps1 -Version 1.0.0
```

После завершения сборки:
- Портативная версия: `dist\AppleFlashStudio\AppleFlashStudio.exe`
- Установщик Windows (если установлен Inno Setup 6): `installer\Output\AppleFlashStudio-1.0.0-setup.exe`

---

## Подготовка драйверов и прошивальщиков на Windows

1. **Обычный режим связи (Normal Mode / USBMux)**:
   - Установите официальное приложение **«Устройства Apple» (Apple Devices)** из Microsoft Store
     или классический пакет **iTunes x64** с сайта Apple. Это установит драйвер `usbaapl64.sys`
     и запустит системную службу `AppleMobileDeviceService`.
2. **Движок перепрошивки (достаточно одного из двух)**:
   - **pymobiledevice3** (устанавливается автоматически через `run_apple_flash.bat` или командой
     `.venv\Scripts\pip install pymobiledevice3`), либо
   - **libimobiledevice / idevicerestore для Windows**: скопируйте файлы `idevicerestore.exe`,
     `irecovery.exe`, `ideviceinfo.exe`, `idevice_id.exe`, `ideviceenterrecovery.exe` в папку
     `%LOCALAPPDATA%\AppleFlashStudio\tools` (кнопка **«Открыть папку tools»** на вкладке *Настройки*).
3. **Особенность режима DFU на Windows (особенно для MacBook M1–M4 / T2 и `idevicerestore`)**:
   - Подключите устройство в режиме DFU (экран полностью чёрный, в Диспетчере устройств видно
     `Apple Mobile Device (DFU Mode)` с кодом `USB\VID_05AC&PID_1227`).
   - Для кабеля MacBook используйте дата-кабель **USB-C (USB 2.0 / 3.x)** (не кабель Thunderbolt!)
     строго в сервисный DFU-порт целевого ноутбука (см. вкладку *Мастер DFU / Recovery*).
   - Если `idevicerestore` не может захватить USB-интерфейс DFU из-за стандартного драйвера,
     откройте бесплатную утилиту **Zadig** → *Options → List All Devices* → выберите
     `Apple Mobile Device (DFU Mode)` и нажмите **Replace Driver → WinUSB**.

---

## Важные технические и правовые ограничения

- **Подпись прошивок Apple TSS**: при реальной перепрошивке iPhone, iPad и MacBook загрузчик
  запрашивает цифровую подпись компонентов (`SHSH2` / `ApTicket`) у официального сервера Apple
  (`gs.apple.com`), если не передан заранее сохранённый билет подписи. Установить неподписываемую
  компанией Apple версию iOS/iPadOS в штатном режиме нельзя.
- **Никакого обхода защиты владельца**: приложение **не обходит** блокировку активации iCloud
  (Activation Lock / Find My), MDM-профили или код-пароль устройства. Если на устройстве включён
  «Локатор», после чистой перепрошивки потребуется ввод Apple ID владельца.
- **Учебные ДЕМО-макеты**: создаваемые при первом запуске файлы `DEMO_*.ipsw` содержат только
  структуру `BuildManifest.plist` для проверки интерфейса и режима `Dry-Run`. Реальная запись
  демо-макетов на устройство программно заблокирована; удалить их можно в один клик в разделе *Настройки*.
