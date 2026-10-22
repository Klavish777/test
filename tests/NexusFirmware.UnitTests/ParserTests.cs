using System.Buffers.Binary;
using System.Text;
using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Ota;
using NexusFirmware.Firmware.Qualcomm;
using NexusFirmware.Firmware.Samsung;
using NexusFirmware.Firmware.Scatter;

namespace NexusFirmware.UnitTests;

[TestFixture]
public sealed class PayloadParserTests
{
    private static byte[] Varint(ulong value)
    {
        var list = new List<byte>();
        do
        {
            var b = (byte)(value & 0x7F);
            value >>= 7;
            if (value != 0)
            {
                b |= 0x80;
            }

            list.Add(b);
        }
        while (value != 0);

        return list.ToArray();
    }

    private static byte[] Field(int number, int wireType) => Varint((ulong)((number << 3) | wireType));

    private static byte[] Partition(string name, ulong size, int operations)
    {
        var bytes = new List<byte>();
        var nameBytes = Encoding.UTF8.GetBytes(name);
        bytes.AddRange(Field(1, 2));
        bytes.AddRange(Varint((ulong)nameBytes.Length));
        bytes.AddRange(nameBytes);

        var info = new List<byte>();
        info.AddRange(Field(1, 0));
        info.AddRange(Varint(size));
        bytes.AddRange(Field(7, 2));
        bytes.AddRange(Varint((ulong)info.Count));
        bytes.AddRange(info);

        for (var i = 0; i < operations; i++)
        {
            bytes.AddRange(Field(8, 2));
            bytes.AddRange(Varint(0));
        }

        return bytes.ToArray();
    }

    private static byte[] BuildPayload(params byte[][] partitions)
    {
        var manifest = new List<byte>();
        manifest.AddRange(Field(12, 0));
        manifest.AddRange(Varint(0));
        foreach (var partition in partitions)
        {
            manifest.AddRange(Field(13, 2));
            manifest.AddRange(Varint((ulong)partition.Length));
            manifest.AddRange(partition);
        }

        var header = new List<byte>();
        // версия = 2
        var version = new byte[8];
        BinaryPrimitives.WriteUInt64BigEndian(version, 2);
        header.AddRange("CrAU"u8.ToArray());
        header.AddRange(version);
        var sizeBytes = new byte[8];
        BinaryPrimitives.WriteUInt64BigEndian(sizeBytes, (ulong)manifest.Count);
        header.AddRange(sizeBytes);
        var signatureSize = new byte[4];
        BinaryPrimitives.WriteUInt32BigEndian(signatureSize, 0);
        header.AddRange(signatureSize);
        header.AddRange(manifest);
        return header.ToArray();
    }

    [Test]
    public void ReadsManifestPartitions()
    {
        using var temp = new TempDirectory();
        var path = temp.File("payload.bin");
        File.WriteAllBytes(path, BuildPayload(
            Partition("boot", 123456, 2),
            Partition("system", 987654321, 1)));

        var payload = PayloadParser.Read(path);

        Assert.That(payload.Version, Is.EqualTo(2UL));
        Assert.That(payload.Partitions, Has.Count.EqualTo(2));
        Assert.That(payload.Partitions[0].Name, Is.EqualTo("boot"));
        Assert.That(payload.Partitions[0].SizeBytes, Is.EqualTo(123456));
        Assert.That(payload.Partitions[0].OperationCount, Is.EqualTo(2));
        Assert.That(payload.Partitions[1].Name, Is.EqualTo("system"));
    }

    [Test]
    public void RejectsInvalidMagic()
    {
        using var temp = new TempDirectory();
        var path = temp.File("payload.bin");
        File.WriteAllBytes(path, new byte[64]);

        Assert.That(PayloadParser.LooksLikePayload(path), Is.False);
        Assert.Throws<InvalidDataException>(() => PayloadParser.Read(path));
    }
}

[TestFixture]
public sealed class ScatterParserTests
{
    private const string Sample = """
        - general: MTK_PLATFORM_CFG
          info: MTK_PLATFORM: MT6765 | Project: k62v1_64_bsp
          platform: MT6765
          project: k62v1_64_bsp
          storage: HW_STORAGE_EMMC
        - partition_index: SYS0
          partition_name: preloader
          file_name: preloader_k62v1_64_bsp.bin
          is_download: true
          type: SV5_BL_BIN
          linear_start_addr: 0x0
          partition_size: 0x40000
          region: EMMC_BOOT_1
          operation_type: BOOTLOADERS
        - partition_index: SYS1
          partition_name: boot
          file_name: boot.img
          is_download: true
          type: EXT4_IMG
          linear_start_addr: 0x400000
          partition_size: 0x2000000
          region: EMMC_USER
          operation_type: UPDATE
        """;

    [Test]
    public void ParsesPlatformAndPartitions()
    {
        var scatter = ScatterParser.ParseText(Sample);

        Assert.That(scatter.Platform, Is.EqualTo("MT6765"));
        Assert.That(scatter.Project, Is.EqualTo("k62v1_64_bsp"));
        Assert.That(scatter.Partitions, Has.Count.EqualTo(2));
        Assert.That(scatter.Partitions[0].PartitionName, Is.EqualTo("preloader"));
        Assert.That(scatter.Partitions[0].PartitionSize, Is.EqualTo(0x40000));
        Assert.That(scatter.Partitions[0].IsDownload, Is.True);
        Assert.That(scatter.Partitions[1].PartitionName, Is.EqualTo("boot"));
        Assert.That(scatter.TotalDeclaredBytes, Is.EqualTo(0x40000 + 0x2000000));
    }

