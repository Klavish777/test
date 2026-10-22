using System.IO.Compression;
using System.Text;
using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Comparison;
using NexusFirmware.Firmware.Compatibility;
using NexusFirmware.Firmware.Extractor;
using NexusFirmware.Firmware.Library;
using NUnit.Framework;

namespace NexusFirmware.UnitTests;

[TestFixture]
public sealed class CompatibilityTests
{
    [Test]
    public void BlocksWhenDeviceMissing()
    {
        var result = FirmwareCompatibility.Check(null, TestData.Package());
        Assert.That(result.IsCompatible, Is.False);
        Assert.That(result.BlockingCount, Is.GreaterThanOrEqualTo(1));
    }

    [Test]
    public void BlocksLockedBootloader()
    {
        using var temp = new TempDirectory();
        var file = Path.Combine(temp.Path, "fw.zip");
        File.WriteAllText(file, "x");
        var package = TestData.Package(path: file);

        var result = FirmwareCompatibility.Check(TestData.Device(unlocked: false), package);

        Assert.That(result.IsCompatible, Is.False);
        Assert.That(result.Items.Any(i => i.Check == "Загрузчик" && i.Severity == CompatibilitySeverity.Blocking), Is.True);
    }

    [Test]
    public void BlocksModelMismatch()
    {
        using var temp = new TempDirectory();
        var file = Path.Combine(temp.Path, "fw.zip");
        File.WriteAllText(file, "x");
        var package = TestData.Package(model: "SM-A505F", path: file);

        var result = FirmwareCompatibility.Check(TestData.Device(), package);

        Assert.That(result.Items.Any(i => i.Check == "Модель" && i.Severity == CompatibilitySeverity.Blocking), Is.True);
    }

    [Test]
    public void WarnsWhenIntegrityNotVerified()
    {
        using var temp = new TempDirectory();
        var file = Path.Combine(temp.Path, "fw.zip");
        File.WriteAllText(file, "x");
        var package = TestData.Package(integrity: IntegrityState.NotVerified, path: file);

        var result = FirmwareCompatibility.Check(TestData.Device(), package);

        Assert.That(result.Items.Any(i => i.Check == "Целостность" && i.Severity == CompatibilitySeverity.Warning), Is.True);
    }

    [Test]
    public void BlocksAntiRollbackDowngrade()
    {
        using var temp = new TempDirectory();
        var file = Path.Combine(temp.Path, "fw.zip");
        File.WriteAllText(file, "x");

        var result = FirmwareCompatibility.Check(TestData.Device(), TestData.Package(path: file), "9", "5");

        Assert.That(result.Items.Any(i => i.Check == "Anti-rollback" && i.Severity == CompatibilitySeverity.Blocking), Is.True);
    }
}

[TestFixture]
public sealed class FirmwareComparerTests
{
    private static void FillZip(string path, params (string Name, string Content)[] entries)
    {
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        foreach (var (name, content) in entries)
        {
            using var writer = new StreamWriter(zip.CreateEntry(name).Open());
            writer.Write(content);
        }
    }

    [Test]
    public void ComparesMetadataAndArchiveContents()
    {
        using var temp = new TempDirectory();
        var left = Path.Combine(temp.Path, "left.zip");
        FillZip(left, ("boot.img", "boot"), ("system.img", "system"));

        var right = Path.Combine(temp.Path, "right.zip");
        FillZip(right, ("boot.img", "boot"), ("vendor.img", "vendor"));

        var leftPackage = new FirmwarePackage
        {
            Id = "left",
            DisplayName = "zip",
            Format = FirmwareFormat.Zip,
            FilePath = left,
            Sha256 = new string('1', 64),
            Version = "1.0"
        };

        var rightPackage = new FirmwarePackage
        {
            Id = "right",
            DisplayName = "zip",
            Format = FirmwareFormat.Zip,
            FilePath = right,
            Sha256 = new string('2', 64),
            Version = "2.0"
        };

        var comparison = FirmwareComparer.Compare(leftPackage, rightPackage);

        Assert.That(comparison.Rows.Any(r => r.Property == "SHA-256" && r.Differs), Is.True);
        Assert.That(comparison.OnlyInLeft, Does.Contain("system.img"));
        Assert.That(comparison.Notes.Any(n => n.Contains("Версии различаются")), Is.True);
    }
}

[TestFixture]
public sealed class AnalyzerTests
{
    [Test]
    public async Task InspectsZipAndListsEntries()
    {
        using var temp = new TempDirectory();
        var path = TestData.CreateFirmwareZip(temp.Path, "boot.img", "system.img");
        var analyzer = new FirmwareAnalyzer();

        var analysis = analyzer.Inspect(path, computeHash: true);

        Assert.That(analysis.Format, Is.EqualTo(FirmwareFormat.Zip));
        Assert.That(analysis.Sha256, Is.Not.Null.And.Length.EqualTo(64));
        Assert.That(analysis.Sections.Any(s => s.Title == "Содержимое" && s.Rows.Count == 2), Is.True);

        var json = FirmwareAnalyzer.ToJson(analysis);
        var csv = FirmwareAnalyzer.ToCsv(analysis);
        Assert.That(json, Does.Contain("boot.img"));
        Assert.That(csv, Does.Contain("section;key;value"));

        await Task.CompletedTask;
    }

    [Test]
    public void InspectsTotallyUnknownFile()
    {
        using var temp = new TempDirectory();
        var path = Path.Combine(temp.Path, "unknown.bin");
        File.WriteAllBytes(path, new byte[] { 0x00, 0xFF, 0x01, 0x02, 0x03 });

        var analysis = new FirmwareAnalyzer().Inspect(path);

        Assert.That(analysis.Format, Is.EqualTo(FirmwareFormat.Unknown));
        Assert.That(analysis.Limitations, Is.Not.Empty);
    }

    [Test]
    public async Task ExtractsZipToDestination()
    {
        using var temp = new TempDirectory();
        var path = TestData.CreateFirmwareZip(temp.Path, "boot.img");
        var destination = Path.Combine(temp.Path, "out");
        var service = new FirmwareExtractorService(new FakeLogBus());

        var files = await service.ExtractAsync(path, destination);

        Assert.That(files, Has.Count.EqualTo(1));
        Assert.That(File.Exists(Path.Combine(destination, "boot.img")), Is.True);
    }

    [Test]
    public async Task ExtractsGzip()
    {
        using var temp = new TempDirectory();
        var path = Path.Combine(temp.Path, "payload.gz");
        await using (var file = File.Create(path))
        await using (var gzip = new GZipStream(file, CompressionMode.Compress))
        {
            await gzip.WriteAsync(Encoding.UTF8.GetBytes("compressed-data"));
        }

        var destination = Path.Combine(temp.Path, "out");
        var service = new FirmwareExtractorService(new FakeLogBus());
        var files = await service.ExtractAsync(path, destination);

        Assert.That(File.ReadAllText(files[0]), Is.EqualTo("compressed-data"));
    }

    [Test]
    public void FreeSpaceIsReported()
    {
        var (free, root) = FirmwareLibrary.GetFreeSpace(Path.GetTempPath());
        Assert.That(free, Is.GreaterThanOrEqualTo(0));
        Assert.That(root, Is.Not.Empty);
    }
}
