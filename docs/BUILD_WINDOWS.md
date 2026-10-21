# Сборка в Windows EXE и установщик

Приложение поставляется в двух видах:

1. **Портативная сборка** — каталог `dist\SmartphoneRepairOS` с `SmartphoneRepairOS.exe`,
   работает без установки.
2. **Установщик** — `SmartphoneRepairOS-<версия>-setup.exe` (Inno Setup), ставит программу
   в `%LOCALAPPDATA%\Programs\Smartphone Repair OS` или в выбранный каталог, создаёт ярлыки
   и запись в «Установка и удаление программ».

## 1. Автоматическая сборка (рекомендуется)

На машине должны быть установлены:

- Windows 10/11 x64;
- Python 3.10+ (python.org, галочка «Add python.exe to PATH»);
- Inno Setup 6 — <https://jrsoftware.org/isinfo.php> (только для установщика).

Затем в каталоге проекта:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -Version 0.1.0
```

или двойным щелчком `scripts\build_windows.bat`.

Скрипт последовательно:

1. создаёт `.venv` и устанавливает `requirements-dev.txt`;
2. запускает тесты (`pytest`, Qt в режиме `offscreen`);
3. проверяет базу (`main.py --check`);
4. собирает `dist\SmartphoneRepairOS\SmartphoneRepairOS.exe` через PyInstaller;
5. если найден `ISCC.exe` — формирует `installer\Output\SmartphoneRepairOS-<версия>-setup.exe`.

## 2. Ручная сборка

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

python -m pytest tests -q

pyinstaller build\smartphone_repair_os.spec --noconfirm --clean --distpath dist --workpath build\pyinstaller

"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss /DAppVersion=0.1.0
```

## 3. Сборка через GitHub Actions

Workflow `.github/workflows/ci.yml`:

- job `tests` — тесты на Ubuntu;
- job `build-windows` — тесты и сборка на `windows-latest`, публикация артефактов
  `SmartphoneRepairOS-portable` и `SmartphoneRepairOS-installer`;
- при пуше тега `v*` установщик автоматически прикрепляется к GitHub Release.

Запуск вручную: вкладка **Actions → CI · тесты и сборка Windows → Run workflow**.
Готовые файлы скачиваются из раздела **Artifacts** или из **Releases**.

## 4. Что попадает в сборку

| Данные | Куда | Примечание |
|---|---|---|
| Код приложения | внутрь `_internal` (PyInstaller onedir) | обновляется новой сборкой |
| Миграции SQL | `repair_os/data/migrations` | применяются при первом запуске |
| Переводы | `repair_os/resources/i18n` | JSON-каталоги |
| Документация | `docs/` | копируется в сборку |
| База данных, прошивки, библиотека | `%LOCALAPPDATA%\SmartphoneRepairOS` | данные пользователя, не входят в установщик |
| Резервные копии | `%LOCALAPPDATA%\SmartphoneRepairOS\backups` | ZIP с манифестом и SHA-256 |

Обновление приложения не затрагивает пользовательские данные: каталог данных
находится вне каталога установки.

## 5. Кодовая подпись (для распространения)

Чтобы Windows SmartScreen не показывал предупреждение, подпишите установщик
сертификатом Code Signing (EV или OV):

```powershell
signtool sign /f cert.pfx /p <пароль> /tr http://timestamp.digicert.com /td sha256 /fd sha256 `
    installer\Output\SmartphoneRepairOS-0.1.0-setup.exe
```

`cert.pfx` и пароль **не храните в репозитории**; используйте секреты CI.

## 6. Публикация релиза

```powershell
git tag v0.1.0
git push origin v0.1.0
```

Workflow `CI · тесты и сборка Windows` на теге `v*` соберёт EXE, установщик и
портативный ZIP и приложит их к GitHub Release. Логи каждого шага сборки лежат
в `build\logs` и выгружаются артефактом `build-logs` даже при ошибке.

## 7. Типовые проблемы

| Симптом | Решение |
|---|---|
| `Python не найден` | установите Python 3.10+ и перезапустите терминал |
| `Не найден PySide6` | `pip install -r requirements-dev.txt` внутри активированного `.venv` |
| `ISCC не найден` | установите Inno Setup 6; портативная сборка при этом уже готова |
| Антивирус блокирует EXE PyInstaller | подпишите код или добавьте в исключения для теста |
| Приложение не запускается, окно пустое | запустите `SmartphoneRepairOS.exe --check` из консоли, посмотрите `logs\repair_os.log` |
| Сборка падает на тестах UI | проверьте, что `QT_QPA_PLATFORM=offscreen` не конфликтует с локальными настройками Qt |
| `script '...\main.py' not found` | в `build/smartphone_repair_os.spec` корень проекта должен вычисляться от **каталога** spec-файла: `SPECPATH` — это каталог, а не файл |
| `UnicodeEncodeError: 'charmap' codec ...` | Windows использует cp1252 для перенаправленного вывода; скрипт сборки выставляет `PYTHONUTF8=1`, а приложение — `configure_console()` |
| Нужно понять, почему упал CI | скачайте артефакт `build-logs` (файлы `build/logs/*.log`): там полный вывод pip, pytest, PyInstaller, ISCC и дымового запуска EXE |
