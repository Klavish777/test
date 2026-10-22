using System.Buffers.Binary;
using System.Formats.Tar;
using System.IO.Compression;
using System.Text;
using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Detection;
using NexusFirmware.Firmware.Images;
using NUnit.Framework;

namespace NexusFirmware.UnitTests;

[TestFixture]
public sealed class FormatDetectorTests
{
    [Test]
    public void DetectsZipBySignature()
    {
        using var temp = new TempDirectory();
        var path = temp.File("archive.bin"); // расширение не совпадает с содержимым
        using (var zip = ZipFile.Open(path, ZipArchiveMode.Create))
        {
            var entry = zip.CreateEntry("file.txt");
            using var writer = new StreamWriter(entry.Open());
            writer.Write("hello");
        }

        Assert.That(FormatDetector.Detect(path), Is.EqualTo(FirmwareFormat.Zip));
    }

    [Test]
    public void DetectsSparseImage()
    {
        using var temp = new TempDirectory();
        var path = temp.File("system.img");
        var bytes = new byte[64];
        BinaryPrimitives.WriteUInt32LittleEndian(bytes, SparseImageParser.Magic);
        File.WriteAllBytes(path, bytes);

        Assert.That(FormatDetector.Detect(path), Is.EqualTo(FirmwareFormat.SparseImage));
    }

    [Test]
    public void DetectsPayload()
    {
        using var temp = new TempDirectory();
        var path = temp.File("payload.bin");
        var payload = new byte[24];
        "CrAU"u8.CopyTo(payload);
        System.Buffers.Binary.BinaryPrimitives.WriteUInt64BigEndian(payload.AsSpan(8), 2);
        System.Buffers.Binary.BinaryPrimitives.WriteUInt64BigEndian(payload.AsSpan(16), 0);
        File.WriteAllBytes(path, payload);

        Assert.That(FormatDetector.Detect(path), Is.EqualTo(FirmwareFormat.PayloadBin));
    }

    [Test]
    public void DetectsTarByMagic()
    {
        using var temp = new TempDirectory();
        var path = temp.File("package.tar");
        using (var stream = File.Create(path))
        using (var writer = new TarWriter(stream, TarEntryFormat.Ustar))
        {
            var entry = new UstarTarEntry(TarEntryType.RegularFile, "boot.img")
            {
                DataStream = new MemoryStream(Encoding.ASCII.GetBytes("kernel"))
            };
            writer.WriteEntry(entry);
        }

        Assert.That(FormatDetector.Detect(path), Is.EqualTo(FirmwareFormat.Tar));
    }

    [Test]
    public void DetectsSamsungComponentByExtension()
    {
        using var temp = new TempDirectory();
        var path = temp.File("HOME_CSC_G973FOXM9FUB1.txt");
        File.WriteAllText(path, "not a real archive");

        var format = FormatDetector.SamsungFormatFromName(path);
        Assert.That(format, Is.EqualTo(FirmwareFormat.SamsungHomeCsc));
    }
}

[TestFixture]
public sealed class ZipInspectorTests
{
    [Test]
    public void DetectsTraversalEntries()
    {
        using var temp = new TempDirectory();
        var path = temp.File("evil.zip");
        using (var zip = ZipFile.Open(path, ZipArchiveMode.Create))
        {
            using (var writer = new StreamWriter(zip.CreateEntry("../escape.txt").Open()))
            {
                writer.Write("bad");
            }

            using (var writer = new StreamWriter(zip.CreateEntry("good.txt").Open()))
            {
                writer.Write("ok");
            }
        }

        var inspection = ZipInspector.Inspect(path);
        Assert.That(inspection.SafeToExtract, Is.False);
        Assert.That(inspection.BlockingIssues.Any(i => i.Contains("path traversal") || i.Contains("Обход каталога")), Is.True);
    }

    [Test]
    public async Task Extract_RefusesDangerousArchive()
    {
        using var temp = new TempDirectory();
        var path = temp.File("evil.zip");
        using (var zip = ZipFile.Open(path, ZipArchiveMode.Create))
        {
            using var writer = new StreamWriter(zip.CreateEntry("../../escape.txt").Open());
            writer.Write("bad");
        }

        var destination = temp.File("out");
        var exception = Assert.ThrowsAsync<InvalidOperationException>(
            async () => await ZipInspector.ExtractAsync(path, destination));
        Assert.That(exception!.Message, Does.Contain("безопасности"));
    }

