using System.Text.Json;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection.Usb;

namespace NexusFirmware.Drivers;

public sealed record DriverSource(string Vendor, string Purpose, string Url, string Note);

public sealed class DriverInventoryItem
{
    public required string DeviceName { get; init; }
    public required string InstanceId { get; init; }
    public string? Manufacturer { get; init; }
    public string? Service { get; init; }
    public DriverStatus Status { get; init; }
    public int? ProblemCode { get; init; }
    public string? VendorHint { get; init; }
    public string Guidance { get; init; } = "";
}

public sealed record SignatureCheckResult(
    bool IsSigned,
    bool IsValid,
    string Status,
    string? SignerSubject,
    string? Thumbprint,
    string? Timestamp,
    string Message);

/// <summary>
/// Центр драйверов: инвентаризация проблемных USB-устройств, ссылки на официальные источники,
/// проверка цифровой подписи установочных пакетов. Проверка подписи драйверов НЕ отключается.
/// </summary>
public sealed class DriverCenterService
{
    private readonly WindowsUsbEnumerator _usb;
    private readonly IToolLocator _locator;
    private readonly IProcessRunner _runner;
    private readonly ILogBus _log;

    public DriverCenterService(WindowsUsbEnumerator usb, IToolLocator locator, IProcessRunner runner, ILogBus log)
    {
        _usb = usb;
        _locator = locator;
        _runner = runner;
        _log = log;
    }

    public IReadOnlyList<DriverSource> OfficialSources { get; } = new[]
    {
        new DriverSource("Google", "Android USB Driver / Platform Tools", "https://developer.android.com/studio/run/win-usb", "Официальный драйвер для Pixel и универсальный WinUSB."),
        new DriverSource("Samsung", "Samsung USB Driver / Smart Switch", "https://www.samsung.com/us/support/downloads/", "Драйвер для режимов MTP, ADB и Download."),
        new DriverSource("MediaTek", "MediaTek USB VCOM drivers", "https://www.mediatek.com/", "Официальные драйверы публикуются производителем устройства."),
        new DriverSource("Qualcomm", "Qualcomm USB Driver (QDLoader 9008)", "https://www.qualcomm.com/", "Драйвер HS-USB QDLoader требуется для режима EDL."),
        new DriverSource("Xiaomi", "Xiaomi USB Driver", "https://www.mi.com/global/support/", "Также доступен через Mi Flash Tool от Xiaomi."),
        new DriverSource("Motorola", "Motorola Device Manager", "https://support.motorola.com/", "Официальный пакет драйверов Motorola."),
        new DriverSource("OnePlus", "OnePlus USB Drivers", "https://www.oneplus.com/support", "Драйверы публикуются в разделе поддержки."),
        new DriverSource("Huawei / Honor", "HiSuite", "https://consumer.huawei.com/en/support/", "HiSuite содержит драйверы для устройств Huawei/Honor.")
    };

    public async Task<IReadOnlyList<DriverInventoryItem>> GetInventoryAsync(CancellationToken cancellationToken = default)
    {
        if (!_usb.IsSupported)
        {
            return Array.Empty<DriverInventoryItem>();
        }

        var devices = await _usb.EnumerateAsync(cancellationToken).ConfigureAwait(false);
        var items = new List<DriverInventoryItem>();

        foreach (var device in devices)
        {
            var vendor = KnownUsbIdentifiers.VendorName(device.VendorId);
            if (vendor is null)
            {
                continue;
            }

            var status = device.Driver;
            var guidance = status switch
            {
                DriverStatus.Problem => "Устройство сообщает об ошибке драйвера. Откройте Диспетчер устройств, удалите проблемное устройство и переустановите официальный драйвер.",
                DriverStatus.Ok => "Драйвер загружен без ошибок.",
                _ => "Состояние драйвера не определено."
            };

            items.Add(new DriverInventoryItem
            {
                DeviceName = device.Description ?? "USB-устройство",
                InstanceId = device.DeviceInstanceId,
                Manufacturer = device.Manufacturer,
                Service = device.Service,
                Status = status,
                ProblemCode = device.ProblemCode,
                VendorHint = vendor,
                Guidance = guidance
            });
        }

        return items;
    }

    public async Task<IReadOnlyList<string>> CheckToolchainAsync(CancellationToken cancellationToken = default)
    {
        var messages = new List<string>();
        var adb = _locator.Find("adb");
        var fastboot = _locator.Find("fastboot");

        messages.Add(adb is null ? "ADB не найден: установите Android Platform Tools." : $"ADB: {adb}");
        messages.Add(fastboot is null ? "Fastboot не найден: установите Android Platform Tools." : $"Fastboot: {fastboot}");

        if (adb is not null)
        {
            var result = await _runner.RunAsync(new ProcessRequest
            {
                FileName = adb,
                Arguments = ["version"],
                Timeout = TimeSpan.FromSeconds(8),
                Description = "adb version"
            }, cancellationToken).ConfigureAwait(false);

            messages.Add(result.Started
                ? "ADB запускается: " + result.StandardOutput.Split('\n').FirstOrDefault()?.Trim()
                : "ADB не запускается: " + result.StartError);
        }

        return messages;
    }

