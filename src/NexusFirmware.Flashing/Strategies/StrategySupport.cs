using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Compatibility;

namespace NexusFirmware.Flashing.Strategies;

/// <summary>Общие проверки и форматирование шагов для всех стратегий.</summary>
internal static class StrategySupport
{
    public static List<CompatibilityItem> BaseChecks(FlashPlanContext context, bool requiresFastboot, bool requiresAdb)
    {
        var checks = FirmwareCompatibility.Check(
            context.Device,
            context.Package,
            context.DeviceBinaryRevision,
            context.PackageBinaryRevision).Items.ToList();

        if (context.Options.DryRun)
        {
            checks.Add(new CompatibilityItem("Режим", CompatibilitySeverity.Info,
                "Dry Run: план будет выполнен без изменения устройства."));
        }
        else if (!context.Options.AllowDeviceModification)
        {
            checks.Add(new CompatibilityItem("Разрешение", CompatibilitySeverity.Blocking,
                "Изменение устройства запрещено настройками. Включите разрешение и подтвердите операцию."));
        }

        if (requiresFastboot)
        {
            checks.Add(context.Fastboot.IsAvailable
                ? new CompatibilityItem("Fastboot", CompatibilitySeverity.Info, "fastboot доступен.")
                : new CompatibilityItem("Fastboot", CompatibilitySeverity.Blocking,
                    "fastboot не найден. Установите Android Platform Tools и укажите путь в настройках."));

            if (context.Device.Mode is not (DeviceMode.Fastboot or DeviceMode.Adb))
            {
                checks.Add(new CompatibilityItem("Режим", CompatibilitySeverity.Blocking,
                    $"Устройство в режиме {context.Device.ModeText}: для этой стратегии нужен Fastboot или ADB."));
            }

            if (context.Device.Mode == DeviceMode.Adb)
            {
                checks.Add(new CompatibilityItem("Перевод в fastboot", CompatibilitySeverity.Warning,
                    "Устройство в режиме ADB: потребуется перезагрузка в загрузчик (adb reboot bootloader)."));
            }
        }

        if (requiresAdb && !context.Adb.IsAvailable)
        {
            checks.Add(new CompatibilityItem("ADB", CompatibilitySeverity.Blocking,
                "adb не найден. Установите Android Platform Tools."));
        }

        if (context.Device.BatteryLevel is < 25)
        {
            checks.Add(new CompatibilityItem("Батарея", CompatibilitySeverity.Blocking,
                $"Уровень заряда {context.Device.BatteryLevel}% — недостаточно для безопасной операции."));
        }
        else if (context.Device.BatteryLevel is null)
        {
            checks.Add(new CompatibilityItem("Батарея", CompatibilitySeverity.Warning,
                "Уровень заряда неизвестен. Убедитесь, что устройство заряжено."));
        }

        if (context.Device.Driver == DriverStatus.Problem)
        {
            checks.Add(new CompatibilityItem("Драйвер", CompatibilitySeverity.Warning,
                "Драйвер USB-устройства сообщает об ошибке. Операция может прерваться."));
        }

        var free = Firmware.Library.FirmwareLibrary.GetFreeSpace(Path.GetTempPath());
        if (free.FreeBytes > 0 && free.FreeBytes < context.Package.SizeBytes * 2)
        {
            checks.Add(new CompatibilityItem("Свободное место", CompatibilitySeverity.Warning,
                $"Свободного места на {free.Root} ({SizeFormatting.HumanReadable(free.FreeBytes)}) может не хватить для подготовки образов."));
        }

        if (context.Options.WipeUserData && !context.Options.ConfirmDataWipe)
        {
            checks.Add(new CompatibilityItem("Данные пользователя", CompatibilitySeverity.Blocking,
                "Запрошено стирание данных без отдельного подтверждения."));
        }

        return checks;
    }

    public static OperationStep Informational(string title, string detail) =>
        new() { Title = title, Detail = detail, Risk = OperationRisk.Informational };

    public static OperationStep DeviceChange(string title, string detail, string? command = null) =>
        new() { Title = title, Detail = detail, Command = command, Risk = OperationRisk.ModifiesDevice };

    public static OperationStep Destructive(string title, string detail) =>
        new() { Title = title, Detail = detail, Risk = OperationRisk.Destructive };

    public static IReadOnlyList<string> DeviceSummaryLines(DeviceInfo device) =>
    [
        $"{device.DisplayName} · {device.ModeText}",
        $"Серийный номер: {device.MaskedSerial}",
        $"Состояние: {device.ConnectionText}",
        $"Загрузчик: {BootloaderText(device.BootloaderUnlocked)}"
    ];

    public static string BootloaderText(bool? unlocked) => unlocked switch
    {
        true => "разблокирован",
        false => "заблокирован",
        _ => "не определено"
    };

    public static string DeviceSummary(DeviceInfo device) =>
        $"{device.DisplayName} [{device.ModeText}] · {device.MaskedSerial}";
}
