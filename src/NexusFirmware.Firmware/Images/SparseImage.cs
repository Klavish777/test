using System.Buffers.Binary;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Firmware.Images;

/// <summary>Разбор Android sparse image (libsparse). Только чтение, оригинал не изменяется.</summary>
public sealed class SparseImageInfo
{
    public uint MajorVersion { get; init; }
    public uint MinorVersion { get; init; }
    public ushort FileHeaderSize { get; init; }
    public ushort ChunkHeaderSize { get; init; }
    public uint BlockSize { get; init; }
    public uint TotalBlocks { get; init; }
    public uint TotalChunks { get; init; }
    public long ExpectedOutputBytes { get; init; }
    public IReadOnlyList<SparseChunk> Chunks { get; init; } = Array.Empty<SparseChunk>();

    public string Summary =>
        $"sparse v{MajorVersion}.{MinorVersion}, блок {BlockSize} Б, блоков {TotalBlocks}, чанков {TotalChunks}, " +
        $"ожидаемый размер {SizeFormatting.HumanReadable(ExpectedOutputBytes)}";
}

public sealed record SparseChunk(int Index, string Type, uint BlockCount, long DataBytes, string Description);

public static class SparseImageParser
{
    public const uint Magic = 0xED26FF3A;
    private const ushort ChunkTypeRaw = 0xCAC1;
    private const ushort ChunkTypeFill = 0xCAC2;
    private const ushort ChunkTypeDontCare = 0xCAC3;
    private const ushort ChunkTypeCrc32 = 0xCAC4;

    public static bool HasSparseMagic(string filePath)
    {
        using var stream = File.OpenRead(filePath);
        Span<byte> magic = stackalloc byte[4];
        return stream.Read(magic) == 4 && BinaryPrimitives.ReadUInt32LittleEndian(magic) == Magic;
    }

    public static SparseImageInfo Read(string filePath)
    {
        using var stream = File.OpenRead(filePath);
        return Read(stream);
    }

    public static SparseImageInfo Read(Stream stream)
    {
        Span<byte> header = stackalloc byte[28];
        if (stream.Read(header) != 28)
        {
            throw new InvalidDataException("Файл слишком мал для sparse-заголовка.");
        }

        var magic = BinaryPrimitives.ReadUInt32LittleEndian(header);
        if (magic != Magic)
        {
            throw new InvalidDataException("Неверная сигнатура sparse image (ожидался 0xED26FF3A).");
        }

        var major = BinaryPrimitives.ReadUInt16LittleEndian(header[4..]);
        var minor = BinaryPrimitives.ReadUInt16LittleEndian(header[6..]);
        var fileHeaderSize = BinaryPrimitives.ReadUInt16LittleEndian(header[8..]);
        var chunkHeaderSize = BinaryPrimitives.ReadUInt16LittleEndian(header[10..]);
        var blockSize = BinaryPrimitives.ReadUInt32LittleEndian(header[12..]);
        var totalBlocks = BinaryPrimitives.ReadUInt32LittleEndian(header[16..]);
        var totalChunks = BinaryPrimitives.ReadUInt32LittleEndian(header[20..]);
        var checksum = BinaryPrimitives.ReadUInt32LittleEndian(header[24..]);

        if (fileHeaderSize < 28 || chunkHeaderSize < 12 || blockSize == 0)
        {
            throw new InvalidDataException("Некорректные параметры sparse-заголовка.");
        }

        if (stream.CanSeek)
        {
            stream.Seek(fileHeaderSize, SeekOrigin.Begin);
        }

        var chunks = new List<SparseChunk>();
        long expected = 0;
        var chunkHeader = new byte[12];

        for (var i = 0; i < totalChunks; i++)
        {
            if (stream.Read(chunkHeader) != 12)
            {
                throw new InvalidDataException($"Обрыв данных: чанк {i + 1} из {totalChunks} не найден.");
            }

            var type = BinaryPrimitives.ReadUInt16LittleEndian(chunkHeader);
            var blocks = BinaryPrimitives.ReadUInt32LittleEndian(chunkHeader.AsSpan(4));
            var totalSize = BinaryPrimitives.ReadUInt32LittleEndian(chunkHeader.AsSpan(8));
            var dataBytes = Math.Max(0, totalSize - (long)chunkHeaderSize);

            string typeName;
            string description;
            long outputBytes;

            switch (type)
            {
                case ChunkTypeRaw:
                    typeName = "RAW";
                    outputBytes = (long)blocks * blockSize;
                    description = $"{blocks} блок(ов) реальных данных";
                    break;
                case ChunkTypeFill:
                    typeName = "FILL";
                    outputBytes = (long)blocks * blockSize;
                    var pattern = new byte[4];
                    if (dataBytes >= 4)
                    {
                        stream.ReadExactly(pattern);
                        description = $"{blocks} блок(ов) заполнения шаблоном 0x{BinaryPrimitives.ReadUInt32LittleEndian(pattern):X8}";
                        stream.Seek(dataBytes - 4, SeekOrigin.Current);
                    }
                    else
                    {
                        description = $"{blocks} блок(ов) заполнения";
                    }

                    break;
                case ChunkTypeDontCare:
                    typeName = "DONT_CARE";
                    outputBytes = (long)blocks * blockSize;
                    description = $"{blocks} блок(ов) без данных (нули)";
                    break;
                case ChunkTypeCrc32:
                    typeName = "CRC32";
                    outputBytes = 0;
                    description = $"Контрольная сумма CRC32 чанка (заявленная: 0x{checksum:X8})";
                    break;
                default:
                    typeName = $"0x{type:X4}";
                    outputBytes = 0;
                    description = "Неизвестный тип чанка";
                    break;
            }

            if (dataBytes > 0 && type is not (ChunkTypeFill))
            {
                if (stream.CanSeek)
                {
                    stream.Seek(dataBytes, SeekOrigin.Current);
                }
                else
                {
                    var buffer = new byte[Math.Min(dataBytes, 1024 * 1024)];
                    var remaining = dataBytes;
                    while (remaining > 0)
                    {
                        var read = stream.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                        if (read == 0)
                        {
                            break;
                        }

                        remaining -= read;
                    }
                }
            }

            expected += outputBytes;
            chunks.Add(new SparseChunk(i + 1, typeName, blocks, dataBytes, description));
        }

        return new SparseImageInfo
        {
            MajorVersion = major,
            MinorVersion = minor,
            FileHeaderSize = fileHeaderSize,
            ChunkHeaderSize = chunkHeaderSize,
            BlockSize = blockSize,
            TotalBlocks = totalBlocks,
            TotalChunks = totalChunks,
            ExpectedOutputBytes = expected,
            Chunks = chunks
        };
    }

