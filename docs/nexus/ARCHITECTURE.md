# Архитектура NEXUS Firmware Studio

## Общая схема

```
┌─────────────────────────────────────────────────────────────────────────┐
│ NexusFirmware.App (WPF, net10.0-windows)                                │
│  MainWindow + 14 View/ViewModel · DialogService · DeviceSession ·       │
│  ReportService · AppNavigation                                          │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ вызовы сервисов, подписки на события, отчёты
┌───────────────▼─────────────────────────────────────────────────────────┐
│ Прикладные модули                                                       │
│  Flashing (планировщик, стратегии)                                      │
│  Qualcomm · MediaTek · Samsung (подготовка пакетов и отчётов)           │
│  Drivers · Plugins (доверие, загрузка)                                  │
│  Firmware (форматы, архивы, образы, библиотека, сравнение)              │
│  DeviceDetection (ADB, Fastboot, USB, обнаружение)                      │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ абстракции
┌───────────────▼─────────────────────────────────────────────────────────┐
│ NexusFirmware.Infrastructure                                            │
│  ProcessRunner · ToolLocator · ExternalToolAdapter · LogBus (Serilog)   │
│  AppPaths · SettingsService · NexusDatabase (SQLite) + репозитории      │
└───────────────┬─────────────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────────────┐
│ NexusFirmware.Core                                                      │
│  Модели (DeviceInfo, FirmwarePackage, OperationPlan/Step, отчёты)       │
│  Безопасность (PathSafety, Hashing, InputValidator, Redactor)          │
│  JobQueue · ReportWriter · IPlugin · Localizer                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Зависимости направлены вниз: Core не знает о WPF, о процессах и о SQLite; Infrastructure
реализует абстракции Core; прикладные модули используют и то, и другое; App только связывает их.

## Проекты

| Проект | Ответственность | Ключевые типы |
|--------|-----------------|---------------|
| `NexusFirmware.Core` | модель предметной области, правила безопасности, очередь заданий, контракты плагинов | `DeviceInfo`, `FirmwarePackage`, `OperationPlan`, `JobQueue`, `PathSafety`, `Hashing`, `Redactor`, `InputValidator`, `ReportWriter`, `PluginManifest` |
| `NexusFirmware.Infrastructure` | внешние процессы, журналирование, конфигурация, SQLite | `ProcessRunner`, `ToolLocator`, `LogBus`, `AppPaths`, `SettingsService`, `NexusDatabase`, `FirmwareRepository`, `DiagnosticsRepository`, `TrustRepository` |
| `NexusFirmware.DeviceDetection` | обнаружение устройств и низкоуровневые команды | `AdbProvider`, `FastbootProvider`, `WindowsUsbEnumerator`, `DeviceDiscoveryService`, `AdbService`, `FastbootService` |
| `NexusFirmware.Firmware` | форматы, архивы, образы, извлечение, сравнение, библиотека | `FormatDetector`, `ZipInspector`, `TarInspector`, `Lz4FrameDecoder`, `SparseImageParser`, `BootImageParser`, `PayloadParser`, `ScatterParser`, `RawProgramParser`, `SamsungPackageAnalyzer`, `FirmwareLibrary`, `FirmwareExtractorService`, `FirmwareComparer` |
| `NexusFirmware.Flashing` | построение плана записи и его выполнение | `FlashPlanner`, `FlashPlan`, `FlashOptions`, `FastbootImageStrategy`, `AdbSideloadStrategy`, `ExternalToolStrategies` |
| `NexusFirmware.Qualcomm` | подготовка EDL/Firehose | `QualcommService`, `QualcommPackageAnalysis` |
| `NexusFirmware.MediaTek` | подготовка BROM/SP Flash Tool | `MediaTekService`, `MtkPackageAnalysis` |
| `NexusFirmware.Samsung` | подготовка Odin/Download mode | `SamsungService`, `SamsungPackageResult` |
| `NexusFirmware.Drivers` | инвентаризация драйверов и подписи | `DriverCenterService`, `DriverInventoryItem`, `SignatureCheckResult` |
| `NexusFirmware.Plugins` | доверие и загрузка модулей производителей | `PluginTrustPolicy`, `PluginLoader`, `PluginHost`, `GenericAndroidPlugin` |
| `NexusFirmware.App` | интерфейс и связывание | `MainViewModel`, 13 разделов, `AppHost` |

## Поток обнаружения устройства

1. `MainViewModel` по таймеру (интервал из настроек) вызывает `DeviceDiscoveryService.ScanAsync()`.
2. `DeviceDiscoveryService` опрашивает параллельно:
   * `AdbProvider` — `adb devices -l`, разбор состояния (`device`, `unauthorized`, `offline`),
     затем `adb shell getprop` для модели, кодового имени, версии Android, блокировки загрузчика;
   * `FastbootProvider` — `fastboot devices` и `fastboot getvar all` (модель, `unlocked`,
     `current-slot`, размеры разделов);
   * `WindowsUsbEnumerator` — `Get-PnpDevice -PresentOnly -Class USB,AndroidUsbDeviceClass,Ports`
     и `Get-PnpDeviceProperty`, что даёт VID/PID, состояние драйвера и код проблемы.
3. Результаты объединяются по серийному номеру/VID-PID; устройство, видимое одновременно в ADB и
   USB, не дублируется. USB-устройство без seral-номера остаётся без него — поле `Serial = null`,
   интерфейс показывает «недоступно».
4. `DeviceSession` хранит текущий список и выбранное устройство; представления подписаны на
   `ObservableCollection`, поэтому список обновляется без перезагрузки страницы.

Ошибки инструментов не приводятся к «устройство не найдено»: провайдер возвращает
`ProviderStatus { ProviderId, Available, Detail }`, и интерфейс отличает «adb не установлен» от
«adb установлен, устройств нет».

## Поток работы с прошивкой

1. **Импорт.** `FirmwareLibrary.ImportAsync` считает SHA-256 (потоково), определяет формат,
   проверяет дубликат по хэшу, пишет запись в `firmware` и историю импорта.
2. **Разбор.** `FirmwareAnalyzer.Inspect` (только чтение) определяет формат по сигнатуре,
   разбирает заголовки (sparse, boot.img, payload), перечисляет содержимое архивов, формирует
   секции отчёта, список предупреждений и **явный список ограничений** — что именно не удалось
   определить.
3. **Извлечение.** `FirmwareExtractorService` создаёт временный каталог, проверяет архив
   (`ZipInspector`/`TarInspector`), распаковывает с контролем каждого пути и лимитов, никогда не
   изменяя исходный файл. Пользователь может указать собственный каталог назначения.
4. **Сравнение.** `FirmwareComparer` сопоставляет метаданные и содержимое двух архивов: список
   файлов, размеры, различия, файлы только слева/справа.
5. **Совместимость.** `FirmwareCompatibility.Check` формирует `CompatibilityItem` с уровнями
   `Info/Warning/Blocking`: модель, производитель, регион, состояние загрузчика, целостность
   файла, anti-rollback (сравнение ревизий бинарника, если обе известны).

## Поток прошивания

```
FlashPlanner.BuildPlanAsync(context)
        │  проверки: устройство, режим, загрузчик, целостность, свободное место,
        │  anti-rollback, наличие образов, поддержка стратегией
        ▼
