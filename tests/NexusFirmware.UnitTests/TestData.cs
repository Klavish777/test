using System.IO.Compression;
using NexusFirmware.Core.Models;
using NUnit.Framework;

namespace NexusFirmware.UnitTests;

internal static class TestData
{
    public static FirmwarePackage Package(string? model = "G973F", string? manufacturer = "Samsung", IntegrityState integrity = IntegrityState.Verified, string? path = null)
    {
        return new FirmwarePackage
        {
            Id = Guid.NewGuid().ToString("N"),
            DisplayName = "AP_test.tar.md5",
            Manufacturer = manufacturer,
            Model = model,
            Region = "OXM",
            Version = "G973FXXU9FUB1",
            Format = FirmwareFormat.TarMd5,
            SizeBytes = 1024,
            Sha256 = new string('a', 64),
            Integrity = integrity,
            FilePath = path,
            ImportedAt = DateTimeOffset.Now,
            LastCheckedAt = DateTimeOffset.Now
        };
    }

    public static DeviceInfo Device(bool unlocked = true, DeviceMode mode = DeviceMode.Fastboot, ConnectionState connection = ConnectionState.Connected)
    {
        return new DeviceInfo
        {
            Id = "fastboot:TEST123",
            Transport = DeviceTransport.Fastboot,
            Mode = mode,
            Connection = connection,
            Serial = "TEST123",
            Manufacturer = "Samsung",
            Model = "SM-G973F",
            Codename = "beyond1",
            Region = "OXM",
            AndroidVersion = "12",
            BatteryLevel = 80,
            BootloaderUnlocked = unlocked,
            Capabilities = new[] { "Fastboot-переменные" }
        };
    }

    public static string CreateFirmwareZip(string directory, params string[] entries)
    {
        var path = Path.Combine(directory, "firmware.zip");
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        foreach (var entryName in entries)
        {
            var entry = zip.CreateEntry(entryName);
            using var writer = new StreamWriter(entry.Open());
            writer.Write("NEXUS test content for " + entryName);
        }

        return path;
    }
}

