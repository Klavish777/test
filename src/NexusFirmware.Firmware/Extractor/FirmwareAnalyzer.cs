using System.Globalization;
using System.Text;
using System.Text.Json;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Detection;
using NexusFirmware.Firmware.Images;
using NexusFirmware.Firmware.Ota;
using NexusFirmware.Firmware.Qualcomm;
using NexusFirmware.Firmware.Samsung;
using NexusFirmware.Firmware.Scatter;

namespace NexusFirmware.Firmware.Extractor;

public sealed record AnalysisRow(string Key, string Value);

public sealed class AnalysisSection
{
    public required string Title { get; init; }
    public required IReadOnlyList<AnalysisRow> Rows { get; init; }
    public IReadOnlyList<string> Notes { get; init; } = Array.Empty<string>();
}

public sealed class FirmwareAnalysis
{
    public required string FilePath { get; init; }
    public required string FileName { get; init; }
    public long SizeBytes { get; init; }
    public FirmwareFormat Format { get; init; }
    public string? Sha256 { get; init; }
    public IReadOnlyList<AnalysisSection> Sections { get; init; } = Array.Empty<AnalysisSection>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Limitations { get; init; } = Array.Empty<string>();
    public DateTimeOffset AnalyzedAt { get; init; } = DateTimeOffset.Now;

    public string Summary => $"{FileName} · {Format} · {SizeFormatting.HumanReadable(SizeBytes)}";
}

/// <summary>
/// Анализ файлов прошивок: определение контейнера, оглавление, заголовки образов,
/// таблицы разделов, sparse/payload/scatter/rawprogram. Работает только на чтение;
/// распаковка выполняется только во временный каталог.
/// </summary>
public sealed class FirmwareAnalyzer
{
    public FirmwareAnalysis Inspect(string filePath, bool computeHash = false, CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsReadableFile(filePath))
        {
            throw new FileNotFoundException("Файл не найден или пуст.", filePath);
        }

        var info = new FileInfo(filePath);
        var format = FormatDetector.Detect(filePath);
        var sections = new List<AnalysisSection>();
        var warnings = new List<string>();
        var limitations = new List<string>();

        var sha = computeHash ? Hashing.Sha256FileAsync(filePath, null, cancellationToken).GetAwaiter().GetResult() : null;

