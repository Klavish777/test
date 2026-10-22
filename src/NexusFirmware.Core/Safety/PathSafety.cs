using System.Text.RegularExpressions;

namespace NexusFirmware.Core.Safety;

/// <summary>
/// Безопасная работа с путями и именами записей архивов: защита от path traversal,
/// абсолютных путей, NTFS alternate data streams и зарезервированных имён Windows.
/// </summary>
public static class PathSafety
{
    private static readonly char[] InvalidNameChars = Path.GetInvalidFileNameChars();
    private static readonly HashSet<string> ReservedNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    };

    /// <summary>Проверяет, что имя записи архива безопасно, и возвращает нормализованный относительный путь.</summary>
    public static bool TryNormalizeArchiveEntry(string entryName, out string normalized, out string? reason)
    {
        normalized = string.Empty;
        reason = null;

        if (string.IsNullOrWhiteSpace(entryName))
        {
            reason = "Пустое имя записи архива.";
            return false;
        }

        var name = entryName.Replace('\\', '/').Trim();

        if (name.StartsWith('/') || name.StartsWith('~'))
        {
            reason = $"Абсолютный путь в архиве: «{entryName}».";
            return false;
        }

        if (Regex.IsMatch(name, "^[A-Za-z]:", RegexOptions.CultureInvariant))
        {
            reason = $"Путь с буквой диска в архиве: «{entryName}».";
            return false;
        }

        if (name.Contains('\0'))
        {
            reason = "Имя записи содержит нулевой символ.";
            return false;
        }

        var segments = name.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (segments.Length == 0)
        {
            reason = "Пустое имя записи архива.";
            return false;
        }

        foreach (var segment in segments)
        {
            if (segment == "..")
            {
                reason = $"Обход каталога (path traversal) в записи «{entryName}».";
                return false;
            }

            if (segment == ".")
            {
                continue;
            }

            if (segment.IndexOfAny(InvalidNameChars) >= 0)
            {
                reason = $"Недопустимые символы в имени «{segment}».";
                return false;
            }

            if (segment.Contains(':'))
            {
                reason = $"Поток данных NTFS (alternate data stream) в имени «{segment}».";
                return false;
            }

            var stem = segment.Split('.')[0];
            if (ReservedNames.Contains(stem))
            {
                reason = $"Зарезервированное имя Windows «{segment}».";
                return false;
            }

            if (segment.Length > 255)
            {
                reason = "Слишком длинное имя записи.";
                return false;
            }
        }

        normalized = string.Join('/', segments.Where(s => s != "."));
        return normalized.Length > 0;
    }

    /// <summary>Объединяет корневой каталог и относительный путь, гарантируя нахождение результата внутри корня.</summary>
    public static bool TryCombineInside(string rootDirectory, string relativePath, out string fullPath)
    {
        fullPath = string.Empty;
        if (!TryNormalizeArchiveEntry(relativePath, out var normalized, out _))
        {
            return false;
        }

        var root = Path.GetFullPath(rootDirectory);
        if (!root.EndsWith(Path.DirectorySeparatorChar))
        {
            root += Path.DirectorySeparatorChar;
        }

        var candidate = Path.GetFullPath(Path.Combine(root, normalized.Replace('/', Path.DirectorySeparatorChar)));
        if (!candidate.StartsWith(root, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        fullPath = candidate;
        return true;
    }

    /// <summary>Проверяет, что путь существует и является файлом с допустимым расширением.</summary>
    public static bool IsExistingFile(string? path) =>
        !string.IsNullOrWhiteSpace(path) && File.Exists(path) && !IsReparsePointForbidden(path);

    public static bool IsExistingDirectory(string? path) =>
        !string.IsNullOrWhiteSpace(path) && Directory.Exists(path);

    private static bool IsReparsePointForbidden(string path)
    {
        try
        {
            var attributes = File.GetAttributes(path);
            return attributes.HasFlag(FileAttributes.Device);
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>Создаёт уникальный временный каталог внутри системного temp с читаемым префиксом.</summary>
    public static string CreateWorkDirectory(string prefix)
    {
        var safePrefix = Regex.Replace(prefix, "[^A-Za-z0-9_.-]", "_");
        if (safePrefix.Length > 40)
        {
            safePrefix = safePrefix[..40];
        }

        var path = Path.Combine(Path.GetTempPath(), "NexusFirmware", $"{safePrefix}_{Guid.NewGuid():N}");
        Directory.CreateDirectory(path);
        return path;
    }

    /// <summary>Безопасное удаление временного каталога. Ошибки не пробрасываются наружу.</summary>
    public static void TryDeleteDirectory(string? path)
    {
        if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path))
        {
            return;
        }

        try
        {
            Directory.Delete(path, recursive: true);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }
}
