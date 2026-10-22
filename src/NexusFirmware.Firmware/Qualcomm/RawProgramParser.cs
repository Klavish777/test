using System.Globalization;
using System.Xml;
using System.Xml.Linq;

namespace NexusFirmware.Firmware.Qualcomm;

/// <summary>Запись rawprogram XML (Qualcomm Firehose-совместимый план программирования).</summary>
public sealed class RawProgramEntry
{
    public required string Label { get; init; }
    public string? FileName { get; init; }
    public int? PhysicalPartition { get; init; }
    public long? StartSector { get; init; }
    public long? NumSectors { get; init; }
    public long? SectorSize { get; init; }
    public bool Sparse { get; init; }
    public string? StartByteHex { get; init; }
}

public sealed class RawProgramDocument
{
    public required string FilePath { get; init; }
    public IReadOnlyList<RawProgramEntry> Programs { get; init; } = Array.Empty<RawProgramEntry>();
    public IReadOnlyList<string> Patches { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
    public string? ProductName { get; init; }
}

/// <summary>Разбор rawprogram XML из пакетов Qualcomm. DTD и внешние сущности запрещены.</summary>
public static class RawProgramParser
{
    public static RawProgramDocument Parse(string path)
    {
        var settings = new XmlReaderSettings
        {
            DtdProcessing = DtdProcessing.Prohibit,
            XmlResolver = null,
            IgnoreComments = true
        };

        var warnings = new List<string>();
        var programs = new List<RawProgramEntry>();
        var patches = new List<string>();
        string? product = null;

        using var stream = File.OpenRead(path);
        using var reader = XmlReader.Create(stream, settings);
        var document = XDocument.Load(reader);

        var root = document.Root;
        if (root is null)
        {
            return new RawProgramDocument { FilePath = path, Warnings = ["Пустой XML-документ."] };
        }

        product = root.Attribute("product_name")?.Value ?? root.Attribute("build")?.Value;

        foreach (var element in document.Descendants())
        {
            var name = element.Name.LocalName;
            if (name.Equals("program", StringComparison.OrdinalIgnoreCase))
            {
                var label = element.Attribute("label")?.Value;
                if (string.IsNullOrWhiteSpace(label))
                {
                    warnings.Add("Запись <program> без атрибута label пропущена.");
                    continue;
                }

                programs.Add(new RawProgramEntry
                {
                    Label = label,
                    FileName = NullIfEmpty(element.Attribute("filename")?.Value),
                    PhysicalPartition = ParseInt(element.Attribute("physical_partition_number")?.Value),
                    StartSector = ParseLong(element.Attribute("start_sector")?.Value),
                    NumSectors = ParseLong(element.Attribute("num_partition_sectors")?.Value),
                    SectorSize = ParseLong(element.Attribute("SECTOR_SIZE_IN_BYTES")?.Value),
                    Sparse = string.Equals(element.Attribute("sparse")?.Value, "true", StringComparison.OrdinalIgnoreCase),
                    StartByteHex = NullIfEmpty(element.Attribute("start_byte_hex")?.Value)
                });
            }
            else if (name.Equals("patch", StringComparison.OrdinalIgnoreCase))
            {
                var label = element.Attribute("filename")?.Value ?? element.Attribute("partition")?.Value;
                if (!string.IsNullOrWhiteSpace(label))
                {
                    patches.Add(label);
                }
            }
        }

        if (programs.Count == 0)
        {
            warnings.Add("В XML не найдено записей <program>.");
        }

        var missingPaths = programs.Where(p => p.StartSector is null && p.StartByteHex is null).ToArray();
        if (missingPaths.Length > 0)
        {
            warnings.Add($"{missingPaths.Length} записей без адреса начала — план неполный.");
        }

        return new RawProgramDocument
        {
            FilePath = path,
            Programs = programs,
            Patches = patches,
            Warnings = warnings,
            ProductName = product
        };
    }

    private static string? NullIfEmpty(string? value) => string.IsNullOrWhiteSpace(value) ? null : value;

    private static int? ParseInt(string? value) =>
        int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed) ? parsed : null;

    private static long? ParseLong(string? value) =>
        long.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed) ? parsed : null;
}
