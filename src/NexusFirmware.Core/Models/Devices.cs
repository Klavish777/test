namespace NexusFirmware.Core.Models;

/// <summary>Режим, в котором устройство видно хосту. Значение Unknown означает «не определено».</summary>
public enum DeviceMode
{
    Unknown = 0,
    Adb,
    Fastboot,
    Recovery,
    Sideload,
    Download,
    QualcommEdl,
    MediaTekBootrom,
    MediaTekPreloader,
    DiagnosticsPort,
    UsbGeneric
}

public enum DeviceTransport
{
    Unknown = 0,
    Adb,
    Fastboot,
    Usb
}

public enum DriverStatus
{
    Unknown = 0,
    Ok,
    Problem,
    Missing,
    Inaccessible
}

public enum ConnectionState
{
    Unknown = 0,
    Connected,
    Unauthorized,
    Offline,
    NoPermissions
}

/// <summary>
/// Снимок обнаруженного устройства. Все поля, кроме явно полученных от устройства,
/// остаются <c>null</c> — интерфейс обязан показывать их как «недоступно», а не как факт.
/// </summary>
public sealed class DeviceInfo
{
    public required string Id { get; init; }
    public DeviceTransport Transport { get; init; } = DeviceTransport.Unknown;
    public DeviceMode Mode { get; init; } = DeviceMode.Unknown;
    public ConnectionState Connection { get; init; } = ConnectionState.Unknown;

    public string? Serial { get; init; }
    public string? Manufacturer { get; init; }
    public string? Model { get; init; }
    public string? Codename { get; init; }
    public string? AndroidVersion { get; init; }
    public string? BuildId { get; init; }
    public string? Region { get; init; }
    public string? Platform { get; init; }
    public int? BatteryLevel { get; init; }
    public bool? BootloaderUnlocked { get; init; }
    public bool? AdbAuthorized { get; init; }
    public string? Slot { get; init; }
    public string? BootloaderVersion { get; init; }

    public string? VendorId { get; init; }
    public string? ProductId { get; init; }
    public string? UsbDevicePath { get; init; }
    public DriverStatus Driver { get; init; } = DriverStatus.Unknown;
    public string? DriverName { get; init; }

    public DateTimeOffset DetectedAt { get; init; } = DateTimeOffset.Now;
    public IReadOnlyList<string> Capabilities { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public string DisplayName
    {
        get
        {
            var name = string.Join(" ", new[] { Manufacturer, Model }.Where(s => !string.IsNullOrWhiteSpace(s)));
            if (!string.IsNullOrWhiteSpace(name))
            {
                return name;
            }

            return string.IsNullOrWhiteSpace(Serial) ? "Неизвестное устройство" : $"Неизвестное устройство ({Safety.Redactor.MaskIdentifier(Serial)})";
        }
    }

    public string ModeText => Mode switch
    {
        DeviceMode.Adb => "ADB",
        DeviceMode.Fastboot => "Fastboot",
        DeviceMode.Recovery => "Recovery",
        DeviceMode.Sideload => "Sideload",
        DeviceMode.Download => "Download (Odin)",
        DeviceMode.QualcommEdl => "Qualcomm EDL / 9008",
        DeviceMode.MediaTekBootrom => "MediaTek BootROM",
        DeviceMode.MediaTekPreloader => "MediaTek Preloader",
        DeviceMode.DiagnosticsPort => "Diagnostics",
        DeviceMode.UsbGeneric => "USB",
        _ => "Не определено"
    };

    public string MaskedSerial => Safety.Redactor.MaskIdentifier(Serial);

    public string ConnectionText => Connection switch
    {
        ConnectionState.Connected => "Подключено",
        ConnectionState.Unauthorized => "Ожидает подтверждения ADB",
        ConnectionState.Offline => "Нет связи",
        ConnectionState.NoPermissions => "Нет прав доступа",
        _ => "Неизвестно"
    };

    public string DriverText => Driver switch
    {
        DriverStatus.Ok => "Драйвер в порядке",
        DriverStatus.Problem => "Проблема с драйвером",
        DriverStatus.Missing => "Драйвер не найден",
        DriverStatus.Inaccessible => "Нет доступа к устройству",
        _ => "Не проверялся"
    };

    public DeviceInfo WithCapabilities(IEnumerable<string> capabilities) => new()
    {
        Id = Id,
        Transport = Transport,
        Mode = Mode,
        Connection = Connection,
        Serial = Serial,
        Manufacturer = Manufacturer,
        Model = Model,
        Codename = Codename,
        AndroidVersion = AndroidVersion,
        BuildId = BuildId,
        Region = Region,
        Platform = Platform,
        BatteryLevel = BatteryLevel,
        BootloaderUnlocked = BootloaderUnlocked,
        AdbAuthorized = AdbAuthorized,
        Slot = Slot,
        BootloaderVersion = BootloaderVersion,
        VendorId = VendorId,
        ProductId = ProductId,
        UsbDevicePath = UsbDevicePath,
        Driver = Driver,
        DriverName = DriverName,
        DetectedAt = DetectedAt,
        Capabilities = capabilities.ToArray(),
        Warnings = Warnings
    };
}

/// <summary>Сырые сведения о USB-узле, полученные от операционной системы.</summary>
public sealed class UsbDeviceDescriptor
{
    public required string DeviceInstanceId { get; init; }
    public string? Description { get; init; }
    public string? FriendlyName { get; init; }
    public string? Manufacturer { get; init; }
    public ushort? VendorId { get; init; }
    public ushort? ProductId { get; init; }
    public string? Service { get; init; }
    public ushort? Class { get; init; }
    public ushort? SubClass { get; init; }
    public ushort? Protocol { get; init; }
    public DriverStatus Driver { get; init; } = DriverStatus.Unknown;
    public int? ProblemCode { get; init; }
    public string? LocationInfo { get; init; }
}

public static class KnownUsbIdentifiers
{
    public const ushort QualcommVendorId = 0x05C6;
    public const ushort GoogleVendorId = 0x18D1;
    public const ushort SamsungVendorId = 0x04E8;
    public const ushort MediaTekVendorId = 0x0E8D;
    public const ushort MotorolaVendorId = 0x22B8;
    public const ushort XiaomiVendorId = 0x2717;
    public const ushort OnePlusVendorId = 0x2A70;
    public const ushort OppoVendorId = 0x22D9;
    public const ushort VivoVendorId = 0x2D95;
    public const ushort HuaweiVendorId = 0x12D1;
    public const ushort ZteVendorId = 0x19D2;
    public const ushort TranssionVendorId = 0x1782;
    public const ushort QualcommEdlProductId = 0x9008;
    public const ushort GoogleFastbootProductId = 0x4EE0;

    public static string? VendorName(ushort? vendorId) => vendorId switch
    {
        0x05C6 => "Qualcomm",
        0x18D1 => "Google",
        0x04E8 => "Samsung",
        0x0E8D => "MediaTek",
        0x22B8 => "Motorola",
        0x2717 => "Xiaomi",
        0x2A70 => "OnePlus",
        0x22D9 => "OPPO",
        0x2D95 => "Vivo",
        0x12D1 => "Huawei / Honor",
        0x19D2 => "ZTE / Nubia",
        0x1782 => "Transsion (Infinix / Tecno)",
        0x2A96 => "Realme",
        _ => null
    };
}
