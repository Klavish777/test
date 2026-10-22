namespace NexusFirmware.Firmware.Archives;

/// <summary>Лимиты распаковки: защита от zip-бомб и переполнения диска.</summary>
public sealed class ExtractionLimits
{
    public long MaxTotalBytes { get; init; } = 32L * 1024 * 1024 * 1024;

    public long MaxEntryBytes { get; init; } = 16L * 1024 * 1024 * 1024;

    public int MaxEntries { get; init; } = 20_000;

    public double MaxCompressionRatio { get; init; } = 1000;

    public static ExtractionLimits Default { get; } = new();
}

public sealed class ArchiveInspectionResult
{
    public required IReadOnlyList<NexusFirmware.Core.Models.FirmwareArchiveEntry> Entries { get; init; }
    public required IReadOnlyList<string> BlockingIssues { get; init; }
    public required IReadOnlyList<string> Warnings { get; init; }
    public long TotalUncompressedBytes { get; init; }
    public bool SafeToExtract => BlockingIssues.Count == 0;
}