    /// <summary>Проверка цифровой подписи установочного пакета через Authenticode (PowerShell).</summary>
    public async Task<SignatureCheckResult> VerifyInstallerSignatureAsync(string filePath, CancellationToken cancellationToken = default)
    {
        if (!File.Exists(filePath))
        {
            return new SignatureCheckResult(false, false, "FileNotFound", null, null, null, "Файл не найден.");
        }

        if (!OperatingSystem.IsWindows())
        {
            return new SignatureCheckResult(false, false, "Unsupported", null, null, null,
                "Проверка Authenticode доступна только в Windows.");
        }

        var escaped = filePath.Replace("'", "''");
        var script = $"""
            $ErrorActionPreference = 'Stop';
            $sig = Get-AuthenticodeSignature -FilePath '{escaped}';
            [pscustomobject]@{{
              Status = [string]$sig.Status;
              StatusMessage = [string]$sig.StatusMessage;
              SignerSubject = if ($sig.SignerCertificate) {{ [string]$sig.SignerCertificate.Subject }} else {{ $null }};
              Thumbprint = if ($sig.SignerCertificate) {{ [string]$sig.SignerCertificate.Thumbprint }} else {{ $null }};
              Timestamp = if ($sig.TimeStamperCertificate) {{ [string]$sig.TimeStamperCertificate.Subject }} else {{ $null }}
            }} | ConvertTo-Json -Compress
            """;

        var powershell = Path.Combine(Environment.SystemDirectory, "WindowsPowerShell", "v1.0", "powershell.exe");
        var result = await _runner.RunAsync(new ProcessRequest
        {
            FileName = File.Exists(powershell) ? powershell : "powershell.exe",
            Arguments = ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            Timeout = TimeSpan.FromSeconds(45),
            RedactOutput = false,
            Description = "Authenticode signature check"
        }, cancellationToken).ConfigureAwait(false);

        if (!result.Started || result.TimedOut)
        {
            return new SignatureCheckResult(false, false, "Error", null, null, null,
                "Не удалось проверить подпись: " + (result.StartError ?? "тайм-аут"));
        }

        try
        {
            using var document = JsonDocument.Parse(result.StandardOutput);
            var root = document.RootElement;
            var status = root.TryGetProperty("Status", out var s) ? s.GetString() ?? "Unknown" : "Unknown";
            var valid = status.Equals("Valid", StringComparison.OrdinalIgnoreCase);
            var signer = root.TryGetProperty("SignerSubject", out var signerElement) && signerElement.ValueKind == JsonValueKind.String
                ? signerElement.GetString()
                : null;
            var thumbprint = root.TryGetProperty("Thumbprint", out var tp) && tp.ValueKind == JsonValueKind.String ? tp.GetString() : null;
            var timestamp = root.TryGetProperty("Timestamp", out var ts) && ts.ValueKind == JsonValueKind.String ? ts.GetString() : null;

            var message = valid
                ? "Подпись действительна." + (signer is null ? "" : $" Издатель: {signer}")
                : $"Подпись не подтверждена (статус {status}). Установка такого пакета не рекомендуется.";

            _log.Write(valid ? LogLevel.Information : LogLevel.Warning, "Drivers", message);
            return new SignatureCheckResult(!string.IsNullOrWhiteSpace(signer), valid, status, signer, thumbprint, timestamp, message);
        }
        catch (JsonException ex)
        {
            return new SignatureCheckResult(false, false, "ParseError", null, null, null,
                "Ответ PowerShell не разобран: " + ex.Message);
        }
    }

    /// <summary>Шаги безопасной переустановки драйвера. Приложение не меняет политику подписи.</summary>
    public IReadOnlyList<string> GetReinstallGuidance() => new[]
    {
        "Запустите Диспетчер устройств (devmgmt.msc) от имени администратора.",
        "Найдите проблемное устройство (жёлтый значок) в разделе «Портативные устройства» или «Другие устройства».",
        "Откройте свойства → «Драйвер» → «Удалить устройство», отметьте «Попытка удаления драйвера».",
        "Отключите и подключите кабель USB (желательно USB 2.0 порт на задней панели).",
        "Установите официальный драйвер производителя и перезагрузите компьютер.",
        "Не отключайте проверку подписи драйверов: это снижает безопасность системы."
    };
}
