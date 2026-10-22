using System.Diagnostics;
using System.Text;
using System.Text.Json;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;

namespace NexusFirmware.DeviceDetection.Usb;

/// <summary>
/// Перечисление USB-устройств через WMI/CIM (PowerShell Get-CimInstance).
/// Работает только в Windows; на других ОС возвращает пустой список с пояснением.
/// Данные не выдумываются: если PowerShell недоступен — список остаётся пустым.
/// </summary>
public sealed class WindowsUsbEnumerator
{
    private readonly IProcessRunner _runner;
    private readonly ILogBus _log;

    public WindowsUsbEnumerator(IProcessRunner runner, ILogBus log)
    {
        _runner = runner;
        _log = log;
    }

    public bool IsSupported => OperatingSystem.IsWindows();

    private const string Query = """
        $ErrorActionPreference = 'Stop';
        Get-CimInstance Win32_PnPEntity |
          Where-Object { $_.DeviceID -like 'USB\VID_*' } |
          Select-Object DeviceID, Name, Manufacturer, Service, Status, ConfigManagerErrorCode, PNPClass |
          ConvertTo-Json -Compress -Depth 3
        """;

    public async Task<IReadOnlyList<UsbDeviceDescriptor>> EnumerateAsync(CancellationToken cancellationToken = default)
    {
        if (!OperatingSystem.IsWindows())
        {
            return Array.Empty<UsbDeviceDescriptor>();
        }

        var powershell = Path.Combine(Environment.SystemDirectory, "WindowsPowerShell", "v1.0", "powershell.exe");
        if (!File.Exists(powershell))
        {
            powershell = "powershell.exe";
        }

        var result = await _runner.RunAsync(new ProcessRequest
        {
            FileName = powershell,
            Arguments = ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", Query],
            Timeout = TimeSpan.FromSeconds(30),
            RedactOutput = false,
            Description = "USB enumeration (WMI)"
        }, cancellationToken).ConfigureAwait(false);

        if (!result.Started || result.TimedOut)
        {
            _log.Warn("USB", "Не удалось перечислить USB-устройства через WMI.");
            return Array.Empty<UsbDeviceDescriptor>();
        }

        return ParseJson(result.StandardOutput);
    }

    /// <summary>Разбор JSON от ConvertTo-Json (объект или массив).</summary>
    public static IReadOnlyList<UsbDeviceDescriptor> ParseJson(string json)
    {
        var list = new List<UsbDeviceDescriptor>();
        if (string.IsNullOrWhiteSpace(json))
        {
            return list;
        }

        JsonDocument document;
        try
        {
            document = JsonDocument.Parse(json);
        }
        catch (JsonException)
        {
            return list;
        }

        using (document)
        {
            var elements = document.RootElement.ValueKind == JsonValueKind.Array
                ? document.RootElement.EnumerateArray()
                : new[] { document.RootElement }.AsEnumerable();

            foreach (var element in elements)
            {
                if (element.ValueKind != JsonValueKind.Object)
                {
                    continue;
                }

                var deviceId = GetString(element, "DeviceID");
                if (string.IsNullOrWhiteSpace(deviceId))
                {
                    continue;
                }

                var (vid, pid) = ParseVidPid(deviceId);
                var errorCode = GetInt(element, "ConfigManagerErrorCode");
                var status = GetString(element, "Status");

                list.Add(new UsbDeviceDescriptor
                {
                    DeviceInstanceId = deviceId,
                    Description = GetString(element, "Name"),
                    FriendlyName = GetString(element, "Name"),
                    Manufacturer = GetString(element, "Manufacturer"),
                    VendorId = vid,
                    ProductId = pid,
                    Service = GetString(element, "Service"),
                    Driver = errorCode is null or 0
                        ? (string.Equals(status, "OK", StringComparison.OrdinalIgnoreCase) ? DriverStatus.Ok : DriverStatus.Unknown)
                        : DriverStatus.Problem,
                    ProblemCode = errorCode is 0 ? null : errorCode
                });
            }
        }

        return list;
    }

    private static (ushort? Vid, ushort? Pid) ParseVidPid(string deviceId)
    {
        ushort? vid = null;
        ushort? pid = null;

        var vidIndex = deviceId.IndexOf("VID_", StringComparison.OrdinalIgnoreCase);
        if (vidIndex >= 0 && deviceId.Length >= vidIndex + 8)
        {
            if (ushort.TryParse(deviceId.AsSpan(vidIndex + 4, 4), System.Globalization.NumberStyles.HexNumber, null, out var parsedVid))
            {
                vid = parsedVid;
            }
        }

        var pidIndex = deviceId.IndexOf("PID_", StringComparison.OrdinalIgnoreCase);
        if (pidIndex >= 0 && deviceId.Length >= pidIndex + 8)
        {
            if (ushort.TryParse(deviceId.AsSpan(pidIndex + 4, 4), System.Globalization.NumberStyles.HexNumber, null, out var parsedPid))
            {
                pid = parsedPid;
            }
        }

        return (vid, pid);
    }

    private static string? GetString(JsonElement element, string property)
    {
        if (!element.TryGetProperty(property, out var value))
        {
            return null;
        }

        return value.ValueKind switch
        {
            JsonValueKind.String => string.IsNullOrWhiteSpace(value.GetString()) ? null : value.GetString(),
            JsonValueKind.Number => value.ToString(),
            _ => null
        };
    }

    private static int? GetInt(JsonElement element, string property)
    {
        if (!element.TryGetProperty(property, out var value))
        {
            return null;
        }

        return value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var number) ? number : null;
    }

    /// <summary>Формирование сведений об устройстве по USB-дескриптору (без выдуманных данных).</summary>
    public static DeviceInfo ToDeviceInfo(UsbDeviceDescriptor descriptor)
    {
        var mode = ClassifyDevice(descriptor);
        var warnings = new List<string>();

        if (descriptor.Driver == DriverStatus.Problem)
        {
            warnings.Add($"Драйвер устройства не работает (код {descriptor.ProblemCode?.ToString() ?? "неизвестен"}). " +
                         "Установите официальный драйвер производителя.");
        }

        if (mode == DeviceMode.QualcommEdl)
        {
            warnings.Add("Устройство в режиме Qualcomm EDL (9008): запись возможна только официальным инструментом.");
        }
        else if (mode == DeviceMode.MediaTekBootrom)
        {
            warnings.Add("Устройство в режиме MediaTek BROM/Preloader: работа с BROM не реализована.");
        }
        else if (mode == DeviceMode.Download)
        {
            warnings.Add("Устройство в режиме Samsung Download: используется официальный инструмент производителя.");
        }

        return new DeviceInfo
        {
            Id = "usb:" + descriptor.InstanceId,
            Transport = DeviceTransport.Usb,
            Mode = mode,
            Connection = descriptor.Driver == DriverStatus.Problem ? ConnectionState.Unknown : ConnectionState.Connected,
            Serial = null,
            Manufacturer = descriptor.Manufacturer,
            Model = descriptor.Name,
            VendorId = $"{(descriptor.VendorId ?? 0):X4}",
            ProductId = $"{(descriptor.ProductId ?? 0):X4}",
            Driver = descriptor.Driver,
            ProblemCode = descriptor.ProblemCode,
            Warnings = warnings
        };
    }
