using NexusFirmware.Core.Models;
using NexusFirmware.Core.Plugins;

namespace NexusFirmware.Plugins.BuiltIn;

/// <summary>
/// Встроенный модуль «Универсальный Android»: демонстрирует контракт плагина и даёт
/// базовые проверки для ADB/Fastboot-устройств без привязки к бренду.
/// </summary>
public sealed class GenericAndroidPlugin : INexusPlugin
{
    public PluginManifest Manifest { get; } = new()
    {
        Id = "nexus.builtin.generic-android",
        Name = "Универсальный Android (ADB/Fastboot)",
        Version = "1.0.0",
        Author = "NEXUS Firmware Studio",
        Publisher = "NEXUS Firmware Studio",
        Description = "Базовые проверки совместимости для устройств, доступных через ADB или Fastboot.",
        AssemblyFile = "NexusFirmware.Plugins.dll",
        EntryType = nameof(GenericAndroidPlugin),
        SupportedBrands = ["Generic Android"],
        SupportedPlatforms = ["ARM64", "ARM32"],
        RequiredDrivers = ["Android ADB Interface", "Android Bootloader Interface"],
        Operations = ["Диагностика ADB", "Чтение переменных fastboot", "Отчёт о состоянии устройства"],
        FirmwareFormats = ["zip", "img", "sparse", "payload.bin"],
        RequiredPermissions = ["USB-доступ (обычные права пользователя)"],
        Limitations = ["Операции записи не выполняются без явного плана и подтверждения."]
    };

    public IReadOnlyList<CompatibilityItem> CheckCompatibility(DeviceInfo device)
    {
        var items = new List<CompatibilityItem>();

        switch (device.Transport)
        {
            case DeviceTransport.Adb:
                items.Add(new CompatibilityItem("Транспорт", CompatibilitySeverity.Info, "ADB доступен: возможна диагностика."));
                break;
            case DeviceTransport.Fastboot:
                items.Add(new CompatibilityItem("Транспорт", CompatibilitySeverity.Info, "Fastboot доступен: возможна работа с разделами при разблокированном загрузчике."));
                break;
            case DeviceTransport.Usb:
                items.Add(new CompatibilityItem("Транспорт", CompatibilitySeverity.Warning,
                    "Устройство видно только как USB: нет доступа к диагностическим интерфейсам."));
                break;
            default:
                items.Add(new CompatibilityItem("Транспорт", CompatibilitySeverity.Warning, "Транспорт не определён."));
                break;
        }

        if (device.Connection != ConnectionState.Connected)
        {
            items.Add(new CompatibilityItem("Соединение", CompatibilitySeverity.Warning,
                $"Состояние соединения: {device.ConnectionText}."));
        }

        return items;
    }

    public IReadOnlyList<string> DescribeOperations(DeviceInfo device) => device.Transport switch
    {
        DeviceTransport.Adb => ["Чтение свойств", "logcat", "Перезагрузка в режимы", "Диагностический отчёт"],
        DeviceTransport.Fastboot => ["Переменные загрузчика", "Список разделов", "Перезагрузка"],
        _ => ["Диагностика USB-подключения"]
    };
}
