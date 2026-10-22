using NexusFirmware.Core.Models;

namespace NexusFirmware.Firmware.Compatibility;

/// <summary>
/// Проверка совместимости прошивки и устройства. Все проверки консервативны:
/// при отсутствии данных выдаётся предупреждение, а не «всё совместимо».
/// </summary>
public static class FirmwareCompatibility
{
    public static CompatibilityCheckResult Check(
        DeviceInfo? device,
        FirmwarePackage? package,
        string? deviceBinaryRevision = null,
        string? packageBinaryRevision = null)
    {
        var items = new List<CompatibilityItem>();

        if (device is null)
        {
            items.Add(new CompatibilityItem("Устройство", CompatibilitySeverity.Blocking,
                "Устройство не выбрано. Прошивка без подтверждённого устройства не планируется."));
        }

        if (package is null)
        {
            items.Add(new CompatibilityItem("Прошивка", CompatibilitySeverity.Blocking,
                "Прошивка не выбрана."));
        }

        if (device is not null && package is not null)
        {
            CheckManufacturer(device, package, items);
            CheckModel(device, package, items);
            CheckRegion(device, package, items);
            CheckMode(device, items);
            CheckBootloader(device, items);
            CheckIntegrity(package, items);
            CheckBinaryRevision(device, package, items, deviceBinaryRevision, packageBinaryRevision);
        }

        return new CompatibilityCheckResult { Items = items };
    }

    private static void CheckManufacturer(DeviceInfo device, FirmwarePackage package, List<CompatibilityItem> items)
    {
        if (string.IsNullOrWhiteSpace(package.Manufacturer) || string.IsNullOrWhiteSpace(device.Manufacturer))
        {
            items.Add(new CompatibilityItem("Производитель", CompatibilitySeverity.Warning,
                "Производитель устройства или прошивки неизвестен — проверьте вручную."));
            return;
        }

        var same = package.Manufacturer.Contains(device.Manufacturer, StringComparison.OrdinalIgnoreCase) ||
                   device.Manufacturer.Contains(package.Manufacturer, StringComparison.OrdinalIgnoreCase);

        items.Add(new CompatibilityItem("Производитель", same ? CompatibilitySeverity.Info : CompatibilitySeverity.Blocking,
            same
                ? $"Производитель совпадает: {device.Manufacturer}."
                : $"Прошивка для {package.Manufacturer}, устройство — {device.Manufacturer}."));
    }

    private static void CheckModel(DeviceInfo device, FirmwarePackage package, List<CompatibilityItem> items)
    {
        var packageIdentity = (package.Model ?? package.Codename ?? string.Empty).Trim();
        if (packageIdentity.Length == 0)
        {
            items.Add(new CompatibilityItem("Модель", CompatibilitySeverity.Warning,
                "В метаданных прошивки нет модели — автоматическая проверка невозможна."));
            return;
        }

        var deviceIdentity = new[] { device.Model, device.Codename }
            .Where(s => !string.IsNullOrWhiteSpace(s))
            .ToArray();

        if (deviceIdentity.Length == 0)
        {
            items.Add(new CompatibilityItem("Модель", CompatibilitySeverity.Warning,
                "Модель устройства не определена — проверка по коду невозможна."));
            return;
        }

        var normalize = (string s) => s.Replace("_", "").Replace(" ", "").ToUpperInvariant();
        var normalizedPackage = normalize(packageIdentity);
        var match = deviceIdentity.Any(d => normalize(d!) == normalizedPackage ||
                                             normalizedPackage.Contains(normalize(d!), StringComparison.Ordinal) ||
                                             normalize(d!).Contains(normalizedPackage, StringComparison.Ordinal));

        items.Add(new CompatibilityItem("Модель", match ? CompatibilitySeverity.Info : CompatibilitySeverity.Blocking,
            match
                ? $"Код модели совпадает: {packageIdentity}."
                : $"Прошивка предназначена для «{packageIdentity}», устройство — «{string.Join(" / ", deviceIdentity)}»."));
    }

    private static void CheckRegion(DeviceInfo device, FirmwarePackage package, List<CompatibilityItem> items)
    {
        if (string.IsNullOrWhiteSpace(package.Region) || string.IsNullOrWhiteSpace(device.Region))
        {
            items.Add(new CompatibilityItem("Регион", CompatibilitySeverity.Info,
                "Регион прошивки или устройства не указан — пропущено (не влияет на совместимость кода модели)."));
            return;
        }

        var matches = package.Region.Contains(device.Region, StringComparison.OrdinalIgnoreCase) ||
                      device.Region.Contains(package.Region, StringComparison.OrdinalIgnoreCase);

        items.Add(new CompatibilityItem("Регион", matches ? CompatibilitySeverity.Info : CompatibilitySeverity.Warning,
            matches
                ? $"Регион совпадает: {package.Region}."
                : $"Регион прошивки «{package.Region}» отличается от региона устройства «{device.Region}». Возможны отличия CSC."));
    }

