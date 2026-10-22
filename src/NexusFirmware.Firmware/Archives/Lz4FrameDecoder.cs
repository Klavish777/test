using System.Buffers.Binary;

namespace NexusFirmware.Firmware.Archives;

/// <summary>
/// Минимальный декодер формата LZ4 Frame (RFC-совместимый): поддерживаются независимые
/// и связанные блоки, несжатые блоки, проверки блоков и содержимого (XXH32).
/// Используется для анализа образов прошивок, упакованных в .lz4.
/// </summary>
public static class Lz4FrameDecoder
{
    private static readonly uint FrameMagic = 0x184D2204;

    public sealed class Lz4Info
    {
        public int Version { get; init; }
        public bool BlockIndependent { get; init; }
        public bool BlockChecksum { get; init; }
        public bool ContentChecksum { get; init; }
        public bool ContentSizePresent { get; init; }
        public long? ContentSize { get; init; }
        public int MaxBlockSize { get; init; }
        public long TotalBlocks { get; init; }
        public long UncompressedBytes { get; init; }
        public bool ContentChecksumValid { get; init; }
    }

    public static bool IsLz4Frame(ReadOnlySpan<byte> header) =>
        header.Length >= 4 && BinaryPrimitives.ReadUInt32LittleEndian(header) == FrameMagic;

    public static async Task<Lz4Info> DecompressAsync(Stream input, Stream output, CancellationToken cancellationToken = default)
    {
        var header = new byte[4];
        if (await ReadExactAsync(input, header, cancellationToken).ConfigureAwait(false) != 4 ||
            BinaryPrimitives.ReadUInt32LittleEndian(header) != FrameMagic)
        {
            throw new InvalidDataException("Файл не является LZ4 Frame (неверная сигнатура).");
        }

        var descriptor = new byte[2];
        if (await ReadExactAsync(input, descriptor, cancellationToken).ConfigureAwait(false) != 2)
        {
            throw new InvalidDataException("Повреждён заголовок LZ4 Frame.");
        }

        var flg = descriptor[0];
        var bd = descriptor[1];
        var version = (flg >> 6) & 0x03;
        if (version != 1)
        {
            throw new InvalidDataException($"Неподдерживаемая версия LZ4 Frame: {version}.");
        }

        var blockIndependent = (flg & 0x20) != 0;
        var blockChecksum = (flg & 0x10) != 0;
        var contentSizePresent = (flg & 0x08) != 0;
        var contentChecksum = (flg & 0x04) != 0;
        var dictIdPresent = (flg & 0x01) != 0;
        var maxBlockSize = ((bd >> 4) & 0x07) switch
        {
            4 => 64 * 1024,
            5 => 256 * 1024,
            6 => 1024 * 1024,
            7 => 4 * 1024 * 1024,
            _ => throw new InvalidDataException("Недопустимый размер блока LZ4 Frame.")
        };

        long? contentSize = null;
        if (contentSizePresent)
        {
            var sizeBuffer = new byte[8];
            if (await ReadExactAsync(input, sizeBuffer, cancellationToken).ConfigureAwait(false) != 8)
            {
                throw new InvalidDataException("Повреждён заголовок LZ4 Frame (content size).");
            }

            contentSize = (long)BinaryPrimitives.ReadUInt64LittleEndian(sizeBuffer);
        }

        if (dictIdPresent)
        {
            var dictBuffer = new byte[4];
            if (await ReadExactAsync(input, dictBuffer, cancellationToken).ConfigureAwait(false) != 4)
            {
                throw new InvalidDataException("Повреждён заголовок LZ4 Frame (dictionary).");
            }
        }

        var headerChecksum = new byte[1];
        if (await ReadExactAsync(input, headerChecksum, cancellationToken).ConfigureAwait(false) != 1)
        {
            throw new InvalidDataException("Повреждён заголовок LZ4 Frame (checksum).");
        }

        var headerBytes = new List<byte> { flg, bd };
        if (contentSize is not null)
        {
            headerBytes.AddRange(BitConverter.GetBytes((ulong)contentSize.Value));
        }

        var computedHeaderChecksum = (byte)(XxHash32.Hash(headerBytes.ToArray()) >> 8);
        var headerValid = computedHeaderChecksum == headerChecksum[0];

        var blockHeader = new byte[4];
        var window = new byte[64 * 1024];
        var windowLength = 0;
        long totalBlocks = 0;
        long uncompressedTotal = 0;
        long written = 0;

        // Контрольная сумма содержимого считается потоково по распакованным блокам.
        var contentHasher = contentChecksum ? new XxHash32() : null;

        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (await ReadExactAsync(input, blockHeader, cancellationToken).ConfigureAwait(false) != 4)
            {
                throw new InvalidDataException("Неожиданный конец LZ4-потока.");
            }

            var rawBlockSize = BinaryPrimitives.ReadUInt32LittleEndian(blockHeader);
            if (rawBlockSize == 0)
            {
                break;
            }

            var uncompressedBlock = (rawBlockSize & 0x80000000u) != 0;
            var blockSize = (int)(rawBlockSize & 0x7FFFFFFFu);
            if (blockSize <= 0 || blockSize > maxBlockSize)
            {
                throw new InvalidDataException($"Недопустимый размер блока LZ4: {blockSize}.");
            }

            var blockData = new byte[blockSize];
            if (await ReadExactAsync(input, blockData, cancellationToken).ConfigureAwait(false) != blockSize)
            {
                throw new InvalidDataException("Повреждён блок LZ4.");
            }

            if (blockChecksum)
            {
                var checksum = new byte[4];
                if (await ReadExactAsync(input, checksum, cancellationToken).ConfigureAwait(false) != 4)
                {
                    throw new InvalidDataException("Повреждена контрольная сумма блока LZ4.");
                }

                var expected = BinaryPrimitives.ReadUInt32LittleEndian(checksum);
                if (XxHash32.Hash(blockData) != expected)
                {
                    throw new InvalidDataException("Контрольная сумма блока LZ4 не совпадает.");
                }
            }

            byte[] decoded;
            if (uncompressedBlock)
            {
                decoded = blockData;
            }
            else
            {
                decoded = new byte[maxBlockSize];
                var combined = new byte[windowLength + blockData.Length];
                Buffer.BlockCopy(window, 0, combined, 0, windowLength);
                Buffer.BlockCopy(blockData, 0, combined, windowLength, blockData.Length);
                var produced = DecodeBlock(combined, windowLength, decoded);
                decoded = decoded[..produced];
            }

            await output.WriteAsync(decoded, cancellationToken).ConfigureAwait(false);
            uncompressedTotal += decoded.Length;
            written += decoded.Length;
            totalBlocks++;

            contentHasher?.Append(decoded);

            // Обновляем окно (последние 64 КБ распакованных данных).
            UpdateWindow(decoded, window, ref windowLength);
        }

