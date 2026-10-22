using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Firmware.Scatter;

/// <summary>Запись scatter-файла MediaTek.</summary>
public sealed class ScatterEntry
{
    public int Index { get; init; }
    public required string PartitionName { get; init; }
    public string? FileName { get; init; }
    public string? Type { get; init; }
    public string? Region { get; init; }
    public string? Storage { get; init; }
    public string? OperationType { get; init; }
    public bool? IsDownload { get; init; }
    public bool? IsUpgradable { get; init; }
    public bool? IsReserved { get; init; }
    public long? LinearStartAddress { get; init; }
    public long? PartitionSize { get; init; }
    public string? BoundaryCheck { get; init; }
    public string? RawLine { get; init; }
}

public sealed class ScatterFile
{
    public required string FilePath { get; init; }
    public string? Platform { get; init; }
    public string? Project { get; init; }
    public string? Storage { get; init; }
    public IReadOnlyDictionary<string, string> General { get; init; } = new Dictionary<string, string>();
    public IReadOnlyList<ScatterEntry> Partitions { get; init; } = Array.Empty<ScatterEntry>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public long TotalDeclaredBytes => Partitions.Sum(p => p.PartitionSize ?? 0);
}

/// <summary>
/// Разбор MediaTek scatter-файла (текстовый YAML-подобный формат). Только чтение,
/// никаких операций записи и обхода защит (SLA/DAA) не выполняется.
/// </summary>
public static class ScatterParser
{
    private static readonly Regex KeyValueRegex = new(@"^\s*[-]?\s*(?<key>[A-Za-z_]+)\s*:\s*(?<value>.*)$", RegexOptions.CultureInvariant);