FlashPlan { StrategyId, OperationPlan (шаги, проверки, риски), Targets, Job }
        │  UI показывает план, предупреждения и наивысший риск
        ▼
пользователь подтверждает (dry-run — без записи; реальная запись — ввод серийного номера)
        ▼
JobQueue.Enqueue(job) → последовательное выполнение шагов, прогресс, журнал
        ▼
OperationReport → ReportService (Markdown + JSON) → DiagnosticsRepository
```

* `FlashOptions.DryRun` по умолчанию `true`.
* Реальная запись возможна только при `DryRun = false` **и** `AllowDeviceModification = true`
  **и** подтверждении серийным номером в диалоге.
* `OperationRisk`: `ReadOnly` → `ModifiesDevice` → `Destructive`; план с `Blocking`-проверкой
  не выполняется вовсе.
* Для Samsung/MediaTek/Qualcomm стратегии возвращают план с блокирующей проверкой и
  пояснением, что протокол не реализован, а шаги описывают подготовку пакета для официального
  инструмента.

## Очередь заданий

`JobQueue` — единственная точка выполнения длительных операций. Задания выполняются
последовательно (одно устройство — одна операция), события `JobChanged` поднимаются в UI через
`Dispatcher`. Отмена поддерживается между шагами; шаг, помеченный как неотменяемый (например,
уже начатая запись раздела), не прерывается на середине. По завершении задание преобразуется в
`OperationReport`.

## Данные

```
%LOCALAPPDATA%\NexusFirmwareStudio\      (портативно: <папка exe>\data)
├── nexus.db        SQLite: firmware, firmware_note, device_snapshot,
│                   operation_report, trusted_publisher, journal
├── logs\           Serilog, ротация по дням, хранение 14 дней
├── reports\        Markdown и JSON отчёты
└── plugins\        манифесты и сборки плагинов (загрузка выключена по умолчанию)
```

Схема создаётся идемпотентно (`CREATE TABLE IF NOT EXISTS`) с таблицей `schema_version` для
будущих миграций. Все запросы параметризованы.

## Плагины

`PluginHost.ScanAndLoad` читает `manifest.json`, проверяет:
идентификатор/версию, наличие сборки, **SHA-256 сборки**, издателя в списке доверенных,
включён ли вообще загрузчик (`AllowPluginLoading`, по умолчанию выключен). При любом
несоответствии сборка не загружается, а решение попадает в `LastRejected` и показывается в
разделе «Плагины». Встроенный модуль `GenericAndroidPlugin` описывает общие операции Android и
не требует внешнего кода.

## Интерфейс

`App.xaml` содержит словарь ресурсов тёмной темы и 14 `DataTemplate` (ViewModel → View).
`MainViewModel` держит навигацию, выбранное устройство, журнал и очередь заданий; каждая
страница — отдельная ViewModel, получающая сервисы через конструктор. Ни одна ViewModel не
создаёт сервисы сама: всё собирается в `AppHost` (Microsoft.Extensions.DependencyInjection).
