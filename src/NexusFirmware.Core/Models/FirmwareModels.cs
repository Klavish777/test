namespace NexusFirmware.Core.Models;

public enum FirmwareFormat
{
    Unknown = 0,
    Zip,
    Tar,
    TarMd5,
    Gzip,
    Lz4,
    Image,
    SparseImage,
    PayloadBin,
    SamsungAp,
    SamsungBl,
    SamsungCp,
    SamsungCsc,
    SamsungHomeCsc,
    Scatter,
    RawProgramXml,
    Elf,
    Executable,
    Text
}

public enum IntegrityState
{
    Unknown = 0,
    NotVerified,
    Verified,
    Failed
}

public sealed class FirmwareFileRecord
{
    public required string FullPath { get; init; }
    public required string FileName { get; init; }
    public long SizeBytes { get; init; }
    public string? Sha256 { get; init; }
    public FirmwareFormat Format { get; init; } = FirmwareFormat.Unknown;
    public DateTimeOffset LastWriteTime { get; init; }
    public IReadOnlyDictionary<string, string> Metadata { get; init; } = new Dictionary<string, string>();

    public string SizeText => SizeFormatting.HumanReadable(SizeBytes);
}

public sealed class FirmwarePackage
{
    public required string Id { get; init; }
    public required string DisplayName { get; init; }
    public string? Manufacturer { get; init; }
    public string? Model { get; init; }
    public string? Region { get; init; }
    public string? Version { get; init; }
    public string? BuildNumber { get; init; }
    public string? AndroidVersion { get; init; }
    public string? Codename { get; init; }
    public FirmwareFormat Format { get; init; } = FirmwareFormat.Unknown;
    public string? FilePath { get; init; }
    public long SizeBytes { get; init; }
    public string? Sha256 { get; init; }
    public IntegrityState Integrity { get; init; } = IntegrityState.Unknown;
    public string? Notes { get; init; }
    public string? Source { get; init; }
    public bool IsUserProvided { get; init; }
    public DateTimeOffset ImportedAt { get; init; } = DateTimeOffset.Now;
    public DateTimeOffset LastCheckedAt { get; init; } = DateTimeOffset.Now;
    public IReadOnlyList<FirmwareComponent> Components { get; init; } = Array.Empty<FirmwareComponent>();
    public IReadOnlyDictionary<string, string> Metadata { get; init; } = new Dictionary<string, string>();

    public string FormatText => Format switch
    {
        FirmwareFormat.Zip => "ZIP-архив",
        FirmwareFormat.Tar => "TAR-архив",
        FirmwareFormat.TarMd5 => "TAR.MD5 (Samsung)",
        FirmwareFormat.Gzip => "GZip",
        FirmwareFormat.Lz4 => "LZ4",
        FirmwareFormat.Image => "RAW image",
        FirmwareFormat.SparseImage => "Android sparse image",
        FirmwareFormat.PayloadBin => "payload.bin (OTA)",
        FirmwareFormat.SamsungAp => "Samsung AP",
        FirmwareFormat.SamsungBl => "Samsung BL",
        FirmwareFormat.SamsungCp => "Samsung CP",
        FirmwareFormat.SamsungCsc => "Samsung CSC",
        FirmwareFormat.SamsungHomeCsc => "Samsung HOME_CSC",
        FirmwareFormat.Scatter => "MediaTek scatter",
        FirmwareFormat.RawProgramXml => "Qualcomm rawprogram XML",
        FirmwareFormat.Elf => "ELF",
        FirmwareFormat.Executable => "Исполняемый файл",
        FirmwareFormat.Text => "Текстовый файл",
        _ => "Неизвестный формат"
    };

    public string SizeText => SizeFormatting.HumanReadable(SizeBytes);

    public string IntegrityText => Integrity switch
    {
        IntegrityState.Verified => "SHA-256 подтверждён",
        IntegrityState.Failed => "SHA-256 не совпадает",
        IntegrityState.NotVerified => "Не проверялся",
        _ => "Неизвестно"
    };
}

public sealed class FirmwareComponent
{
    public required string Name { get; init; }
    public required string FileName { get; init; }
    public long? SizeBytes { get; init; }
    public FirmwareFormat Format { get; init; }
    public string? Sha256 { get; init; }
    public string? Partition { get; init; }
    public string? Version { get; init; }
}

public sealed class FirmwareArchiveEntry
{
    public required string FullName { get; init; }
    public long Length { get; init; }
    public long? CompressedLength { get; init; }
    public bool IsDirectory { get; init; }
    public DateTimeOffset? LastWriteTime { get; init; }
    public bool IsSuspicious { get; init; }
    public string? SuspicionReason { get; init; }
}

public sealed class CompatibilityCheckResult
{
    public required IReadOnlyList<CompatibilityItem> Items { get; init; }

    public bool IsCompatible => Items.All(i => i.Severity != CompatibilitySeverity.Blocking);

    public int BlockingCount => Items.Count(i => i.Severity == CompatibilitySeverity.Blocking);

    public int WarningCount => Items.Count(i => i.Severity == CompatibilitySeverity.Warning);
}

public enum CompatibilitySeverity
{
    Info = 0,
    Warning,
    Blocking
}

public sealed record CompatibilityItem(string Check, CompatibilitySeverity Severity, string Message);

public static class SizeFormatting
{
    public static string HumanReadable(long bytes)
    {
        if (bytes < 0)
        {
            return "—";
        }

        string[] units = ["Б", "КБ", "МБ", "ГБ", "ТБ"];
        double value = bytes;
        var unit = 0;
        while (value >= 1024 && unit < units.Length - 1)
        {
            value /= 1024;
            unit++;
        }

        return unit == 0
            ? $"{bytes} {units[unit]}"
            : $"{value:0.##} {units[unit]}";
    }
}
