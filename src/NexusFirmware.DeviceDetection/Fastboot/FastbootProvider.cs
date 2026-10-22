using System.Text.RegularExpressions;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;

namespace NexusFirmware.DeviceDetection.Fastboot;

/// <summary>Обнаружение устройств в режиме fastboot и чтение переменных загрузчика.</summary>
public sealed class FastbootProvider : IDeviceProvider
{
    private readonly IProcessRunner _runner;
    private readonly IToolLocator _locator;
    private readonly ILogBus _log;

    public FastbootProvider(IProcessRunner runner, IToolLocator locator, ILogBus log)
    {
        _runner = runner;
        _locator = locator;
        _log = log;
    }

    public string ProviderId => "fastboot";

    public string DisplayName => "Fastboot";

    public string? FastbootPath => _locator.Find("fastboot");

    public Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult(FastbootPath is not null);

    public async Task<IReadOnlyList<DeviceInfo>> DiscoverAsync(CancellationToken cancellationToken = default)
    {
        var fastboot = FastbootPath;
        if (fastboot is null)
        {
            return Array.Empty<DeviceInfo>();
        }

        var result = await _runner.RunAsync(new ProcessRequest
        {
            FileName = fastboot,
            Arguments = ["devices"],
            Timeout = TimeSpan.FromSeconds(12),
            Description = "fastboot devices"
        }, cancellationToken).ConfigureAwait(false);

        if (!result.Started)
        {
            _log.Warn("Fastboot", $"Не удалось запустить fastboot: {result.StartError}");
            return Array.Empty<DeviceInfo>();
        }

        var devices = ParseDeviceList(result.CombinedOutput);
        var enriched = new List<DeviceInfo>();

        foreach (var device in devices)
        {
            enriched.Add(await EnrichAsync(device, fastboot, cancellationToken).ConfigureAwait(false));
        }

        return enriched;
    }

    private async Task<DeviceInfo> EnrichAsync(DeviceInfo device, string fastboot, CancellationToken cancellationToken)
    {
        var varsTask = _runner.RunAsync(new ProcessRequest
        {
            FileName = fastboot,
            Arguments = ["-s", device.Serial!, "getvar", "all"],
            Timeout = TimeSpan.FromSeconds(20),
            Description = "fastboot getvar all"
        }, cancellationToken);

        var productTask = _runner.RunAsync(new ProcessRequest
        {
            FileName = fastboot,
            Arguments = ["-s", device.Serial!, "getvar", "product"],
            Timeout = TimeSpan.FromSeconds(10),
            Description = "fastboot getvar product"
        }, cancellationToken);

        await Task.WhenAll(varsTask, productTask).ConfigureAwait(false);

        var vars = ParseGetVarOutput(varsTask.Result.CombinedOutput + Environment.NewLine + productTask.Result.CombinedOutput);

        vars.TryGetValue("product", out var product);
        vars.TryGetValue("unlocked", out var unlocked);
        vars.TryGetValue("secure", out var secure);
        vars.TryGetValue("current-slot", out var slot);
        vars.TryGetValue("version-bootloader", out var bootloader);
        vars.TryGetValue("serialno", out var serialNo);
        vars.TryGetValue("battery-voltage", out var batteryVoltage);
        vars.TryGetValue("max-download-size", out var maxDownload);

        bool? unlockedValue = unlocked?.ToLowerInvariant() switch
        {
            "yes" or "true" or "1" => true,
            "no" or "false" or "0" => false,
            _ => null
        };

        var warnings = new List<string>();
        if (secure is not null && secure.Equals("yes", StringComparison.OrdinalIgnoreCase))
        {
            warnings.Add("Загрузчик сообщает secure=yes — часть операций записи может быть заблокирована производителем.");
        }

        if (unlockedValue == false)
        {
            warnings.Add("Загрузчик заблокирован: fastboot flash недоступен без официальной разблокировки.");
        }

        if (int.TryParse(batteryVoltage, out var millivolts) && millivolts > 0)
        {
            warnings.Add($"Напряжение батареи (по данным загрузчика): {millivolts} мВ.");
        }

        return new DeviceInfo
        {
            Id = device.Id,
            Transport = DeviceTransport.Fastboot,
            Mode = DeviceMode.Fastboot,
            Connection = device.Connection,
            Serial = serialNo ?? device.Serial,
            Codename = product,
            Model = product,
            Platform = vars.GetValueOrDefault("platform"),
            Slot = slot,
            BootloaderVersion = bootloader,
            BootloaderUnlocked = unlockedValue,
            Driver = DriverStatus.Ok,
            DriverName = "Android Bootloader Interface",
            DetectedAt = DateTimeOffset.Now,
            Warnings = warnings,
            Capabilities =
            [
                "Fastboot-переменные",
                "Разделы и слоты (чтение)",
                "Перезагрузка в режимы"
            ],
            UsbDevicePath = maxDownload is null ? null : $"max-download-size={maxDownload}",
            BuildId = bootloader is null ? null : $"bootloader {bootloader}"
        };
    }

    /// <summary>Разбор вывода fastboot getvar: строки вида «(bootloader) key: value».</summary>
    public static IReadOnlyDictionary<string, string> ParseGetVarOutput(string output)
    {
        var vars = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(output))
        {
            return vars;
        }

        foreach (var line in output.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var match = Regex.Match(line, @"^\s*(?:\(bootloader\)\s*)?(?<key>[A-Za-z0-9_.\-]+)\s*:\s*(?<value>.*)$", RegexOptions.CultureInvariant);
            if (!match.Success)
            {
                continue;
            }

            var key = match.Groups["key"].Value.Trim();
            var value = match.Groups["value"].Value.Trim();
            if (key.Length == 0 || key.Equals("finished", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            vars[key] = value;
        }

        return vars;
    }

    /// <summary>Разбор вывода «fastboot devices».</summary>
    public static IReadOnlyList<DeviceInfo> ParseDeviceList(string output)
    {
        var devices = new List<DeviceInfo>();
        if (string.IsNullOrWhiteSpace(output))
        {
            return devices;
        }

        foreach (var rawLine in output.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith('<') || line.StartsWith('*'))
            {
                continue;
            }

            var parts = line.Split('\t', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2)
            {
                parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            }

            if (parts.Length < 2)
            {
                continue;
            }

            var serial = parts[0];
            var state = parts[1].ToLowerInvariant();
            var connection = state.Contains("fastboot", StringComparison.Ordinal)
                ? ConnectionState.Connected
                : state.Contains("unauthorized", StringComparison.Ordinal)
                    ? ConnectionState.Unauthorized
                    : ConnectionState.Unknown;

            devices.Add(new DeviceInfo
            {
                Id = $"fastboot:{serial}",
                Transport = DeviceTransport.Fastboot,
                Mode = DeviceMode.Fastboot,
                Connection = connection,
                Serial = serial,
                DetectedAt = DateTimeOffset.Now,
                Driver = DriverStatus.Unknown
            });
        }

        return devices;
    }
}
