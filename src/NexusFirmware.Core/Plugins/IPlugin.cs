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
    public IReadOnlyList<string> RequiredPermissions { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Limitations { get; init; } = Array.Empty<string>();
    public bool RequiresElevation { get; init; }
    public string MinimumHostVersion { get; init; } = "1.0.0";
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
    NotAllowedByPolicy
}

public sealed record PluginValidationResult(
    PluginTrustDecision Decision,
    string Message,
    PluginManifest? Manifest = null,
    string? AssemblyPath = null)
{
    public bool IsTrusted => Decision == PluginTrustDecision.Trusted;
}