        sections.Add(new AnalysisSection
        {
            Title = "Файл",
            Rows =
            [
                new AnalysisRow("Путь", info.FullName),
                new AnalysisRow("Имя", info.Name),
                new AnalysisRow("Размер", $"{SizeFormatting.HumanReadable(info.Length)} ({info.Length} байт)"),
                new AnalysisRow("Изменён", info.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture)),
                new AnalysisRow("Формат", format.ToString()),
                new AnalysisRow("SHA-256", sha ?? "не вычислялся")
            ]
        });

        switch (format)
        {
            case FirmwareFormat.Zip:
                AnalyzeZip(filePath, sections, warnings);
                limitations.Add("Вложенные архивы и образы внутри ZIP не распаковываются автоматически при анализе — используйте извлечение.");
                break;

            case FirmwareFormat.Tar:
            case FirmwareFormat.TarMd5:
                AnalyzeTar(filePath, sections, warnings);
                limitations.Add("Содержимое TAR.MD5 перечисляется, но вложенные образы не разбираются без извлечения.");
                break;

            case FirmwareFormat.Gzip:
                AnalyzeGzip(filePath, sections, warnings);
                break;

            case FirmwareFormat.Lz4:
                AnalyzeLz4(filePath, sections, warnings);
                break;

            case FirmwareFormat.SparseImage:
                AnalyzeSparse(filePath, sections, warnings);
                break;

            case FirmwareFormat.PayloadBin:
                AnalyzePayload(filePath, sections, warnings);
                limitations.Add("Извлечение отдельных разделов из payload.bin не реализовано: формат требует операций update_engine.");
                break;

            case FirmwareFormat.Scatter:
                AnalyzeScatter(filePath, sections, warnings);
                break;

            case FirmwareFormat.RawProgramXml:
                AnalyzeRawProgram(filePath, sections, warnings);
                break;

            case FirmwareFormat.Image:
                AnalyzeImage(filePath, sections, warnings);
                break;

            default:
                warnings.Add($"Формат {format} не разбирается: доступен просмотр базовых сведений.");
                limitations.Add("Для этого формата парсер не реализован.");
                break;
        }

        var samsungComponent = SamsungFormat(format) || SamsungPackageAnalyzer.AnalyzeFile(filePath).Component is not null;
        if (samsungComponent && format is not FirmwareFormat.Zip)
        {
            try
            {
                var samsung = SamsungPackageAnalyzer.AnalyzeFile(filePath);
                sections.Add(new AnalysisSection
                {
                    Title = "Samsung",
                    Rows =
                    [
                        new AnalysisRow("Компонент", samsung.Component ?? "не распознан"),
                        new AnalysisRow("Код модели", samsung.ModelCode ?? "—"),
                        new AnalysisRow("PDA", samsung.PdaVersion ?? "—"),
                        new AnalysisRow("CSC", samsung.CscVersion ?? "—"),
                        new AnalysisRow("Ревизия загрузчика", samsung.BootloaderBinary ?? "—")
                    ],
                    Notes = samsung.Warnings
                });
            }
            catch (Exception ex) when (ex is IOException or InvalidDataException)
            {
                warnings.Add("Метаданные Samsung не прочитаны: " + ex.Message);
            }
        }

        return new FirmwareAnalysis
        {
            FilePath = filePath,
            FileName = info.Name,
            SizeBytes = info.Length,
            Format = format,
            Sha256 = sha,
            Sections = sections,
            Warnings = warnings,
            Limitations = limitations
        };
    }

    private static bool SamsungFormat(FirmwareFormat format) => format is
        FirmwareFormat.SamsungAp or FirmwareFormat.SamsungBl or FirmwareFormat.SamsungCp or
        FirmwareFormat.SamsungCsc or FirmwareFormat.SamsungHomeCsc or FirmwareFormat.TarMd5;

    private static void AnalyzeZip(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        var inspection = ZipInspector.Inspect(filePath);
        var rows = new List<AnalysisRow>
        {
            new("Записей", inspection.Entries.Count.ToString()),
            new("Суммарный размер после распаковки", SizeFormatting.HumanReadable(inspection.TotalUncompressedBytes))
        };

        sections.Add(new AnalysisSection { Title = "ZIP-контейнер", Rows = rows, Notes = inspection.Warnings });

        var entries = inspection.Entries
            .Where(e => !e.IsDirectory)
            .OrderByDescending(e => e.Length)
            .Take(500)
            .Select(e => new AnalysisRow(e.FullName, SizeFormatting.HumanReadable(e.Length)))
            .ToArray();

        sections.Add(new AnalysisSection { Title = "Содержимое", Rows = entries });
        warnings.AddRange(inspection.BlockingIssues);
    }

    private static void AnalyzeTar(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        var inspection = TarInspector.InspectFile(filePath);
        sections.Add(new AnalysisSection
        {
            Title = "TAR-контейнер",
            Rows =
            [
                new AnalysisRow("Записей", inspection.Entries.Count.ToString()),
                new AnalysisRow("Суммарный размер", SizeFormatting.HumanReadable(inspection.TotalUncompressedBytes))
            ],
            Notes = inspection.Warnings
        });

        sections.Add(new AnalysisSection
        {
            Title = "Содержимое",
            Rows = inspection.Entries
                .Where(e => !e.IsDirectory)
                .OrderByDescending(e => e.Length)
                .Take(500)
                .Select(e => new AnalysisRow(e.FullName, SizeFormatting.HumanReadable(e.Length)))
                .ToArray()
        });

        warnings.AddRange(inspection.BlockingIssues);
    }

    private static void AnalyzeGzip(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        using var stream = File.OpenRead(filePath);
        using var gzip = new System.IO.Compression.GZipStream(stream, System.IO.Compression.CompressionMode.Decompress, leaveOpen: true);
        var buffer = new byte[512];
        var read = gzip.Read(buffer, 0, buffer.Length);

        var innerFormat = FormatFromHeader(buffer.AsSpan(0, read));
        sections.Add(new AnalysisSection
        {
            Title = "GZip",
            Rows =
            [
                new AnalysisRow("Внутренний формат (по первым байтам)", innerFormat),
                new AnalysisRow("Ограничение", "Полная проверка возможна только после распаковки во временный каталог")
            ]
        });

        if (innerFormat == "Sparse image")
        {
            warnings.Add("Внутри GZip обнаружен Android sparse image.");
        }
    }

    private static void AnalyzeLz4(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        var temp = Path.Combine(Path.GetTempPath(), $"nexus_lz4_{Guid.NewGuid():N}.bin");
        try
        {
            using var input = File.OpenRead(filePath);
            using var output = File.Create(temp);
            var lz4Info = Lz4FrameDecoder.DecompressAsync(input, output).GetAwaiter().GetResult();
            output.Flush();

            sections.Add(new AnalysisSection
            {
                Title = "LZ4 Frame",
                Rows =
                [
                    new AnalysisRow("Версия", lz4Info.Version.ToString()),
                    new AnalysisRow("Блоков", lz4Info.TotalBlocks.ToString()),
                    new AnalysisRow("Максимальный размер блока", SizeFormatting.HumanReadable(lz4Info.MaxBlockSize)),
                    new AnalysisRow("Независимые блоки", lz4Info.BlockIndependent ? "да" : "нет"),
                    new AnalysisRow("Размер после распаковки", SizeFormatting.HumanReadable(lz4Info.UncompressedBytes)),
                    new AnalysisRow("Контрольные суммы", lz4Info.ContentChecksumValid ? "проверены" : "не подтверждены")
                ]
            });

            var header = new byte[512];
            using var inner = File.OpenRead(temp);
            var read = inner.Read(header, 0, header.Length);
            sections.Add(new AnalysisSection
            {
                Title = "Содержимое LZ4",
                Rows = [new AnalysisRow("Внутренний формат (по первым байтам)", FormatFromHeader(header.AsSpan(0, read)))]
            });
        }
        catch (InvalidDataException ex)
        {
            warnings.Add("LZ4 не прочитан: " + ex.Message);
        }
        finally
        {
            try
            {
                File.Delete(temp);
            }
            catch (IOException)
            {
            }
        }
    }

    private static void AnalyzeSparse(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        var sparse = SparseImageParser.Read(filePath);
        sections.Add(new AnalysisSection
        {
            Title = "Android sparse image",
            Rows =
            [
                new AnalysisRow("Версия", $"{sparse.MajorVersion}.{sparse.MinorVersion}"),
                new AnalysisRow("Размер блока", $"{sparse.BlockSize} Б"),
                new AnalysisRow("Всего блоков", sparse.TotalBlocks.ToString()),
                new AnalysisRow("Всего чанков", sparse.TotalChunks.ToString()),
                new AnalysisRow("Ожидаемый размер raw", SizeFormatting.HumanReadable(sparse.ExpectedOutputBytes))
            ]
        });

        sections.Add(new AnalysisSection
        {
            Title = "Чанки",
            Rows = sparse.Chunks.Take(500).Select(c => new AnalysisRow($"#{c.Index} {c.Type}", c.Description)).ToArray()
        });

        if (sparse.Chunks.Count == 0)
        {
            warnings.Add("Sparse-образ содержит 0 чанков (возможно, повреждён).");
        }
    }

    private static void AnalyzePayload(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        try
        {
            var payload = PayloadParser.Read(filePath);
            sections.Add(new AnalysisSection
            {
                Title = "OTA payload",
                Rows =
                [
                    new AnalysisRow("Версия формата", payload.Version.ToString()),
                    new AnalysisRow("Minor version", payload.MinorVersion.ToString()),
                    new AnalysisRow("Размер манифеста", SizeFormatting.HumanReadable(payload.ManifestSize)),
                    new AnalysisRow("Размер подписи метаданных", SizeFormatting.HumanReadable(payload.MetadataSignatureSize)),
                    new AnalysisRow("Частичное обновление", payload.IsPartialUpdate ? "да" : "нет"),
                    new AnalysisRow("Разделов", payload.Partitions.Count.ToString()),
                    new AnalysisRow("Данные начинаются с", payload.DataOffset.ToString())
                ]
            });

            sections.Add(new AnalysisSection
            {
                Title = "Разделы payload",
                Rows = payload.Partitions
                    .Select(p => new AnalysisRow(p.Name, $"{SizeFormatting.HumanReadable(p.SizeBytes ?? 0)}, операций: {p.OperationCount}"))
                    .ToArray()
            });
        }
        catch (InvalidDataException ex)
        {
            warnings.Add("payload.bin не прочитан: " + ex.Message);
        }
    }

    private static void AnalyzeScatter(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        var scatter = ScatterParser.Parse(filePath);
        sections.Add(new AnalysisSection
        {
            Title = "MediaTek scatter",
            Rows =
            [
                new AnalysisRow("Платформа", scatter.Platform ?? "не указана"),
                new AnalysisRow("Проект", scatter.Project ?? "—"),
                new AnalysisRow("Носитель", scatter.Storage ?? "—"),
                new AnalysisRow("Разделов", scatter.Partitions.Count.ToString()),
                new AnalysisRow("Суммарный размер", SizeFormatting.HumanReadable(scatter.TotalDeclaredBytes))
            ],
            Notes = scatter.Warnings
        });

        sections.Add(new AnalysisSection
        {
            Title = "Разделы",
            Rows = scatter.Partitions.Select(p => new AnalysisRow(
                p.PartitionName,
                $"{p.FileName ?? "—"} · {SizeFormatting.HumanReadable(p.PartitionSize ?? 0)} · {p.OperationType ?? "—"}")).ToArray()
        });

        warnings.AddRange(scatter.Warnings);

        var directory = Path.GetDirectoryName(filePath);
        if (directory is not null)
        {
            var checks = ScatterParser.VerifyFiles(scatter, directory);
            var missing = checks.Where(c => !c.FileExists).ToArray();
            if (missing.Length > 0)
            {
                warnings.Add($"Отсутствуют файлы образов для {missing.Length} разделов: {string.Join(", ", missing.Take(10).Select(m => m.FileName))}");
            }
        }
    }

    private static void AnalyzeRawProgram(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        try
        {
            var document = RawProgramParser.Parse(filePath);
            sections.Add(new AnalysisSection
            {
                Title = "Qualcomm rawprogram",
                Rows =
                [
                    new AnalysisRow("Продукт", document.ProductName ?? "—"),
                    new AnalysisRow("Записей <program>", document.Programs.Count.ToString()),
                    new AnalysisRow("<patch>", document.Patches.Count.ToString())
                ],
                Notes = document.Warnings
            });

            sections.Add(new AnalysisSection
            {
                Title = "Разделы",
                Rows = document.Programs.Take(500).Select(p => new AnalysisRow(
                    p.Label,
                    $"{p.FileName ?? "—"} · сектор {p.StartSector?.ToString() ?? "—"} · {p.NumSectors?.ToString() ?? "—"} сект.")).ToArray()
            });

            warnings.AddRange(document.Warnings);
        }
        catch (System.Xml.XmlException ex)
        {
            warnings.Add("XML не прочитан: " + ex.Message);
        }
    }

    private static void AnalyzeImage(string filePath, List<AnalysisSection> sections, List<string> warnings)
    {
        try
        {
            if (SparseImageParser.HasSparseMagic(filePath))
            {
                AnalyzeSparse(filePath, sections, warnings);
                return;
            }
        }
        catch (IOException)
        {
        }

        var boot = BootImageParser.TryRead(filePath);
        if (boot is not null)
        {
            sections.Add(new AnalysisSection
            {
                Title = "Android boot image",
                Rows =
                [
                    new AnalysisRow("Версия заголовка", boot.HeaderVersion.ToString()),
                    new AnalysisRow("Kernel", SizeFormatting.HumanReadable(boot.KernelSize)),
                    new AnalysisRow("Ramdisk", SizeFormatting.HumanReadable(boot.RamdiskSize)),
                    new AnalysisRow("Page size", boot.PageSize.ToString()),
                    new AnalysisRow("Board", boot.Board ?? "—"),
                    new AnalysisRow("Command line", boot.CommandLine ?? "—")
                ]
            });
            return;
        }

        sections.Add(new AnalysisSection
        {
            Title = "Образ",
            Rows = [new AnalysisRow("Тип", "RAW/неизвестный образ без распознанного заголовка")]
        });
        warnings.Add("Заголовок образа не распознан (не boot image и не sparse). Анализ таблицы разделов внутри образа не выполнялся.");
    }

    private static string FormatFromHeader(ReadOnlySpan<byte> header)
    {
        if (header.Length >= 4 && header[..4].SequenceEqual("CrAU"u8))
        {
            return "payload.bin";
        }

        if (header.Length >= 4 && header[..4].SequenceEqual(new byte[] { 0x3A, 0xFF, 0x26, 0xED }))
        {
            return "Android sparse image";
        }

        if (header.Length >= 4 && header[..4].SequenceEqual(new byte[] { 0x04, 0x22, 0x4D, 0x18 }))
        {
            return "LZ4 frame";
        }

        if (header.Length >= 2 && header[0] == 0x1F && header[1] == 0x8B)
        {
            return "GZip";
        }

        if (header.Length >= 265 && Encoding.ASCII.GetString(header.Slice(257, 5)).StartsWith("ustar", StringComparison.Ordinal))
        {
            return "TAR";
        }

        if (header.Length >= 4 && header[..4].SequenceEqual(new byte[] { 0x50, 0x4B, 0x03, 0x04 }))
        {
            return "ZIP";
        }

        if (header.Length >= 8 && header[..8].SequenceEqual("ANDROID!"u8))
        {
            return "Android boot image";
        }

        return "не определено";
    }

    public static string ToJson(FirmwareAnalysis analysis) => JsonSerializer.Serialize(new
    {
        analysis.FileName,
        analysis.FilePath,
        analysis.SizeBytes,
        Format = analysis.Format.ToString(),
        analysis.Sha256,
        analysis.AnalyzedAt,
        Sections = analysis.Sections.Select(s => new
        {
            s.Title,
            Rows = s.Rows.Select(r => new { r.Key, r.Value }),
            s.Notes
        }),
        analysis.Warnings,
        analysis.Limitations
    }, new JsonSerializerOptions { WriteIndented = true });

    public static string ToCsv(FirmwareAnalysis analysis)
    {
        var sb = new StringBuilder();
        sb.AppendLine("section;key;value");
        foreach (var section in analysis.Sections)
        {
            foreach (var row in section.Rows)
            {
                sb.AppendLine($"{EscapeCsv(section.Title)};{EscapeCsv(row.Key)};{EscapeCsv(row.Value)}");
            }
        }

        foreach (var warning in analysis.Warnings)
        {
            sb.AppendLine($"warnings;предупреждение;{EscapeCsv(warning)}");
        }

        return sb.ToString();
    }

    private static string EscapeCsv(string value) => value.Replace(";", ",").Replace("\r", " ").Replace("\n", " ");
}