    private static void CheckMode(DeviceInfo device, List<CompatibilityItem> items)
    {
        switch (device.Mode)
        {
            case DeviceMode.Adb:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Info,
                    "Устройство в режиме ADB: доступны диагностика и перезагрузка в fastboot/recovery."));
                break;
            case DeviceMode.Fastboot:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Info,
                    "Устройство в режиме Fastboot: возможна запись разделов при разблокированном загрузчике."));
                break;
            case DeviceMode.Download:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Info,
                    "Устройство в режиме Download (Samsung). Работа возможна только через официальный/разрешённый инструмент."));
                break;
            case DeviceMode.QualcommEdl:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Warning,
                    "Устройство в режиме EDL: работа требует совместимого programmer-файла и разрешённого инструмента."));
                break;
            case DeviceMode.MediaTekBootrom:
            case DeviceMode.MediaTekPreloader:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Warning,
                    "Устройство MediaTek в сервисном режиме: возможна защита SLA/DAA, требуется авторизация."));
                break;
            case DeviceMode.Unknown:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Warning,
                    "Режим устройства не определён — уточните состояние подключения."));
                break;
            default:
                items.Add(new CompatibilityItem("Режим подключения", CompatibilitySeverity.Info,
                    $"Режим {device.ModeText}."));
                break;
        }

        if (device.Connection is ConnectionState.Unauthorized or ConnectionState.Offline or ConnectionState.NoPermissions)
        {
            items.Add(new CompatibilityItem("Соединение", CompatibilitySeverity.Blocking,
                $"Состояние соединения: {device.ConnectionText}. Операция невозможна."));
        }
    }

    private static void CheckBootloader(DeviceInfo device, List<CompatibilityItem> items)
    {
        if (device.BootloaderUnlocked is null)
        {
            items.Add(new CompatibilityItem("Загрузчик", CompatibilitySeverity.Warning,
                "Состояние загрузчика не определено. Запись разделов не будет запланирована без подтверждения."));
            return;
        }

        items.Add(new CompatibilityItem("Загрузчик",
            device.BootloaderUnlocked.Value ? CompatibilitySeverity.Info : CompatibilitySeverity.Blocking,
            device.BootloaderUnlocked.Value
                ? "Загрузчик разблокирован (по данным устройства)."
                : "Загрузчик заблокирован: запись образов через fastboot недоступна без официальной разблокировки/сервисного режима."));
    }

    private static void CheckIntegrity(FirmwarePackage package, List<CompatibilityItem> items)
    {
        switch (package.Integrity)
        {
            case IntegrityState.Verified:
                items.Add(new CompatibilityItem("Целостность", CompatibilitySeverity.Info, "SHA-256 прошивки подтверждён."));
                break;
            case IntegrityState.Failed:
                items.Add(new CompatibilityItem("Целостность", CompatibilitySeverity.Blocking,
                    "SHA-256 не совпадает с сохранённым значением. Использовать файл нельзя."));
                break;
            default:
                items.Add(new CompatibilityItem("Целостность", CompatibilitySeverity.Warning,
                    "SHA-256 ещё не проверялся. Перед прошивкой необходимо проверить хеш."));
                break;
        }

        if (string.IsNullOrWhiteSpace(package.FilePath))
        {
            items.Add(new CompatibilityItem("Файл", CompatibilitySeverity.Blocking, "У прошивки нет привязанного файла."));
        }
        else if (!File.Exists(package.FilePath))
        {
            items.Add(new CompatibilityItem("Файл", CompatibilitySeverity.Blocking,
                "Файл прошивки недоступен по сохранённому пути."));
        }
    }

    private static void CheckBinaryRevision(
        DeviceInfo device,
        FirmwarePackage package,
        List<CompatibilityItem> items,
        string? deviceBinaryRevision,
        string? packageBinaryRevision)
    {
        if (string.IsNullOrWhiteSpace(deviceBinaryRevision) || string.IsNullOrWhiteSpace(packageBinaryRevision))
        {
            items.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Info,
                "Ревизия загрузчика (binary/bit) не определена у устройства или пакета — проверка отката не выполнена."));
            return;
        }

        if (!int.TryParse(deviceBinaryRevision, out var deviceBinary) || !int.TryParse(packageBinaryRevision, out var packageBinary))
        {
            items.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Info,
                $"Сравнение ревизий недоступно («{deviceBinaryRevision}» / «{packageBinaryRevision}»)."));
            return;
        }

        if (packageBinary < deviceBinary)
        {
            items.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Blocking,
                $"Ревизия пакета ({packageBinary}) ниже ревизии устройства ({deviceBinary}). Откат заблокирован загрузчиком."));
        }
        else if (packageBinary > deviceBinary)
        {
            items.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Warning,
                $"Ревизия пакета ({packageBinary}) выше ревизии устройства ({deviceBinary}). После прошивки откат на прежнюю версию станет невозможен."));
        }
        else
        {
            items.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Info,
                $"Ревизии совпадают ({deviceBinary}). Откат формально не блокируется, но проверьте политику производителя."));
        }

        _ = package;
        _ = device;
    }
}
