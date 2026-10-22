# NEXUS Firmware Studio

Рабочее место сервисного инженера для Windows: определение подключённых устройств, разбор
прошивок, безопасная подготовка операций записи, диагностика и отчётность.

Приложение написано с нуля на **C# / .NET 10** (WPF, MVVM). Оно не является копией UnlockTool,
Chimera, EFT Pro, TSM Pro или иных коммерческих продуктов: совпадает только предметная область —
сервисная работа с прошивками, — а весь код, структура и тексты интерфейса оригинальные.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NEXUS Firmware Studio                                                    │
│ Обзор · Устройства · Прошивки · Прошивание · ADB/Fastboot · Qualcomm ·   │
│ MediaTek · Samsung · Извлечение · Разделы · Журнал · Драйверы ·          │
│ Плагины · Настройки                                                      │
└──────────────────────────────────────────────────────────────────────────┘
```

## Что действительно работает

| Блок | Состояние |
|------|-----------|
| Определение устройств (ADB, Fastboot, USB/Windows) | реализовано, реальные вызовы `adb`/`fastboot`/`Get-PnpDevice` |
| Каталог прошивок, импорт, SHA-256, дубликаты, заметки | реализовано (SQLite) |
| Разбор форматов: zip, tar/tar.md5, gzip, LZ4 frame, sparse, boot.img, payload.bin, scatter, rawprogram XML | реализовано (чтение, только чтение) |
| Безопасная распаковка с защитой от path traversal и zip-бомб | реализовано |
| Сравнение прошивок (метаданные + содержимое архивов) | реализовано |
| Планирование прошивания через Fastboot и ADB sideload | реализовано, запись только после явных подтверждений |
| Проверка совместимости (модель, регион, загрузчик, целостность, anti-rollback) | реализовано |
| Samsung Download mode (Odin), MediaTek BROM/SLA/DAA, Qualcomm EDL/Firehose | **только подготовка**: анализ пакета, план и отчёт для официального инструмента |
| Драйверы: инвентаризация, официальные источники, проверка подписи установщика | реализовано |
| Плагины: манифест, SHA-256, доверенный издатель, выключенная по умолчанию загрузка | реализовано |
| Отчёты (Markdown + JSON) и журнал операций | реализовано |

Чего приложение **не делает** и не будет делать: не обходит блокировку загрузчика, подпись
образов, Secure Boot, SLA/DAA, блокировки аккаунта и DRM; не извлекает персональные данные; не
отправляет данные на сторонние серверы; не отключает проверку подписи драйверов; не выдаёт
неподтверждённые результаты за успешные.

## Требования

* Windows 10/11 x64 (интерфейс — WPF).
* .NET SDK 10.0 — только для сборки из исходников. Готовый установщик self-contained, SDK не нужен.
* Для работы с устройством: `adb` и `fastboot` (Android Platform Tools) в `PATH` либо указаны в
  настройках; официальные драйверы производителя.
* Для сборки установщика: Inno Setup 6.

## Установка

1. Скачайте `NEXUS-Firmware-Studio-Setup-*.exe` из раздела **Releases** этого репозитория.
2. Запустите установщик (права администратора не требуются; приложение не устанавливает драйверы).
3. Запустите «NEXUS Firmware Studio» из меню «Пуск».

Портативная версия — `NexusFirmwareStudio.exe` (self-contained, один файл).

## Сборка из исходников

```powershell
git clone https://github.com/Klavish777/test.git
cd test
dotnet restore NexusFirmware.sln
dotnet build NexusFirmware.sln -c Release
dotnet run --project src/NexusFirmware.App/NexusFirmware.App.csproj
```

Публикация и установщик:

```powershell
dotnet publish src/NexusFirmware.App/NexusFirmware.App.csproj `
  -c Release -r win-x64 --self-contained true `
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true `
  -o artifacts/publish

& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\nexus.iss
# результат: installer\Output\NEXUS-Firmware-Studio-Setup-1.0.0.exe
```

## Тесты

```bash
dotnet test tests/NexusFirmware.UnitTests/NexusFirmware.UnitTests.csproj
dotnet test tests/NexusFirmware.IntegrationTests/NexusFirmware.IntegrationTests.csproj
```

Юнит-тесты покрывают парсеры форматов, безопасность путей, редакцию идентификаторов, проверку
подписи плагинов, планировщик прошивания (без устройства) и очередь заданий. Интеграционные —
SQLite-репозитории, библиотеку прошивок, извлечение архивов, лимиты распаковки и обнаружение
устройств с подставными провайдерами. Тесты **не** требуют подключённого телефона и не выполняют
запись на устройство.

## Структура репозитория

```
.
├── NexusFirmware.sln
├── Directory.Build.props
├── src/
│   ├── NexusFirmware.Core/            доменные модели, безопасность, задания, плагины, отчёты
│   ├── NexusFirmware.Infrastructure/  процессы, логирование, настройки, SQLite
│   ├── NexusFirmware.DeviceDetection/ ADB, Fastboot, USB (Windows), обнаружение
│   ├── NexusFirmware.Firmware/        форматы, архивы, образы, извлечение, сравнение
│   ├── NexusFirmware.Flashing/        планирование и стратегии прошивания
│   ├── NexusFirmware.Qualcomm/        подготовка EDL/Firehose
│   ├── NexusFirmware.MediaTek/        подготовка BROM/SP Flash Tool
│   ├── NexusFirmware.Samsung/         подготовка Odin/Download mode
│   ├── NexusFirmware.Drivers/         драйверы и подписи
│   ├── NexusFirmware.Plugins/         загрузчик плагинов и встроенные модули
│   └── NexusFirmware.App/             WPF-приложение (14 разделов)
├── tests/
│   ├── NexusFirmware.UnitTests/
│   └── NexusFirmware.IntegrationTests/
├── installer/nexus.iss                скрипт Inno Setup
├── samples/nexus-plugin/              пример манифеста плагина
└── docs/nexus/                        документация
```

## Документация

* [docs/nexus/ARCHITECTURE.md](docs/nexus/ARCHITECTURE.md) — архитектура и потоки данных
* [docs/nexus/CAPABILITIES.md](docs/nexus/CAPABILITIES.md) — что реализовано, что частично, что нет
* [docs/nexus/SAFETY.md](docs/nexus/SAFETY.md) — модель безопасности и разрушительные операции
* [docs/nexus/BUILD.md](docs/nexus/BUILD.md) — сборка, публикация, CI, типовые ошибки
* [docs/nexus/USER_GUIDE.md](docs/nexus/USER_GUIDE.md) — руководство по разделам
* [docs/nexus/PLUGINS.md](docs/nexus/PLUGINS.md) — формат плагинов и доверие
* [docs/nexus/TESTING.md](docs/nexus/TESTING.md) — тесты и что они гарантируют
* [docs/nexus/ROADMAP.md](docs/nexus/ROADMAP.md) — дальнейшие этапы

## Лицензия

См. [LICENSE](LICENSE).