    [Test]
    public async Task Extract_WorksForSafeArchive()
    {
        using var temp = new TempDirectory();
        var path = temp.File("ok.zip");
        using (var zip = ZipFile.Open(path, ZipArchiveMode.Create))
        {
            using var writer = new StreamWriter(zip.CreateEntry("images/boot.img").Open());
            writer.Write("kernel-data");
        }

        var destination = temp.File("out");
        var files = await ZipInspector.ExtractAsync(path, destination);

        Assert.That(files, Has.Count.EqualTo(1));
        Assert.That(File.Exists(temp.File("out/images/boot.img")), Is.True);
    }
}

[TestFixture]
public sealed class TarInspectorTests
{
    [Test]
    public void ListsEntries()
    {
        using var temp = new TempDirectory();
        var path = temp.File("a.tar");
        using (var stream = File.Create(path))
        using (var writer = new TarWriter(stream, TarEntryFormat.Ustar))
        {
            writer.WriteEntry(new UstarTarEntry(TarEntryType.RegularFile, "boot.img") { DataStream = new MemoryStream(new byte[16]) });
            writer.WriteEntry(new UstarTarEntry(TarEntryType.RegularFile, "vendor.img") { DataStream = new MemoryStream(new byte[32]) });
        }

        var inspection = TarInspector.InspectFile(path);
        Assert.That(inspection.SafeToExtract, Is.True);
        Assert.That(inspection.Entries.Count, Is.EqualTo(2));
        Assert.That(inspection.TotalUncompressedBytes, Is.EqualTo(48));
    }
}

[TestFixture]
public sealed class Lz4FrameTests
{
    private static byte[] BuildFrame(byte[] payload, bool uncompressed = true)
    {
        // FLG: version=1, block independent
        byte flg = 0x60;
        byte bd = 0x40; // 64 KB blocks

        var header = new List<byte>();
        header.AddRange(new byte[] { 0x04, 0x22, 0x4D, 0x18 });
        header.Add(flg);
        header.Add(bd);
        var checksum = (byte)(XxHash32.Hash(new[] { flg, bd }) >> 8);
        header.Add(checksum);

        var blockSize = uncompressed ? (uint)(payload.Length | 0x80000000) : (uint)payload.Length;
        var sizeBytes = new byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(sizeBytes, blockSize);
        header.AddRange(sizeBytes);
        header.AddRange(payload);
        header.AddRange(new byte[] { 0, 0, 0, 0 }); // end mark

        return header.ToArray();
    }

    [Test]
    public async Task DecompressesUncompressedBlock()
    {
        var content = Encoding.UTF8.GetBytes("NEXUS firmware test payload 1234567890");
        var frame = BuildFrame(content);

        using var input = new MemoryStream(frame);
        using var output = new MemoryStream();
        var info = await Lz4FrameDecoder.DecompressAsync(input, output);

        Assert.That(Encoding.UTF8.GetString(output.ToArray()), Is.EqualTo(Encoding.UTF8.GetString(content)));
        Assert.That(info.Version, Is.EqualTo(1));
        Assert.That(info.UncompressedBytes, Is.EqualTo(content.Length));
    }

    [Test]
    public async Task DecompressesLiteralOnlyBlock()
    {
        // LZ4-блок из одних литералов: токен 0x40 (4 литерала), затем данные.
        var block = new List<byte> { 0x40 };
        block.AddRange(Encoding.ASCII.GetBytes("abcd"));
        var frame = BuildFrame(block.ToArray(), uncompressed: false);

        using var input = new MemoryStream(frame);
        using var output = new MemoryStream();
        await Lz4FrameDecoder.DecompressAsync(input, output);

        Assert.That(Encoding.ASCII.GetString(output.ToArray()), Is.EqualTo("abcd"));
    }

    [Test]
    public async Task RejectsBrokenFrame()
    {
        using var input = new MemoryStream(Encoding.ASCII.GetBytes("not an lz4 frame"));
        using var output = new MemoryStream();

        var exception = Assert.ThrowsAsync<InvalidDataException>(
            async () => await Lz4FrameDecoder.DecompressAsync(input, output));
        Assert.That(exception!.Message, Does.Contain("LZ4"));
    }

    [Test]
    public void XxHash32_MatchesReferenceValue()
    {
        // Reference: xxh32("", seed 0) == 0x02CC5D05
        Assert.That(XxHash32.Hash(ReadOnlySpan<byte>.Empty), Is.EqualTo(0x02CC5D05u));
    }
}

