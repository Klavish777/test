using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection.Usb;

namespace NexusFirmware.DeviceDetection;

/// <summary>
/// Объединённое обнаружение устройств: ADB, Fastboot и перечисление USB Windows.
/// Не подменяет отсутствующие сведения: если источник недоступен, это явно видно в статусе.
/// </summary>
public sealed class DeviceDiscoveryService
{
    private readonly IReadOnlyList<IDeviceProvider> _providers;
    private readonly WindowsUsbEnumerator _usbEnumerator;
    private readonly IToolLocator _locator;
    private readonly ILogBus _log;
    private readonly SemaphoreSlim _gate = new(1, 1);

    public DeviceDiscoveryService(
        IEnumerable<IDeviceProvider> providers,
        WindowsUsbEnumerator usbEnumerator,
        IToolLocator locator,
        ILogBus log)
    {
        _providers = providers.ToArray();
        _usbEnumerator = usbEnumerator;
        _locator = locator;
        _log = log;
    }

    public async Task<DeviceDiscoverySnapshot> ScanAsync(CancellationToken cancellationToken = default)
    {
        if (!await _gate.WaitAsync(0, cancellationToken).ConfigureAwait(false))
        {
            // Предыдущее сканирование ещё идёт — не запускаем параллельное.
            return new DeviceDiscoverySnapshot { Devices = Array.Empty<DeviceInfo>(), Providers = Array.Empty<ProviderStatus>() };
        }

        try
        {
            var statuses = new List<ProviderStatus>();
            var devices = new List<DeviceInfo>();

            foreach (var provider in _providers)
            {
                var available = await provider.IsAvailableAsync(cancellationToken).ConfigureAwait(false);
                if (!available)
                {
                    statuses.Add(new ProviderStatus(provider.ProviderId, provider.DisplayName, false, "Инструмент не найден"));
                    continue;
                }

                try
                {
                    var found = await provider.DiscoverAsync(cancellationToken).ConfigureAwait(false);
                    devices.AddRange(found);
                    statuses.Add(new ProviderStatus(provider.ProviderId, provider.DisplayName, true,
                        found.Count == 0 ? "Инструмент доступен, устройств нет" : $"Устройств: {found.Count}"));
                }
                catch (OperationCanceledException)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    statuses.Add(new ProviderStatus(provider.ProviderId, provider.DisplayName, false, "Ошибка: " + ex.Message));
                    _log.Error("Discovery", $"Ошибка источника {provider.ProviderId}: {ex.Message}");
                }
            }

            if (_usbEnumerator.IsSupported)
            {
                try
                {
                    var usb = await _usbEnumerator.EnumerateAsync(cancellationToken).ConfigureAwait(false);
                    var adbOrFastbootSerials = devices
                        .Where(d => d.Transport is DeviceTransport.Adb or DeviceTransport.Fastboot)
                        .Select(d => d.Serial)
                        .Where(s => !string.IsNullOrWhiteSpace(s))
                        .ToHashSet(StringComparer.OrdinalIgnoreCase);

                    // USB-интерфейсы ADB/Fastboot отражаются отдельными строками только если это
                    // диагностические режимы (EDL, preloader, download) — обычные ADB-интерфейсы не дублируем.
                    foreach (var descriptor in usb)
                    {
                        var isDiagnostic =
                            (descriptor.VendorId == KnownUsbIdentifiers.QualcommVendorId && descriptor.ProductId == KnownUsbIdentifiers.QualcommEdlProductId) ||
                            descriptor.VendorId == KnownUsbIdentifiers.MediaTekVendorId ||
                            string.Equals(descriptor.Service, "SAMSUNG_USB_Download_Mode", StringComparison.OrdinalIgnoreCase);

                        if (!isDiagnostic && adbOrFastbootSerials.Count > 0)
                        {
                            continue;
                        }

                        if (isDiagnostic)
                        {
                            devices.Add(WindowsUsbEnumerator.ToDeviceInfo(descriptor));
                        }
                    }

                    statuses.Add(new ProviderStatus("usb", "USB (Windows PnP)", true, $"USB-устройств: {usb.Count}"));
                }
                catch (Exception ex)
                {
                    statuses.Add(new ProviderStatus("usb", "USB (Windows PnP)", false, "Ошибка: " + ex.Message));
                }
            }
            else
            {
                statuses.Add(new ProviderStatus("usb", "USB (Windows PnP)", false, "Перечисление USB доступно только в Windows"));
            }

            var ordered = devices
                .GroupBy(d => d.Id)
                .Select(g => g.First())
                .OrderBy(d => d.Transport)
                .ThenBy(d => d.MaskedSerial)
                .ToArray();

            return new DeviceDiscoverySnapshot
            {
                Devices = ordered,
                Providers = statuses,
                TakenAt = DateTimeOffset.Now
            };
        }
        finally
        {
            _gate.Release();
        }
    }

    public bool AdbAvailable => _locator.Find("adb") is not null;

    public bool FastbootAvailable => _locator.Find("fastboot") is not null;

    public string? AdbPath => _locator.Find("adb");

    public string? FastbootPath => _locator.Find("fastboot");
}
