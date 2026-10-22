using NexusFirmware.Core.Models;

namespace NexusFirmware.Core.Plugins;

/// <summary>
/// Манифест модуля расширения. Загружается только при совпадении SHA-256 с манифестом
/// и при соблюдении политики доверия (см. <see cref="PluginTrustPolicy"/>).
/// </summary>
public sealed class PluginManifest
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Version { get; init; }
    public string? Author { get; init; }
    public string? Description { get; init; }
    public string AssemblyFile { get; init; } = "";
    public string EntryType { get; init; } = "";
    public string Sha256 { get; init; } = "";
    public string? Publisher { get; init; }
    public string? Homepage { get; init; }
    public IReadOnlyList<string> SupportedBrands { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> SupportedPlatforms { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> RequiredDrivers { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Operations { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> FirmwareFormats { get; init; } = Array.Empty<string>();

    /// <summary>Модели устройств, для которых заявлена поддержка (может быть пустым = все поддерживаемые транспортом).</summary>
    public IReadOnlyList<string> SupportedModels { get; init; } = Array.Empty<string>();

    /// <summary>Проверки, которые модуль выполняет перед операцией (описания, не код).</summary>
    public IReadOnlyList<string> Checks { get; init; } = Array.Empty<string>();

    /// <summary>Ограничения модуля: что он не делает и при каких условиях отказывается работать.</summary>
    public PluginLimits Limits { get; init; } = new();
    public IReadOnlyList<string> RequiredPermissions { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Limitations { get; init; } = Array.Empty<string>();
    public bool RequiresElevation { get; init; }
    public string MinimumHostVersion { get; init; } = "1.0.0";

    /// <summary>
    /// Отсоединённая подпись манифеста (RSA-SHA256, base64) — файл <c>{AssemblyFile}.sig</c>.
    /// Проверяется, если для издателя сохранён открытый ключ.
    /// </summary>
    public string? Signature { get; init; }

    /// <summary>Строка, которую подписывает издатель. Порядок полей фиксирован.</summary>
    public string SigningPayload =>
        $"{Id}|{Version}|{Sha256?.ToLowerInvariant()}|{Publisher}";
}

/// <summary>Контракт модуля расширения: ядро не знает о конкретных брендах.</summary>
public interface INexusPlugin
{
    PluginManifest Manifest { get; }

    /// <summary>Проверки совместимости для конкретного устройства. Не изменяет устройство.</summary>
    IReadOnlyList<CompatibilityItem> CheckCompatibility(DeviceInfo device);

    /// <summary>Доступные операции модуля для устройства (только описания, без выполнения).</summary>
    IReadOnlyList<string> DescribeOperations(DeviceInfo device);
}

public enum PluginTrustDecision
{
    Trusted = 0,
    HashMismatch,
    UntrustedPublisher,
    Unsigned,
    InvalidManifest,
    NotAllowedByPolicy,
    SignatureInvalid
}

public sealed record PluginValidationResult(
    PluginTrustDecision Decision,
    string Message,
    PluginManifest? Manifest = null,
    string? AssemblyPath = null)
{
    public bool IsTrusted => Decision == PluginTrustDecision.Trusted;
}

/// <summary>Пределы, которые модуль объявляет о себе. Используются для проверок и для интерфейса.</summary>
public sealed class PluginLimits
{
    /// <summary>Максимальный размер файла прошивки, с которым модуль согласен работать.</summary>
    public long MaxFirmwareSizeBytes { get; init; } = 8L * 1024 * 1024 * 1024;

    /// <summary>Заявляет ли модуль операции записи на устройство (требует доверия и подтверждений).</summary>
    public bool CanWriteDevice { get; init; }

    /// <summary>Требуется ли сетевой доступ.</summary>
    public bool RequiresNetwork { get; init; }

    /// <summary>Разделы, с которыми модуль умеет работать. Пусто = не ограничено объявлением.</summary>
    public IReadOnlyList<string> AllowedPartitions { get; init; } = Array.Empty<string>();

    public string Summary =>
        $"файл ≤ {NexusFirmware.Core.Models.SizeFormatting.HumanReadable(MaxFirmwareSizeBytes)}" +
        (CanWriteDevice ? ", запись на устройство" : ", только чтение") +
        (RequiresNetwork ? ", нужен интернет" : ", без сети");
}