[TestFixture]
public sealed class SparseImageTests
{
    private static byte[] BuildSparse(byte[] rawBlock, byte[] fillPattern)
    {
        var bytes = new List<byte>();
        var header = new byte[28];
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(0), SparseImageParser.Magic);
        BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(4), 1);
        BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(6), 0);
        BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(8), 28);
        BinaryPrimitives.WriteUInt16LittleEndian(header.AsSpan(10), 12);
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(12), 4096);
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(16), 3);
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(20), 3);
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(24), 0);
        bytes.AddRange(header);

        void Chunk(ushort type, uint blocks, uint dataSize)
        {
            var chunk = new byte[12];
            BinaryPrimitives.WriteUInt16LittleEndian(chunk.AsSpan(0), type);
            BinaryPrimitives.WriteUInt32LittleEndian(chunk.AsSpan(4), blocks);
            BinaryPrimitives.WriteUInt32LittleEndian(chunk.AsSpan(8), 12 + dataSize);
            bytes.AddRange(chunk);
        }

        Chunk(0xCAC1, 1, 4096);
        bytes.AddRange(rawBlock);
        Chunk(0xCAC2, 1, 4);
        bytes.AddRange(fillPattern);
        Chunk(0xCAC3, 1, 0);

        return bytes.ToArray();
    }

    [Test]
    public void ParsesHeaderAndChunks()
    {
        using var temp = new TempDirectory();
        var path = temp.File("system.img");
        File.WriteAllBytes(path, BuildSparse(new byte[4096], new byte[] { 0xAB, 0xCD, 0xEF, 0x01 }));

        var info = SparseImageParser.Read(path);

        Assert.That(info.TotalChunks, Is.EqualTo(3));
        Assert.That(info.Chunks.Select(c => c.Type), Is.EqualTo(new[] { "RAW", "FILL", "DONT_CARE" }));
        Assert.That(info.ExpectedOutputBytes, Is.EqualTo(3 * 4096));
    }

    [Test]
    public async Task UnsparseProducesRawImage()
    {
        using var temp = new TempDirectory();
        var raw = Enumerable.Repeat((byte)0x11, 4096).ToArray();
        var path = temp.File("system.img");
        File.WriteAllBytes(path, BuildSparse(raw, new byte[] { 0xAB, 0xCD, 0xEF, 0x01 }));

        var output = temp.File("system.raw.img");
        var written = await SparseImageParser.UnsparseAsync(path, output);

        Assert.That(written, Is.EqualTo(12288));
        Assert.That(new FileInfo(output).Length, Is.EqualTo(12288));

        var bytes = await File.ReadAllBytesAsync(output);
        Assert.That(bytes[0], Is.EqualTo(0x11));
        Assert.That(bytes[4096], Is.EqualTo(0xAB));
        Assert.That(bytes[4097], Is.EqualTo(0xCD));
        Assert.That(bytes[8192], Is.EqualTo(0));
    }

    [Test]
    public void RejectsInvalidMagic()
    {
        using var temp = new TempDirectory();
        var path = temp.File("bad.img");
        File.WriteAllBytes(path, new byte[64]);

        Assert.Throws<InvalidDataException>(() => SparseImageParser.Read(path));
    }
}

[TestFixture]
public sealed class BootImageTests
{
    [Test]
    public void ParsesVersion0Header()
    {
        using var temp = new TempDirectory();
        var path = temp.File("boot.img");
        var header = new byte[2048];
        Encoding.ASCII.GetBytes("ANDROID!").CopyTo(header, 0);
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(8), 4096);   // kernel size
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(16), 1024);  // ramdisk
        BinaryPrimitives.WriteUInt32LittleEndian(header.AsSpan(36), 2048);  // page size
        Encoding.ASCII.GetBytes("NEXUS-board").CopyTo(header, 48);
        Encoding.ASCII.GetBytes("console=ttyMSM0").CopyTo(header, 64);
        File.WriteAllBytes(path, header);

        var info = BootImageParser.TryRead(path);

        Assert.That(info, Is.Not.Null);
        Assert.That(info!.HeaderVersion, Is.EqualTo(0));
        Assert.That(info.KernelSize, Is.EqualTo(4096u));
        Assert.That(info.RamdiskSize, Is.EqualTo(1024u));
        Assert.That(info.PageSize, Is.EqualTo(2048u));
        Assert.That(info.Board, Is.EqualTo("NEXUS-board"));
        Assert.That(info.CommandLine, Does.Contain("console=ttyMSM0"));
    }

    [Test]
    public void ReturnsNullForOrdinaryFile()
    {
        using var temp = new TempDirectory();
        var path = temp.File("random.img");
        File.WriteAllBytes(path, new byte[256]);
        Assert.That(BootImageParser.TryRead(path), Is.Null);
    }
}
