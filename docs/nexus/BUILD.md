# Сборка, тестирование и выпуск

## Локальная сборка

Требуется .NET SDK 10.0 (Windows 10/11 x64 для запуска интерфейса).

```powershell
dotnet --info                      # убедитесь, что SDK 10.0 установлен
dotnet restore NexusFirmware.sln
dotnet build NexusFirmware.sln -c Release
dotnet run --project src/NexusFirmware.App/NexusFirmware.App.csproj
```

Проверка библиотек без графической части (работает и на Linux):

```bash
dotnet build tests/NexusFirmware.UnitTests/NexusFirmware.UnitTests.csproj -c Release
dotnet test  tests/NexusFirmware.UnitTests/NexusFirmware.UnitTests.csproj -c Release
dotnet test  tests/NexusFirmware.IntegrationTests/NexusFirmware.IntegrationTests.csproj -c Release
```

## Публикация приложения

Одним файлом (self-contained, ~130 МБ, не требует установленного .NET):

```powershell
dotnet publish src/NexusFirmware.App/NexusFirmware.App.csproj `
  -c Release -r win-x64 --self-contained true `
  -p:PublishSingleFile=true `
  -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:DebugType=none `
  -o artifacts/publish
```

Результат: `artifacts/publish/NexusFirmwareStudio.exe`.

Облегчённый вариант (нужен .NET Desktop Runtime 10):

```powershell
dotnet publish src/NexusFirmware.App/NexusFirmware.App.csproj -c Release -r win-x64 --self-contained false -o artifacts/framework
```

## Установщик (Inno Setup 6)

```powershell
# 1. опубликовать приложение в artifacts/publish (см. выше)
# 2. собрать установщик
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\nexus.iss
```

Готовый файл: `installer\Output\NEXUS-Firmware-Studio-Setup-1.0.0.exe`.

Скрипт `installer/nexus.iss`:

* кладёт содержимое `artifacts/publish` в `%ProgramFiles%\NEXUS Firmware Studio` (или в каталог
  пользователя при установке без прав администратора);
* добавляет ярлыки и деинсталлятор;
* копирует документацию в подкаталог `docs`;
* **не** устанавливает драйверы, службы и не меняет политику подписи драйверов.

## CI (GitHub Actions)

`.github/workflows/ci.yml`:

| Job | Где | Что делает |
|-----|-----|------------|
| `tests` | ubuntu-latest | restore, сборка библиотек и тестов, `dotnet test` обоих проектов |
| `windows` | windows-latest | сборка решения (включая WPF), publish self-contained, сборка установщика Inno Setup |
| `release` | ubuntu-latest | при теге `v*` или ручном запуске создаёт релиз с установщиком и EXE |

Артефакты: `nexus-firmware-studio-windows` (установщик + портативный EXE).

Ручной выпуск:

```
Actions → CI → Run workflow → branch: main → release_tag: v1.0.1
```

## Типовые проблемы

| Симптом | Причина и решение |
|---------|-------------------|
| `error NETSDK1045: The current .NET SDK does not support targeting .NET 10.0` | установлен SDK 8/9; поставьте .NET SDK 10.0 и повторите |
| `NU1101: Unable to find package …` | нет доступа к nuget.org; настройте прокси или используйте кэш пакетов |
| `WPF requires Windows` при сборке на Linux | собирайте `NexusFirmware.App` только на Windows; библиотеки и тесты собираются на Linux |
| Установщик не находит `artifacts\publish` | сначала выполните `dotnet publish` с `-o artifacts/publish` |
| Приложение не видит устройство | проверьте `adb devices`, `fastboot devices`, диспетчер устройств; раздел «Драйверы» покажет код проблемы |
| `adb: no permissions` на Linux | правила udev для Android; на Windows — официальный драйвер производителя |
| Отчёты не сохраняются | проверьте права на `%LOCALAPPDATA%\NexusFirmwareStudio\reports` |

## Версии и зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| Microsoft.Extensions.DependencyInjection(+Abstractions) | 9.0.0 | DI в приложении и библиотеках |
| Microsoft.Data.Sqlite | 9.0.0 | локальная база |
| Serilog + Sinks.File/Console | 4.2.0 / 6.0.0 | журналирование |
| NUnit + NUnit3TestAdapter + Microsoft.NET.Test.Sdk | 3.14.0 / 4.6.0 / 17.14.1 | тесты |

Целевые платформы: `net10.0` для библиотек, `net10.0-windows` (WPF) для приложения.
`Nullable` и `ImplicitUsings` включены, анализаторы — на уровне `latest` с отключёнными
платформенными предупреждениями (`CA1416` и др. — см. `Directory.Build.props`).
