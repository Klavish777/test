using System.Buffers.Binary;
using System.Text;

namespace NexusFirmware.Firmware.Images;

/// <summary>Разбор заголовка Android boot image (versions 0–2). Только чтение.</summary>
public sealed class BootImageInfo
{
    public int HeaderVersion { get; init; }
    public uint KernelSize { get; init; }
    public uint RamdiskSize { get; init; }
    public uint PageSize { get; init; }
    public string? Board { get; init; }
    public string? Magic { get; init; }
    public string? CommandLine { get; init; }
    public long TotalImageSize { get; init; }
}

public static class BootImageParser
{
    public static bool LooksLikeBootImage(string path)
    {
        using var stream = File.OpenRead(path);
        Span<byte> magic = stackalloc byte[8];
        return stream.Read(magic) == 8 && magic.SequenceEqual("ANDROID!"u8);
    }

    public static BootImageInfo? TryRead(string path)
    {
        using var stream = File.OpenRead(path);
        return TryRead(stream);
    }

    public static BootImageInfo? TryRead(Stream stream)
    {
        var header = new byte[4096];
        var read = stream.Read(header, 0, header.Length);
        if (read < 44 || !header.AsSpan(0, 8).SequenceEqual("ANDROID!"u8))
        {
            return null;
        }

        // Структура заголовка: v0–v2 — kernel_size@8, ramdisk_size@16, page_size@36, header_version@40;
        // v3+ — kernel_size@8, ramdisk_size@12, header_version@40, страница фиксирована 4096.
        var headerVersion = (int)BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(40));
        if (headerVersion > 4)
        {
            headerVersion = 0;
        }

        var version = headerVersion;
        var kernelSize = BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(8));
        var ramdiskSize = version >= 3
            ? BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(12))
            : BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(16));
        var pageSize = version >= 3 ? 4096u : BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(36));
        var board = version >= 3 ? null : ReadCString(header, 48, 16);
        var cmdline = version >= 3 ? ReadCString(header, 44, 512) : ReadCString(header, 64, 512);

        if (pageSize == 0 || pageSize > 65536)
        {
            pageSize = 2048;
        }

        long total = pageSize;
        total += Align(kernelSize, pageSize);
        total += Align(ramdiskSize, pageSize);

        return new BootImageInfo
        {
            HeaderVersion = version,
            KernelSize = kernelSize,
            RamdiskSize = ramdiskSize,
            PageSize = pageSize,
            Board = string.IsNullOrWhiteSpace(board) ? null : board,
            CommandLine = string.IsNullOrWhiteSpace(cmdline) ? null : cmdline,
            Magic = "ANDROID!",
            TotalImageSize = total
        };
    }

    private static long Align(uint value, uint page) => ((value + page - 1) / page) * page;

    private static string ReadCString(byte[] data, int offset, int length)
    {
        if (offset >= data.Length)
        {
            return string.Empty;
        }

        var slice = data.AsSpan(offset, Math.Min(length, data.Length - offset));
        var end = slice.IndexOf((byte)0);
        if (end >= 0)
        {
            slice = slice[..end];
        }

        return Encoding.ASCII.GetString(slice).Trim();
    }
}
