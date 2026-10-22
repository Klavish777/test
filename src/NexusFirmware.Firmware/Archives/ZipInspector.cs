using System.IO.Compression;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.Firmware.Archives;

/// <summary>
/// Просмотр и безопасная распаковка ZIP. Проверяются имена записей (path traversal),
/// суммарный размер и коэффициент сжатия (zip-бомбы).
/// </summary>
public static class ZipInspector
{
    public static ArchiveInspectionResult Inspect(string zipPath, ExtractionLimits? limits = null)
    {
        limits ??= ExtractionLimits.Default;
        var entries = new List<FirmwareArchiveEntry>();
        var blocking = new List<string>();
        var warnings = new List<string>();
        long totalUncompressed = 0;

        using var archive = ZipFile.OpenRead(zipPath);

        if (archive.Entries.Count > limits.MaxEntries)
        {
            blocking.Add($"Слишком много записей в архиве: {archive.Entries.Count} (лимит {limits.MaxEntries}).");
        }

        foreach (var entry in archive.Entries)
        {
            var isDirectory = string.IsNullOrEmpty(entry.Name);
            var safe = PathSafety.TryNormalizeArchiveEntry(entry.FullName, out var normalized, out var reason);
            var suspicious = !safe;

            if (!safe)
            {
                blocking.Add(reason ?? $"Небезопасная запись: «{entry.FullName}».");
            }
            else if (normalized != entry.FullName.Replace('\\', '/').Trim('/'))
            {
                warnings.Add($"Имя записи нормализовано: «{entry.FullName}» → «{normalized}».");
            }

            if (!isDirectory)
            {
                totalUncompressed += entry.Length;

                if (entry.Length > limits.MaxEntryBytes)
                {
                    blocking.Add($"Запись «{entry.FullName}» превышает допустимый размер ({SizeFormatting.HumanReadable(entry.Length)}).");
                }

                if (entry.CompressedLength > 0 && entry.Length > 1024 * 1024)
                {
                    var ratio = (double)entry.Length / entry.CompressedLength;
                    if (ratio > limits.MaxCompressionRatio)
                    {
                        blocking.Add($"Подозрительный коэффициент сжатия у «{entry.FullName}»: {ratio:0}x.");
                    }
                }
            }

            entries.Add(new FirmwareArchiveEntry
            {
                FullName = entry.FullName,
                Length = entry.Length,
                CompressedLength = entry.CompressedLength,
                IsDirectory = isDirectory,
                LastWriteTime = entry.LastWriteTime,
                IsSuspicious = suspicious,
                SuspicionReason = reason
            });
        }

        if (totalUncompressed > limits.MaxTotalBytes)
        {
            blocking.Add($"Суммарный размер распаковки ({SizeFormatting.HumanReadable(totalUncompressed)}) превышает лимит {SizeFormatting.HumanReadable(limits.MaxTotalBytes)}.");
        }

        return new ArchiveInspectionResult
        {
            Entries = entries,
            BlockingIssues = blocking,
            Warnings = warnings,
            TotalUncompressedBytes = totalUncompressed
        };
    }

    /// <summary>Распаковка в каталог назначения с проверкой каждого пути. Оригинал не изменяется.</summary>
    public static async Task<IReadOnlyList<string>> ExtractAsync(
        string zipPath,
        string destinationDirectory,
        ExtractionLimits? limits = null,
        bool flattenSingleRoot = true,
        IProgress<double>? progress = null,
        CancellationToken cancellationToken = default)
    {
        limits ??= ExtractionLimits.Default;
        var inspection = Inspect(zipPath, limits);
        if (!inspection.SafeToExtract)
        {
            throw new InvalidOperationException("Архив не прошёл проверку безопасности: " + string.Join("; ", inspection.BlockingIssues));
        }

        Directory.CreateDirectory(destinationDirectory);
        var root = Path.GetFullPath(destinationDirectory);
        var extractRoot = root;

        // Если в архиве единственный корневой каталог — распаковываем его содержимое напрямую.
        if (flattenSingleRoot)
        {
            var topLevel = inspection.Entries
                .Where(e => !string.IsNullOrEmpty(e.FullName))
                .Select(e => e.FullName.Replace('\\', '/').Split('/')[0])
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();

            var hasFilesAtRoot = inspection.Entries.Any(e => !e.IsDirectory && !e.FullName.Replace('\\', '/').Contains('/'));
            if (topLevel.Length == 1 && !hasFilesAtRoot)
            {
                extractRoot = root;
            }
        }

        var extracted = new List<string>();
        long processed = 0;

        using var archive = ZipFile.OpenRead(zipPath);
        foreach (var entry in archive.Entries)
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (string.IsNullOrEmpty(entry.Name))
            {
                continue;
            }

            if (!PathSafety.TryCombineInside(extractRoot, entry.FullName, out var targetPath))
            {
                throw new InvalidOperationException($"Небезопасный путь в архиве: «{entry.FullName}».");
            }

            var directory = Path.GetDirectoryName(targetPath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            await using (var source = entry.Open())
            await using (var target = new FileStream(targetPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920, useAsync: true))
            {
                await source.CopyToAsync(target, cancellationToken).ConfigureAwait(false);
            }

            processed += entry.Length;
            extracted.Add(targetPath);

            if (inspection.TotalUncompressedBytes > 0)
            {
                progress?.Report(Math.Clamp(processed * 100.0 / inspection.TotalUncompressedBytes, 0, 100));
            }
        }

        progress?.Report(100);
        return extracted;
    }
}
