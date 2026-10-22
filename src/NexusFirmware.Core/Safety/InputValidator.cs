using System.Text.RegularExpressions;

namespace NexusFirmware.Core.Safety;

/// <summary>Проверка пользовательского ввода перед передачей во внешние инструменты.</summary>
public static partial class InputValidator
{
    [GeneratedRegex("^[A-Za-z0-9._\\-]{1,128}$", RegexOptions.CultureInvariant)]
    private static partial Regex SerialRegex();

    [GeneratedRegex("^[A-Za-z0-9._:\\-]{1,256}$", RegexOptions.CultureInvariant)]
    private static partial Regex PropertyRegex();

    /// <summary>Серийный номер / идентификатор устройства для передачи в adb -s.</summary>
    public static bool IsValidSerial(string? serial) => !string.IsNullOrWhiteSpace(serial) && SerialRegex().IsMatch(serial);

    /// <summary>Ключ свойства Android (ro.product.model и т.п.).</summary>
    public static bool IsValidPropertyKey(string? key) => !string.IsNullOrWhiteSpace(key) && PropertyRegex().IsMatch(key);

    /// <summary>Раздел для fastboot (латиница, цифры, подчёркивание).</summary>
    public static bool IsValidPartitionName(string? name) =>
        !string.IsNullOrWhiteSpace(name) && Regex.IsMatch(name, "^[a-z0-9_]{1,64}$", RegexOptions.CultureInvariant);

    /// <summary>Путь к локальному файлу: существует, не является каталогом, разумный размер.</summary>
    public static bool IsReadableFile(string? path, long maxBytes = 64L * 1024 * 1024 * 1024)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }

        try
        {
            var info = new FileInfo(path);
            return info.Exists && info.Length > 0 && info.Length <= maxBytes;
        }
        catch (Exception)
        {
            return false;
        }
    }

    public static string SanitizeFileName(string? fileName, string fallback = "file")
    {
        if (string.IsNullOrWhiteSpace(fileName))
        {
            return fallback;
        }

        var name = Path.GetFileName(fileName.Trim());
        foreach (var c in Path.GetInvalidFileNameChars())
        {
            name = name.Replace(c, '_');
        }

        name = name.Trim('.', ' ');
        return string.IsNullOrWhiteSpace(name) ? fallback : name;
    }
}
