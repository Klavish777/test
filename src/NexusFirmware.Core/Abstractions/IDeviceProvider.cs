using NexusFirmware.Core.Models;

namespace NexusFirmware.Core.Abstractions;

/// <summary>Источник сведений об устройствах (ADB, Fastboot, USB-перечисление и т.п.).</summary>
public interface IDeviceProvider
{
    string ProviderId { get; }

    string DisplayName { get; }

    /// <summary>true, если источник реально доступен в системе (например, найден adb.exe).</summary>
    Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default);

    Task<IReadOnlyList<DeviceInfo>> DiscoverAsync(CancellationToken cancellationToken = default);
}

public sealed class DeviceDiscoverySnapshot
{
    public required IReadOnlyList<DeviceInfo> Devices { get; init; }
    public required IReadOnlyList<ProviderStatus> Providers { get; init; }
    public DateTimeOffset TakenAt { get; init; } = DateTimeOffset.Now;
}

public sealed record ProviderStatus(string ProviderId, string DisplayName, bool Available, string? Note);
