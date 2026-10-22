namespace NexusFirmware.Core.Localization;

/// <summary>
/// Двуязычные подписи интерфейса. Русский — основной язык, английский — запасной.
/// Значения даны парами, чтобы интерфейс можно было переключать без перезапуска.
/// </summary>
public static class Localizer
{
    public enum Language
    {
        Russian = 0,
        English = 1
    }

    public static Language Current { get; set; } = Language.Russian;

    private static readonly Dictionary<string, (string Ru, string En)> Strings = new(StringComparer.Ordinal)
    {
        ["App.Title"] = ("NEXUS Firmware Studio", "NEXUS Firmware Studio"),
        ["Nav.Dashboard"] = ("Панель управления", "Dashboard"),
        ["Nav.Devices"] = ("Диспетчер устройств", "Device Manager"),
        ["Nav.Firmware"] = ("Центр прошивок", "Firmware Center"),
        ["Nav.Flashing"] = ("Станция прошивки", "Flashing Station"),
        ["Nav.Adb"] = ("ADB и Fastboot", "ADB & Fastboot"),
        ["Nav.Qualcomm"] = ("Сервис Qualcomm", "Qualcomm Service"),
        ["Nav.MediaTek"] = ("Сервис MediaTek", "MediaTek Service"),
        ["Nav.Samsung"] = ("Сервис Samsung", "Samsung Service"),
        ["Nav.Extractor"] = ("Извлечение прошивок", "Firmware Extractor"),
        ["Nav.Partitions"] = ("Разделы", "Partitions Manager"),
        ["Nav.Logs"] = ("Журналы и диагностика", "Logs & Diagnostics"),
        ["Nav.Drivers"] = ("Центр драйверов", "Drivers Center"),
        ["Nav.Plugins"] = ("Плагины", "Plugins"),
        ["Nav.Settings"] = ("Настройки", "Settings"),
        ["Common.NoDevice"] = ("Устройство не выбрано", "No device selected"),
        ["Common.Refresh"] = ("Обновить", "Refresh"),
        ["Common.Cancel"] = ("Отмена", "Cancel"),
        ["Common.Close"] = ("Закрыть", "Close"),
        ["Common.Unavailable"] = ("Недоступно", "Unavailable"),
        ["Common.Yes"] = ("Да", "Yes"),
        ["Common.No"] = ("Нет", "No")
    };

    public static string T(string key)
    {
        if (!Strings.TryGetValue(key, out var pair))
        {
            return key;
        }

        return Current == Language.Russian ? pair.Ru : pair.En;
    }

    public static IReadOnlyCollection<string> Keys => Strings.Keys;
}
