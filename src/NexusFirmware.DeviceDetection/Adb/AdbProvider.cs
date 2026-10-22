using System.Text.RegularExpressions;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.DeviceDetection.Adb;

/// <summary>
/// Обнаружение устройств через Android Debug Bridge. Никаких обходов подтверждения ADB:
/// устройство в состоянии unauthorized показывается именно так.
/// </summary>
public sealed partial class AdbProvider : IDeviceProvider
{
    private readonly IProcessRunner _runner;
    private readonly IToolLocator _locator;
    private readonly ILogBus _log;

    public AdbProvider(IProcessRunner runner, IToolLocator locator, ILogBus log)
    {
        _runner = runner;
        _locator = locator;
        _log = log;
    }

    public string ProviderId => "adb";

    public string DisplayName => "ADB (Android Debug Bridge)";

    public string? AdbPath => _locator.Find("adb");

    public Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(AdbPath is not null);
    }

    public async Task<IReadOnlyList<DeviceInfo>> DiscoverAsync(CancellationToken cancellationToken = default)
    {
        var adb = AdbPath;
        if (adb is null)
        {
            return Array.Empty<DeviceInfo>();
        }

        var result = await _runner.RunAsync(new ProcessRequest
        {
            FileName = adb,
            Arguments = ["devices", "-l"],
            Timeout = TimeSpan.FromSeconds(12),
            Description = "adb devices -l"
        }, cancellationToken).ConfigureAwait(false);

        if (!result.Started)
        {
            _log.Warn("ADB", $"Не удалось запустить adb: {result.StartError}");
            return Array.Empty<DeviceInfo>();
        }

        var devices = ParseDeviceList(result.CombinedOutput);
        var enriched = new List<DeviceInfo>(devices.Count);

        foreach (var device in devices)
        {
            if (device.Connection == ConnectionState.Connected && InputValidator.IsValidSerial(device.Serial))
            {
                enriched.Add(await EnrichAsync(device, adb, cancellationToken).ConfigureAwait(false));
            }
            else
            {
                enriched.Add(device);
            }
        }

        return enriched;
    }

    private async Task<DeviceInfo> EnrichAsync(DeviceInfo device, string adb, CancellationToken cancellationToken)
    {
        var propsTask = _runner.RunAsync(new ProcessRequest
        {
            FileName = adb,
            Arguments = ["-s", device.Serial!, "shell", "getprop"],
            Timeout = TimeSpan.FromSeconds(15),
            Description = "adb getprop"
        }, cancellationToken);

        var batteryTask = _runner.RunAsync(new ProcessRequest
        {
            FileName = adb,
            Arguments = ["-s", device.Serial!, "shell", "dumpsys", "battery"],
            Timeout = TimeSpan.FromSeconds(12),
            Description = "adb dumpsys battery"
        }, cancellationToken);

        var bootloaderTask = _runner.RunAsync(new ProcessRequest
        {
            FileName = adb,
            Arguments = ["-s", device.Serial!, "shell", "getprop", "ro.boot.verifiedbootstate"],
            Timeout = TimeSpan.FromSeconds(10),
            Description = "adb verifiedbootstate"
        }, cancellationToken);

        await Task.WhenAll(propsTask, batteryTask, bootloaderTask).ConfigureAwait(false);

        var props = ParseProps(propsTask.Result.StandardOutput);
        var battery = ParseBatteryLevel(batteryTask.Result.StandardOutput);
        var verifiedBoot = bootloaderTask.Result.StandardOutput.Trim();

        bool? unlocked = null;
        if (props.TryGetValue("ro.boot.flash.locked", out var locked))
        {
            unlocked = locked == "0";
        }

        var manufacturer = props.GetValueOrDefault("ro.product.manufacturer");
        var model = props.GetValueOrDefault("ro.product.model");
        var codename = props.GetValueOrDefault("ro.product.device");
        var buildId = props.GetValueOrDefault("ro.build.display.id") ?? props.GetValueOrDefault("ro.build.id");
        var android = props.GetValueOrDefault("ro.build.version.release");
        var region = props.GetValueOrDefault("ro.product.locale.region") ?? props.GetValueOrDefault("ro.csc.country_code");
        var platform = props.GetValueOrDefault("ro.board.platform") ?? props.GetValueOrDefault("ro.hardware");
        var slot = props.GetValueOrDefault("ro.boot.slot_suffix")?.TrimStart('_');
        var bootloaderVersion = props.GetValueOrDefault("ro.bootloader");

        var capabilities = new List<string>
        {
            "Системная информация",
            "Чтение свойств",
            "Перезагрузка в режимы",
            "Журналы logcat"
        };

        if (props.TryGetValue("ro.boot.flash.locked", out _))
        {
            capabilities.Add("Состояние загрузчика");
        }

        if (!string.IsNullOrWhiteSpace(slot))
        {
            capabilities.Add("Слоты A/B");
        }

        var warnings = new List<string>();
        if (string.IsNullOrWhiteSpace(model) || string.IsNullOrWhiteSpace(codename))
        {
            warnings.Add("Не удалось прочитать часть системных свойств (возможно, ограничение прошивки).");
        }

        if (!string.IsNullOrWhiteSpace(verifiedBoot) && !verifiedBoot.Equals("green", StringComparison.OrdinalIgnoreCase))
        {
            warnings.Add($"Состояние проверенной загрузки: {verifiedBoot}.");
        }

        if (!string.IsNullOrWhiteSpace(bootloaderVersion))
        {
            warnings.Add($"Версия загрузчика: {bootloaderVersion}.");
        }

        return new DeviceInfo
        {
            Id = device.Id,
            Transport = DeviceTransport.Adb,
            Mode = DeviceMode.Adb,
            Connection = ConnectionState.Connected,
            Serial = device.Serial,
            Manufacturer = manufacturer,
            Model = model,
            Codename = codename,
            AndroidVersion = android,
            BuildId = buildId,
            Region = region,
            Platform = platform,
            BatteryLevel = battery,
            BootloaderUnlocked = unlocked,
            AdbAuthorized = true,
            Slot = slot,
            BootloaderVersion = bootloaderVersion,
            Driver = DriverStatus.Ok,
            DriverName = "Android Composite ADB Interface",
            DetectedAt = DateTimeOffset.Now,
            Capabilities = capabilities,
            Warnings = warnings
        };
    }

    private static int? ParseBatteryLevel(string output)
    {
        var match = Regex.Match(output ?? string.Empty, @"level:\s*(\d{1,3})", RegexOptions.IgnoreCase);
        if (match.Success && int.TryParse(match.Groups[1].Value, out var level) && level is >= 0 and <= 100)
        {
            return level;
        }

        return null;
    }

    public static IReadOnlyDictionary<string, string> ParseProps(string output)
    {
        var props = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(output))
        {
            return props;
        }

        foreach (var line in output.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            // Формат: [ro.product.model]: [SM-G973F]
            var match = Regex.Match(line, @"^\s*\[(?<key>[^\]]+)\]:\s*\[(?<value>.*)\]\s*$", RegexOptions.CultureInvariant);
            if (match.Success)
            {
                props[match.Groups["key"].Value.Trim()] = match.Groups["value"].Value.Trim();
            }
        }

        return props;
    }

    /// <summary>Разбор вывода «adb devices -l». Возвращает только реально перечисленные строки.</summary>
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
            if (line.Length == 0 || line.StartsWith("List of devices", StringComparison.OrdinalIgnoreCase) || line.StartsWith('*'))
            {
                continue;
            }

            var parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2)
            {
                continue;
            }

            var serial = parts[0];
            var state = parts[1].ToLowerInvariant();
            var connection = state switch
            {
                "device" => ConnectionState.Connected,
                "unauthorized" => ConnectionState.Unauthorized,
                "offline" => ConnectionState.Offline,
                "no" when parts.Length > 2 && parts[2].StartsWith("permissions", StringComparison.OrdinalIgnoreCase) => ConnectionState.NoPermissions,
                "recovery" => ConnectionState.Connected,
                "sideload" => ConnectionState.Connected,
                _ => ConnectionState.Unknown
            };

            var mode = state switch
            {
                "recovery" => DeviceMode.Recovery,
                "sideload" => DeviceMode.Sideload,
                _ => DeviceMode.Adb
            };

            var model = ExtractToken(parts, "model:");
            var product = ExtractToken(parts, "product:");
            var deviceName = ExtractToken(parts, "device:");
            var transportId = ExtractToken(parts, "transport_id:");

            var warnings = new List<string>();
            if (connection == ConnectionState.Unauthorized)
            {
                warnings.Add("Устройство ожидает подтверждения отладки на экране смартфона.");
            }
            else if (connection == ConnectionState.NoPermissions)
            {
                warnings.Add("Нет прав доступа к USB-устройству (Linux: правила udev).");
            }
            else if (connection == ConnectionState.Offline)
            {
                warnings.Add("Устройство в состоянии offline — переподключите кабель.");
            }

            devices.Add(new DeviceInfo
            {
                Id = $"adb:{serial}",
                Transport = DeviceTransport.Adb,
                Mode = mode,
                Connection = connection,
                Serial = serial,
                Model = model?.Replace('_', ' '),
                Codename = deviceName ?? product,
                AdbAuthorized = connection == ConnectionState.Connected,
                Driver = connection == ConnectionState.Connected ? DriverStatus.Ok : DriverStatus.Unknown,
                Warnings = warnings,
                DetectedAt = DateTimeOffset.Now,
                UsbDevicePath = transportId is null ? null : $"transport_id={transportId}"
            });
        }

        return devices;
    }

    private static string? ExtractToken(string[] parts, string prefix)
    {
        foreach (var part in parts)
        {
            if (part.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                return part[prefix.Length..];
            }
        }

        return null;
    }
}
