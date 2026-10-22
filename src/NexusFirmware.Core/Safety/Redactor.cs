using System.Text.RegularExpressions;

namespace NexusFirmware.Core.Safety;

/// <summary>Маскирование серийных номеров, IMEI и прочих чувствительных идентификаторов в журналах.</summary>
public static partial class Redactor
{
    [GeneratedRegex("(?<![0-9A-Za-z])(\\d{15})(?![0-9])", RegexOptions.CultureInvariant)]
    private static partial Regex ImeiRegex();

    private static readonly string[] SensitiveKeys = ["imei", "meid", "serialno", "serial", "android_id", "gsf_id", "token", "password", "secret"];

    public static string MaskIdentifier(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "—";
        }

        var trimmed = value.Trim();
        if (trimmed.Length <= 4)
        {
            return new string('•', trimmed.Length);
        }

        if (trimmed.Length <= 8)
        {
            return string.Concat(trimmed.AsSpan(0, 2), new string('•', trimmed.Length - 3), trimmed.AsSpan(trimmed.Length - 1));
        }

        return string.Concat(trimmed.AsSpan(0, 3), "•".PadLeft(Math.Min(8, trimmed.Length - 6), '•'), trimmed.AsSpan(trimmed.Length - 3));
    }

    /// <summary>Маскирует 15-значные последовательности (IMEI/MEID) в произвольном тексте.</summary>
    public static string MaskText(string? text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return text ?? string.Empty;
        }

        return ImeiRegex().Replace(text, m =>
        {
            var v = m.Groups[1].Value;
            return $"{v[..2]}{new string('•', 10)}{v[^3..]}";
        });
    }

    /// <summary>Скрывает значения чувствительных ключей в выводе adb getprop и подобных источниках.</summary>
    public static string MaskKeyValueLine(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
        {
            return line;
        }

        var lower = line.ToLowerInvariant();
        foreach (var key in SensitiveKeys)
        {
            if (!lower.Contains(key, StringComparison.Ordinal))
            {
                continue;
            }

            var separatorIndex = line.IndexOfAny([':', '=']);
            if (separatorIndex > 0 && separatorIndex < line.Length - 1)
            {
                var prefix = line[..(separatorIndex + 1)];
                return $"{prefix} «скрыто»";
            }
        }

        return MaskText(line);
    }
}