        var contentChecksumValid = true;
        if (contentChecksum)
        {
            var checksum = new byte[4];
            if (await ReadExactAsync(input, checksum, cancellationToken).ConfigureAwait(false) == 4)
            {
                var expected = BinaryPrimitives.ReadUInt32LittleEndian(checksum);
                var actual = contentHasher!.Finish();
                contentChecksumValid = actual == expected;
            }
            else
            {
                contentChecksumValid = false;
            }
        }

        if (contentSize is not null && written != contentSize.Value)
        {
            throw new InvalidDataException($"Размер распакованных данных ({written}) не совпадает с заявленным ({contentSize}).");
        }

        return new Lz4Info
        {
            Version = version,
            BlockIndependent = blockIndependent,
            BlockChecksum = blockChecksum,
            ContentChecksum = contentChecksum,
            ContentSizePresent = contentSizePresent,
            ContentSize = contentSize,
            MaxBlockSize = maxBlockSize,
            TotalBlocks = totalBlocks,
            UncompressedBytes = uncompressedTotal,
            ContentChecksumValid = contentChecksumValid && headerValid
        };
    }

    private static void UpdateWindow(byte[] decoded, byte[] window, ref int windowLength)
    {
        if (decoded.Length >= window.Length)
        {
            Buffer.BlockCopy(decoded, decoded.Length - window.Length, window, 0, window.Length);
            windowLength = window.Length;
            return;
        }

        var keep = Math.Min(windowLength, window.Length - decoded.Length);
        if (keep > 0)
        {
            Buffer.BlockCopy(window, windowLength - keep, window, 0, keep);
        }

        Buffer.BlockCopy(decoded, 0, window, keep, decoded.Length);
        windowLength = keep + decoded.Length;
    }

    /// <summary>Декодирование одного LZ4-блока. <paramref name="prefixLength"/> — размер окна перед блоком.</summary>
    private static int DecodeBlock(byte[] source, int prefixLength, byte[] destination)
    {
        var src = prefixLength;
        var dst = prefixLength;
        var srcEnd = source.Length;

        while (src < srcEnd)
        {
            var token = source[src++];
            var literalLength = token >> 4;

            if (literalLength == 15)
            {
                int extra;
                do
                {
                    if (src >= srcEnd)
                    {
                        throw new InvalidDataException("Повреждён LZ4-блок (длина литералов).");
                    }

                    extra = source[src++];
                    literalLength += extra;
                }
                while (extra == 255);
            }

            if (src + literalLength > srcEnd || dst + literalLength > destination.Length)
            {
                throw new InvalidDataException("Повреждён LZ4-блок (переполнение литералов).");
            }

            Buffer.BlockCopy(source, src, destination, dst, literalLength);
            src += literalLength;
            dst += literalLength;

            if (src >= srcEnd)
            {
                break;
            }

            if (src + 2 > srcEnd)
            {
                throw new InvalidDataException("Повреждён LZ4-блок (смещение).");
            }

            var offset = source[src] | (source[src + 1] << 8);
            src += 2;
            if (offset == 0 || offset > dst)
            {
                throw new InvalidDataException("Повреждён LZ4-блок (недопустимое смещение).");
            }

            var matchLength = token & 0x0F;
            if (matchLength == 15)
            {
                int extra;
                do
                {
                    if (src >= srcEnd)
                    {
                        throw new InvalidDataException("Повреждён LZ4-блок (длина совпадения).");
                    }

                    extra = source[src++];
                    matchLength += extra;
                }
                while (extra == 255);
            }

            matchLength += 4;

            if (dst + matchLength > destination.Length)
            {
                throw new InvalidDataException("Повреждён LZ4-блок (переполнение совпадения).");
            }

            var matchIndex = dst - offset;
            for (var i = 0; i < matchLength; i++)
            {
                destination[dst + i] = destination[matchIndex + i];
            }

            dst += matchLength;
        }

        return dst - prefixLength;
    }

    private static async Task<int> ReadExactAsync(Stream stream, byte[] buffer, CancellationToken cancellationToken)
    {
        var total = 0;
        while (total < buffer.Length)
        {
            var read = await stream.ReadAsync(buffer.AsMemory(total, buffer.Length - total), cancellationToken).ConfigureAwait(false);
            if (read == 0)
            {
                break;
            }

            total += read;
        }

        return total;
    }
}