    [Test]
    public void VerifiesFilesInDirectory()
    {
        using var temp = new TempDirectory();
        File.WriteAllBytes(temp.File("boot.img"), new byte[1024]);

        var scatter = ScatterParser.ParseText(Sample);
        var checks = ScatterParser.VerifyFiles(scatter, temp.Path);

        Assert.That(checks.Single(c => c.FileName == "boot.img").FileExists, Is.True);
        Assert.That(checks.Single(c => c.FileName == "preloader_k62v1_64_bsp.bin").FileExists, Is.False);
    }

    [Test]
    public void WarnsWhenPlatformMissing()
    {
        var scatter = ScatterParser.ParseText("- partition_index: SYS0\n  partition_name: boot\n  file_name: boot.img");
        Assert.That(scatter.Warnings.Any(w => w.Contains("платформа")), Is.True);
    }
}

[TestFixture]
public sealed class RawProgramParserTests
{
    [Test]
    public void ParsesPrograms()
    {
        using var temp = new TempDirectory();
        var path = temp.File("rawprogram0.xml");
        File.WriteAllText(path, """
            <?xml version="1.0" ?>
            <data>
              <program SECTOR_SIZE_IN_BYTES="4096" file_sector_offset="0" filename="gpt_main0.bin"
                       label="PrimaryGPT" num_partition_sectors="6" physical_partition_number="0"
                       size_in_KB="24.0" sparse="false" start_byte_hex="0x0" start_sector="0" />
              <program SECTOR_SIZE_IN_BYTES="4096" file_sector_offset="0" filename="boot.img"
                       label="boot" num_partition_sectors="65536" physical_partition_number="0"
                       size_in_KB="262144.0" sparse="true" start_byte_hex="0x1800000" start_sector="6144" />
              <patch SECTOR_SIZE_IN_BYTES="4096" byte_offset="0" filename="DISK" partition="0" />
            </data>
            """);

        var document = RawProgramParser.Parse(path);

        Assert.That(document.Programs, Has.Count.EqualTo(2));
        Assert.That(document.Programs[0].Label, Is.EqualTo("PrimaryGPT"));
        Assert.That(document.Programs[1].FileName, Is.EqualTo("boot.img"));
        Assert.That(document.Programs[1].Sparse, Is.True);
        Assert.That(document.Patches, Has.Count.EqualTo(1));
    }
}

[TestFixture]
public sealed class SamsungAnalyzerTests
{
    [Test]
    public void ParsesComponentMetadata()
    {
        using var temp = new TempDirectory();
        var path = temp.File("AP_G973FXXU9FUB1_CL12345678_QB12345678_SIGNED.tar.md5");
        File.WriteAllText(path, "placeholder");

        var info = SamsungPackageAnalyzer.AnalyzeFile(path);

        Assert.That(info.Component, Is.EqualTo("AP"));
        Assert.That(info.ModelCode, Is.EqualTo("G973F"));
        Assert.That(info.PdaVersion, Is.EqualTo("G973FXXU9FUB1"));
        Assert.That(info.BuildNumber, Is.EqualTo("12345678"));
        Assert.That(info.BootloaderBinary, Is.EqualTo("9"));
    }

    [Test]
    public void DetectsHomeCsc()
    {
        using var temp = new TempDirectory();
        var path = temp.File("HOME_CSC_OXM_G973FOXM9FUB1_CL12345678_QB12345678_SIGNED.tar.md5");
        File.WriteAllText(path, "placeholder");

        var info = SamsungPackageAnalyzer.AnalyzeFile(path);
        Assert.That(info.Component, Is.EqualTo("HOME_CSC"));
        Assert.That(info.CscVersion, Is.EqualTo("OXM"));
    }

    [Test]
    public void BlocksMixedModels()
    {
        using var temp = new TempDirectory();
        var ap = temp.File("AP_G973FXXU9FUB1_CL1_QB1_SIGNED.tar.md5");
        var bl = temp.File("BL_N986BXXU1AUB1_CL1_QB1_SIGNED.tar.md5");
        File.WriteAllText(ap, "x");
        File.WriteAllText(bl, "y");

        var analysis = SamsungPackageAnalyzer.AnalyzePackage(new[]
        {
            SamsungPackageAnalyzer.AnalyzeFile(ap),
            SamsungPackageAnalyzer.AnalyzeFile(bl)
        });

        Assert.That(analysis.HasBlockingIssues, Is.True);
        Assert.That(analysis.Checks.Any(c => c.Check == "Модель" && c.Severity == CompatibilitySeverity.Blocking), Is.True);
    }

    [TestCase("G973FXXU9FUB1", "9")]
    [TestCase("SM-N986BXXU2AUB1", "2")]
    [TestCase("bad", null)]
    public void ExtractsBinaryRevision(string version, string? expected)
    {
        Assert.That(SamsungPackageAnalyzer.ExtractBinaryRevision(version), Is.EqualTo(expected));
    }
}