    /// <summary>Разворачивание sparse image в raw-файл (в указанный каталог, не рядом с оригиналом).</summary>
    public static async Task<long> UnsparseAsync(string sparsePath, string rawOutputPath, IProgress<double>? progress = null, CancellationToken cancellationToken = default)
    {
        var info = Read(sparsePath);
        await using var source = File.OpenRead(sparsePath);
        source.Seek(info.FileHeaderSize, SeekOrigin.Begin);
        await using var target = new FileStream(rawOutputPath, FileMode.Create, FileAccess.Write, FileShare.None, 1024 * 1024, useAsync: true);

        var chunkHeader = new byte[12];
        var buffer = new byte[1024 * 1024];
        long written = 0;

        for (var i = 0; i < info.TotalChunks; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            source.ReadExactly(chunkHeader);

            var type = BinaryPrimitives.ReadUInt16LittleEndian(chunkHeader);
            var blocks = BinaryPrimitives.ReadUInt32LittleEndian(chunkHeader.AsSpan(4));
            var totalSize = BinaryPrimitives.ReadUInt32LittleEndian(chunkHeader.AsSpan(8));
            var dataBytes = Math.Max(0, totalSize - (long)info.ChunkHeaderSize);
            var outputBytes = (long)blocks * info.BlockSize;

            switch (type)
            {
                case 0xCAC1:
                {
                    var remaining = dataBytes;
                    while (remaining > 0)
                    {
                        var read = await source.ReadAsync(buffer.AsMemory(0, (int)Math.Min(buffer.Length, remaining)), cancellationToken).ConfigureAwait(false);
                        if (read == 0)
                        {
                            throw new InvalidDataException("Обрыв данных в RAW-чанке.");
                        }

                        await target.WriteAsync(buffer.AsMemory(0, read), cancellationToken).ConfigureAwait(false);
                        remaining -= read;
                        written += read;
                        Report(progress, written, info.ExpectedOutputBytes);
                    }

                    break;
                }

                case 0xCAC2:
                {
                    var pattern = new byte[4];
                    await source.ReadAsync(pattern, cancellationToken).ConfigureAwait(false);
                    if (dataBytes > 4)
                    {
                        source.Seek(dataBytes - 4, SeekOrigin.Current);
                    }

                    var fill = new byte[Math.Min(outputBytes, buffer.Length)];
                    for (var offset = 0; offset < fill.Length; offset += 4)
                    {
                        Buffer.BlockCopy(pattern, 0, fill, offset, Math.Min(4, fill.Length - offset));
                    }

                    var remaining = outputBytes;
                    while (remaining > 0)
                    {
                        var count = (int)Math.Min(fill.Length, remaining);
                        await target.WriteAsync(fill.AsMemory(0, count), cancellationToken).ConfigureAwait(false);
                        remaining -= count;
                        written += count;
                        Report(progress, written, info.ExpectedOutputBytes);
                    }

                    break;
                }

                case 0xCAC3:
                {
                    Array.Clear(buffer);
                    var remaining = outputBytes;
                    while (remaining > 0)
                    {
                        var count = (int)Math.Min(buffer.Length, remaining);
                        await target.WriteAsync(buffer.AsMemory(0, count), cancellationToken).ConfigureAwait(false);
                        remaining -= count;
                        written += count;
                        Report(progress, written, info.ExpectedOutputBytes);
                    }

                    break;
                }

                default:
                    if (dataBytes > 0)
                    {
                        source.Seek(dataBytes, SeekOrigin.Current);
                    }

                    break;
            }
        }

        progress?.Report(100);
        return written;
    }

    private static void Report(IProgress<double>? progress, long written, long expected)
    {
        if (progress is not null && expected > 0)
        {
            progress.Report(Math.Clamp(written * 100.0 / expected, 0, 100));
        }
    }
}
