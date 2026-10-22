using System.Formats.Tar;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.Firmware.Archives;

/// <summary>Просмотр и безопасная распаковка TAR (в том числе TAR.MD5 от Samsung).</summary>
public static class TarInspector
{
    public static ArchiveInspectionResult Inspect(Stream stream, ExtractionLimits? limits = null)
    {
        limits ??= ExtractionLimits.Default;
        var entries = new List<FirmwareArchiveEntry>();
        var blocking = new List<string>();
        var warnings = new List<string>();
        long total = 0;

        using var reader = new TarReader(stream, leaveOpen: true);

        TarEntry? entry;
        while ((entry = reader.GetNextEntry()) is not null)
        {
            var isDirectory = entry.EntryType is TarEntryType.Directory;
            var safe = PathSafety.TryNormalizeArchiveEntry(entry.Name, out _, out var reason);
            if (!safe)
            {
                blocking.Add(reason ?? $"Небезопасная запись: «{entry.Name}».");
            }

            if (entry.EntryType is TarEntryType.SymbolicLink or TarEntryType.HardLink)
            {
                blocking.Add($"Символическая/жёсткая ссылка в архиве: «{entry.Name}» — распаковка не выполняется.");
            }

            var length = entry.Length;
            if (!isDirectory)
            {
                total += length;
                if (length > limits.MaxEntryBytes)
                {
                    blocking.Add($"Запись «{entry.Name}» превышает допустимый размер.");
                }
            }

            entries.Add(new FirmwareArchiveEntry
            {
                FullName = entry.Name,
                Length = length,
                IsDirectory = isDirectory,
                LastWriteTime = entry.ModificationTime,
                IsSuspicious = !safe
            });

            if (entries.Count > limits.MaxEntries)
            {
                blocking.Add($"Слишком много записей в архиве (лимит {limits.MaxEntries}).");
                break;
            }
        }

        if (total > limits.MaxTotalBytes)
        {
            blocking.Add($"Суммарный размер распаковки превышает лимит {SizeFormatting.HumanReadable(limits.MaxTotalBytes)}.");
        }

        return new ArchiveInspectionResult
        {
            Entries = entries,
            BlockingIssues = blocking,
            Warnings = warnings,
            TotalUncompressedBytes = total
        };
    }

    public static ArchiveInspectionResult InspectFile(string tarPath, ExtractionLimits? limits = null)
    {
        using var stream = File.OpenRead(tarPath);
        return Inspect(stream, limits);
    }

    public static async Task<IReadOnlyList<string>> ExtractFileAsync(
        string tarPath,
        string destinationDirectory,
        ExtractionLimits? limits = null,
        IProgress<double>? progress = null,
        CancellationToken cancellationToken = default)
    {
        limits ??= ExtractionLimits.Default;
        var extracted = new List<string>();

        await Task.Run(() =>
        {
            using var stream = File.OpenRead(tarPath);
            var inspection = Inspect(stream, limits);
            if (!inspection.SafeToExtract)
            {
                throw new InvalidOperationException("Архив не прошёл проверку безопасности: " + string.Join("; ", inspection.BlockingIssues));
            }

            stream.Position = 0;
            Directory.CreateDirectory(destinationDirectory);

            using var reader = new TarReader(stream, leaveOpen: true);
            TarEntry? entry;
            long processed = 0;

            while ((entry = reader.GetNextEntry()) is not null)
            {
                cancellationToken.ThrowIfCancellationRequested();

                if (entry.EntryType is TarEntryType.Directory)
                {
                    continue;
                }

                if (entry.EntryType is not (TarEntryType.RegularFile or TarEntryType.V7RegularFile))
                {
                    continue;
                }

                if (!PathSafety.TryCombineInside(destinationDirectory, entry.Name, out var target))
                {
                    throw new InvalidOperationException($"Небезопасный путь в архиве: «{entry.Name}».");
                }

                var directory = Path.GetDirectoryName(target);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                entry.ExtractToFile(target, overwrite: true);
                extracted.Add(target);
                processed += entry.Length;

                if (inspection.TotalUncompressedBytes > 0)
                {
                    progress?.Report(Math.Clamp(processed * 100.0 / inspection.TotalUncompressedBytes, 0, 100));
                }
            }
        }, cancellationToken).ConfigureAwait(false);

        progress?.Report(100);
        return extracted;
    }
}