    public static bool LooksLikeScatter(string path)
    {
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            using var reader = new StreamReader(path, Encoding.UTF8, true);
            for (var i = 0; i < 20; i++)
            {
                var line = reader.ReadLine();
                if (line is null)
                {
                    break;
                }

                if (line.Contains("MTK_PLATFORM", StringComparison.OrdinalIgnoreCase) ||
                    line.Contains("partition_index", StringComparison.OrdinalIgnoreCase) ||
                    line.TrimStart().StartsWith("- partition_name", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
        }
        catch (IOException)
        {
        }

        return false;
    }

    public static ScatterFile Parse(string path)
    {
        var text = File.ReadAllText(path, Encoding.UTF8);
        return ParseText(text, path);
    }

    public static ScatterFile ParseText(string text, string path = "<memory>")
    {
        var warnings = new List<string>();
        var general = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var partitions = new List<ScatterEntry>();

        var current = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var inGeneral = false;
        string? platform = null;
        string? project = null;
        string? storage = null;

        void FlushPartition()
        {
            if (current.Count == 0 || !current.TryGetValue("partition_name", out var name) || string.IsNullOrWhiteSpace(name))
            {
                current.Clear();
                return;
            }

            partitions.Add(new ScatterEntry
            {
                Index = parseIntSafe(current.GetValueOrDefault("partition_index")) is { } idx ? idx : partitions.Count,
                PartitionName = name.Trim(),
                FileName = emptyToNull(current.GetValueOrDefault("file_name")),
                Type = emptyToNull(current.GetValueOrDefault("type")),
                Region = emptyToNull(current.GetValueOrDefault("region")),
                Storage = emptyToNull(current.GetValueOrDefault("storage")),
                OperationType = emptyToNull(current.GetValueOrDefault("operation_type")),
                IsDownload = parseBool(current.GetValueOrDefault("is_download")),
                IsUpgradable = parseBool(current.GetValueOrDefault("is_upgradable")),
                IsReserved = parseBool(current.GetValueOrDefault("is_reserved")),
                LinearStartAddress = parseHex(current.GetValueOrDefault("linear_start_addr")),
                PartitionSize = parseHex(current.GetValueOrDefault("partition_size")),
                BoundaryCheck = emptyToNull(current.GetValueOrDefault("boundary_check")),
                RawLine = current.GetValueOrDefault("__line")
            });

            current.Clear();
        }

        foreach (var rawLine in text.Split('\n'))
        {
            var line = rawLine.TrimEnd('\r');
            if (line.Length == 0 || line.TrimStart().StartsWith('#'))
            {
                continue;
            }

            if (line.TrimStart().StartsWith("- partition_index", StringComparison.OrdinalIgnoreCase))
            {
                FlushPartition();
                inGeneral = false;
            }
            else if (line.TrimStart().StartsWith("- general", StringComparison.OrdinalIgnoreCase) ||
                     line.TrimStart().StartsWith("-general", StringComparison.OrdinalIgnoreCase))
            {
                FlushPartition();
                inGeneral = true;
                continue;
            }

            var match = KeyValueRegex.Match(line);
            if (!match.Success)
            {
                continue;
            }

            var key = match.Groups["key"].Value.Trim();
            var value = match.Groups["value"].Value.Trim();

            if (inGeneral && key is not ("general" or "partition_index"))
            {
                if (key.Equals("platform", StringComparison.OrdinalIgnoreCase))
                {
                    platform = emptyToNull(value);
                }
                else if (key.Equals("project", StringComparison.OrdinalIgnoreCase))
                {
                    project = emptyToNull(value);
                }
                else if (key.Equals("storage", StringComparison.OrdinalIgnoreCase))
                {
                    storage = emptyToNull(value);
                }

                general[key] = value;
                continue;
            }

            if (!inGeneral)
            {
                current[key] = value;
                current["__line"] = line.Trim();
            }
        }

        FlushPartition();

        if (platform is null)
        {
            warnings.Add("В scatter-файле не найдена платформа (MTK_PLATFORM). Совместимость с устройством определить нельзя.");
        }

        if (partitions.Count == 0)
        {
            warnings.Add("В scatter-файле не найдено ни одного раздела.");
        }

        var duplicates = partitions
            .GroupBy(p => p.PartitionName, StringComparer.OrdinalIgnoreCase)
            .Where(g => g.Count() > 1)
            .Select(g => g.Key)
            .ToArray();

        if (duplicates.Length > 0)
        {
            warnings.Add("Повторяющиеся разделы в scatter: " + string.Join(", ", duplicates));
        }

        return new ScatterFile
        {
            FilePath = path,
            Platform = platform,
            Project = project,
            Storage = storage,
            General = general,
            Partitions = partitions,
            Warnings = warnings
        };
    }

    /// <summary>Проверка наличия файлов образов рядом со scatter или в каталоге пакета.</summary>
    public static IReadOnlyList<ScatterFileCheck> VerifyFiles(ScatterFile scatter, string directory)
    {
        var checks = new List<ScatterFileCheck>();
        foreach (var partition in scatter.Partitions)
        {
            if (string.IsNullOrWhiteSpace(partition.FileName))
            {
                continue;
            }

            var candidate = Path.Combine(directory, partition.FileName);
            var exists = File.Exists(candidate);
            long? size = exists ? new FileInfo(candidate).Length : null;

            checks.Add(new ScatterFileCheck(
                partition.PartitionName,
                partition.FileName,
                exists,
                size,
                partition.PartitionSize,
                exists && partition.PartitionSize is > 0 && size > partition.PartitionSize
                    ? "Размер файла больше указанного в scatter."
                    : null));
        }

        return checks;
    }

    private static int? parseIntSafe(string? value) =>
        int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed) ? parsed : null;

    private static long? parseHex(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var cleaned = value.Trim();
        if (cleaned.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            cleaned = cleaned[2..];
            return long.TryParse(cleaned, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var hex) ? hex : null;
        }

        return long.TryParse(cleaned, NumberStyles.Integer, CultureInfo.InvariantCulture, out var dec) ? dec : null;
    }

    private static bool? parseBool(string? value) => value?.Trim().ToLowerInvariant() switch
    {
        "true" or "yes" or "1" => true,
        "false" or "no" or "0" => false,
        _ => null
    };

    private static string? emptyToNull(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();
}

public sealed record ScatterFileCheck(
    string PartitionName,
    string FileName,
    bool FileExists,
    long? ActualSize,
    long? DeclaredSize,
    string? Problem);
