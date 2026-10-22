using System.Buffers.Binary;
using System.Text;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Firmware.Ota;

/// <summary>
/// Разбор заголовка и манифеста Android OTA payload.bin (update_engine).
/// Манифест — protobuf; читаются только структура и имена разделов.
/// Полная сборка образов из операций payload не выполняется (см. ограничения).
/// </summary>
public sealed class PayloadInfo
{
    public ulong Version { get; init; }
    public long ManifestSize { get; init; }
    public long MetadataSignatureSize { get; init; }
    public int MinorVersion { get; init; }
    public long? MaxTimestamp { get; init; }
    public bool IsPartialUpdate { get; init; }
    public IReadOnlyList<PayloadPartition> Partitions { get; init; } = Array.Empty<PayloadPartition>();
    public long DataOffset { get; init; }
    public string? SignatureAlgorithm { get; init; }
}

public sealed record PayloadPartition(string Name, long? SizeBytes, int OperationCount, string? HashHex);

public static class PayloadParser
{
    public static bool LooksLikePayload(string path)
    {
        using var stream = File.OpenRead(path);
        Span<byte> magic = stackalloc byte[4];
        return stream.Read(magic) == 4 && magic.SequenceEqual("CrAU"u8);
    }

    public static PayloadInfo Read(string path)
    {
        using var stream = File.OpenRead(path);
        Span<byte> header = stackalloc byte[20];
        if (stream.Read(header) != 20)
        {
            throw new InvalidDataException("Файл слишком мал для заголовка payload.bin.");
        }

        if (!header[..4].SequenceEqual("CrAU"u8))
        {
            throw new InvalidDataException("Неверная сигнатура payload.bin.");
        }

        var version = BinaryPrimitives.ReadUInt64BigEndian(header[4..]);
        var manifestSize = (long)BinaryPrimitives.ReadUInt64BigEndian(header[12..]);
        var metadataSignatureSize = BinaryPrimitives.ReadUInt32BigEndian(header[20..]);

        if (manifestSize <= 0 || manifestSize > 64L * 1024 * 1024)
        {
            throw new InvalidDataException($"Недопустимый размер манифеста payload: {manifestSize}.");
        }

        var manifest = new byte[manifestSize];
        stream.ReadExactly(manifest);

        var proto = new ProtoReader(manifest);
        int minor = 0;
        long? maxTimestamp = null;
        var partial = false;
        var partitions = new List<PayloadPartition>();

        while (proto.TryReadField(out var field, out var wireType))
        {
            switch (field)
            {
                case 12 when wireType == 0:
                    minor = (int)proto.ReadVarint();
                    break;
                case 14 when wireType == 0:
                    maxTimestamp = (long)proto.ReadVarint();
                    break;
                case 16 when wireType == 0:
                    partial = proto.ReadVarint() != 0;
                    break;
                case 13 when wireType == 2:
                    var partitionBytes = proto.ReadLengthDelimited();
                    partitions.Add(ParsePartition(partitionBytes));
                    break;
                default:
                    proto.Skip(wireType);
                    break;
            }
        }

        var dataOffset = 20 + manifestSize + metadataSignatureSize;
        stream.Seek(0, SeekOrigin.Begin);
        var signatureAlgorithm = TryReadSignatureAlgorithm(stream, dataOffset, metadataSignatureSize);

        return new PayloadInfo
        {
            Version = version,
            ManifestSize = manifestSize,
            MetadataSignatureSize = metadataSignatureSize,
            MinorVersion = minor,
            MaxTimestamp = maxTimestamp,
            IsPartialUpdate = partial,
            Partitions = partitions,
            DataOffset = dataOffset,
            SignatureAlgorithm = signatureAlgorithm
        };
    }

    private static PayloadPartition ParsePartition(byte[] bytes)
    {
        var proto = new ProtoReader(bytes);
        var name = "unknown";
        long? size = null;
        var operations = 0;
        string? hash = null;

        while (proto.TryReadField(out var field, out var wireType))
        {
            switch (field)
            {
                case 1 when wireType == 2:
                    name = Encoding.UTF8.GetString(proto.ReadLengthDelimited());
                    break;
                case 7 when wireType == 2:
                    var info = new ProtoReader(proto.ReadLengthDelimited());
                    while (info.TryReadField(out var infoField, out var infoWire))
                    {
                        if (infoField == 1 && infoWire == 0)
                        {
                            size = (long)info.ReadVarint();
                        }
                        else if (infoField == 2 && infoWire == 2)
                        {
                            hash = Convert.ToHexStringLower(info.ReadLengthDelimited());
                        }
                        else
                        {
                            info.Skip(infoWire);
                        }
                    }

                    break;
                case 8 when wireType == 2:
                    operations++;
                    proto.Skip(wireType, alreadyConsumedField: false);
                    break;
                default:
                    proto.Skip(wireType);
                    break;
            }
        }

        return new PayloadPartition(name, size, operations, hash);
    }

    private static string? TryReadSignatureAlgorithm(Stream stream, long offset, long signatureSize)
    {
        if (signatureSize <= 0 || offset + signatureSize > stream.Length)
        {
            return null;
        }

        try
        {
            stream.Seek(offset, SeekOrigin.Begin);
            // Для версии 2 данные начинаются с подписи; алгоритм кодируется в первых байтах блока.
            // Читать полный формат без спецификации небезопасно — возвращаем только размер подписи.
            return $"metadata signature: {signatureSize} Б";
        }
        catch (IOException)
        {
            return null;
        }
    }
}

/// <summary>Минимальный читатель protobuf-полей (varint/length-delimited/fixed).</summary>
internal sealed class ProtoReader
{
    private readonly byte[] _data;
    private int _position;

    public ProtoReader(byte[] data)
    {
        _data = data;
    }

    public bool TryReadField(out int fieldNumber, out int wireType)
    {
        fieldNumber = 0;
        wireType = 0;

        if (_position >= _data.Length)
        {
            return false;
        }

        var key = ReadVarint();
        fieldNumber = (int)(key >> 3);
        wireType = (int)(key & 0x7);
        return fieldNumber > 0;
    }

    public ulong ReadVarint()
    {
        ulong result = 0;
        var shift = 0;
        while (shift < 64 && _position < _data.Length)
        {
            var b = _data[_position++];
            result |= (ulong)(b & 0x7F) << shift;
            if ((b & 0x80) == 0)
            {
                return result;
            }

            shift += 7;
        }

        throw new InvalidDataException("Повреждён protobuf varint.");
    }

    public byte[] ReadLengthDelimited()
    {
        var length = checked((int)ReadVarint());
        if (length < 0 || _position + length > _data.Length)
        {
            throw new InvalidDataException("Повреждён protobuf length-delimited блок.");
        }

        var result = _data.AsSpan(_position, length).ToArray();
        _position += length;
        return result;
    }

    public void Skip(int wireType, bool alreadyConsumedField = false)
    {
        _ = alreadyConsumedField;
        switch (wireType)
        {
            case 0:
                ReadVarint();
                break;
            case 1:
                _position += 8;
                break;
            case 2:
                var length = checked((int)ReadVarint());
                _position += length;
                break;
            case 5:
                _position += 4;
                break;
            default:
                throw new InvalidDataException($"Неподдерживаемый wire type protobuf: {wireType}.");
        }

        if (_position > _data.Length)
        {
            throw new InvalidDataException("Выход за границы protobuf-манифеста.");
        }
    }
}