/// <summary>XXH32 — контрольные суммы LZ4 Frame (потоковый режим).</summary>
public sealed class XxHash32
{
    private const uint Prime1 = 2654435761u;
    private const uint Prime2 = 2246822519u;
    private const uint Prime3 = 3266489917u;
    private const uint Prime4 = 668265263u;
    private const uint Prime5 = 374761393u;

    private readonly byte[] _buffer = new byte[16];
    private readonly uint _seed;
    private int _bufferLength;
    private uint _v1;
    private uint _v2;
    private uint _v3;
    private uint _v4;
    private long _totalLength;
    private bool _hasBlocks;

    public XxHash32(uint seed = 0)
    {
        _seed = seed;
        _v1 = seed + Prime1 + Prime2;
        _v2 = seed + Prime2;
        _v3 = seed;
        _v4 = seed - Prime1;
    }

    public void Append(ReadOnlySpan<byte> data)
    {
        _totalLength += data.Length;

        if (_bufferLength > 0)
        {
            var needed = 16 - _bufferLength;
            var take = Math.Min(needed, data.Length);
            data[..take].CopyTo(_buffer.AsSpan(_bufferLength));
            _bufferLength += take;
            data = data[take..];

            if (_bufferLength == 16)
            {
                Absorb(_buffer);
                _bufferLength = 0;
            }
        }

        while (data.Length >= 16)
        {
            Absorb(data[..16]);
            data = data[16..];
            _hasBlocks = true;
        }

        if (data.Length > 0)
        {
            data.CopyTo(_buffer.AsSpan(_bufferLength));
            _bufferLength += data.Length;
        }
    }

    private void Absorb(ReadOnlySpan<byte> block)
    {
        _v1 = Round(_v1, BinaryPrimitives.ReadUInt32LittleEndian(block));
        _v2 = Round(_v2, BinaryPrimitives.ReadUInt32LittleEndian(block[4..]));
        _v3 = Round(_v3, BinaryPrimitives.ReadUInt32LittleEndian(block[8..]));
        _v4 = Round(_v4, BinaryPrimitives.ReadUInt32LittleEndian(block[12..]));
        _hasBlocks = true;
    }

    public uint Finish()
    {
        var hash = _hasBlocks
            ? RotateLeft(_v1, 1) + RotateLeft(_v2, 7) + RotateLeft(_v3, 12) + RotateLeft(_v4, 18)
            : _seed + Prime5;

        hash += (uint)_totalLength;

        var index = 0;
        while (index <= _bufferLength - 4)
        {
            hash += BinaryPrimitives.ReadUInt32LittleEndian(_buffer.AsSpan(index)) * Prime3;
            hash = RotateLeft(hash, 17) * Prime4;
            index += 4;
        }

        while (index < _bufferLength)
        {
            hash += _buffer[index] * Prime5;
            hash = RotateLeft(hash, 11) * Prime1;
            index++;
        }

        hash ^= hash >> 15;
        hash *= Prime2;
        hash ^= hash >> 13;
        hash *= Prime3;
        hash ^= hash >> 16;
        return hash;
    }

    public static uint Hash(ReadOnlySpan<byte> data, uint seed = 0)
    {
        var hasher = new XxHash32(seed);
        hasher.Append(data);
        return hasher.Finish();
    }

    private static uint Round(uint acc, uint input) => RotateLeft(acc + input * Prime2, 13) * Prime1;

    private static uint RotateLeft(uint value, int count) => (value << count) | (value >> (32 - count));
}
