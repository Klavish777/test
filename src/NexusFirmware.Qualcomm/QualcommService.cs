using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Qualcomm;

namespace NexusFirmware.Qualcomm;

public sealed class QualcommFileInfo
{
    public required string FileName { get; init; }
    public required string FullPath { get; init; }
    public long SizeBytes { get; init; }
    public string? Sha256 { get; init; }
    public string Kind { get; init; } = "неизвестно";
    public IReadOnlyList<string> Notes { get; init; } = Array.Empty<string>();
}

public sealed class QualcommPackageAnalysis
{
    public required string Directory { get; init; }
    public IReadOnlyList<QualcommFileInfo> Files { get; init; } = Array.Empty<QualcommFileInfo>();
    public IReadOnlyList<RawProgramDocument> RawPrograms { get; init; } = Array.Empty<RawProgramDocument>();
    public IReadOnlyList<CompatibilityItem> Checks { get; init; } = Array.Empty<CompatibilityItem>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();

    public bool HasProgrammer => Files.Any(f => f.Kind == "programmer");
    public bool IsComplete => RawPrograms.Count > 0 && HasProgrammer;
}

/// <summary>
/// Сервис Qualcomm: анализ сервисных пакетов (rawprogram XML, programmer-файлы), диагностика EDL.
/// Реализация протокола Firehose и работа с неподтверждёнными programmer-файлами НЕ выполняются.
/// </summary>
public sealed class QualcommService
{
    private static readonly HashSet<string> ProgrammerExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mbn", ".elf", ".bin"
    };

    private readonly ILogBus _log;
    private readonly IToolLocator _locator;

    public QualcommService(ILogBus log, IToolLocator locator)
    {
        _log = log;
        _locator = locator;
    }

    /// <summary>Устройства в режиме EDL (9008) — только реально обнаруженные.</summary>
    public IReadOnlyList<DeviceInfo> FindEdlDevices(IEnumerable<DeviceInfo> devices) =>
        devices.Where(d =>
            d.VendorId is not null &&
            d.VendorId.Equals("05C6", StringComparison.OrdinalIgnoreCase) &&
            (d.ProductId?.Equals("9008", StringComparison.OrdinalIgnoreCase) == true || d.Mode == DeviceMode.QualcommEdl))
            .ToArray();

    public bool IsEdlSupportedEnvironment => OperatingSystem.IsWindows();

    public async Task<QualcommPackageAnalysis> AnalyzePackageAsync(
        string directory,
        bool computeHashes = false,
        CancellationToken cancellationToken = default)
    {
        if (!PathSafety.IsExistingDirectory(directory))
        {
            throw new DirectoryNotFoundException(directory);
        }

        var files = new List<QualcommFileInfo>();
        var rawPrograms = new List<RawProgramDocument>();
        var checks = new List<CompatibilityItem>();
        var warnings = new List<string>();

        foreach (var path in Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories))
        {
            cancellationToken.ThrowIfCancellationRequested();
            var name = Path.GetFileName(path);
            var extension = Path.GetExtension(path).ToLowerInvariant();
            var info = new FileInfo(path);
            var notes = new List<string>();
            string kind;

            if (name.StartsWith("rawprogram", StringComparison.OrdinalIgnoreCase) && extension == ".xml")
            {
                kind = "rawprogram";
                try
                {
                    var document = RawProgramParser.Parse(path);
                    rawPrograms.Add(document);
                    notes.Add($"Записей: {document.Programs.Count}, patch: {document.Patches.Count}.");
                    warnings.AddRange(document.Warnings.Select(w => $"{name}: {w}"));
                }
                catch (System.Xml.XmlException ex)
                {
                    notes.Add("XML не прочитан: " + ex.Message);
                    warnings.Add($"{name}: некорректный XML.");
                }
            }
            else if (name.StartsWith("patch", StringComparison.OrdinalIgnoreCase) && extension == ".xml")
            {
                kind = "patch-xml";
            }
            else if (ProgrammerExtensions.Contains(extension) &&
                     (name.Contains("prog", StringComparison.OrdinalIgnoreCase) ||
                      name.Contains("firehose", StringComparison.OrdinalIgnoreCase) ||
                      extension == ".mbn"))
            {
                kind = "programmer";
                notes.Add("Programmer-файл: подлинность невозможно подтвердить средствами приложения. Используйте только файл из официального источника.");
                if (extension == ".mbn")
                {
                    notes.Add("Формат MBN не разбирается: содержимое не проверяется.");
                }
            }
            else if (name.Contains("gpt", StringComparison.OrdinalIgnoreCase))
            {
                kind = "gpt";
            }
            else if (extension is ".xml")
            {
                kind = "xml";
            }
            else
            {
                kind = "data";
            }

            string? sha = null;
            if (computeHashes && info.Length < 512L * 1024 * 1024)
            {
                sha = await Hashing.Sha256FileAsync(path, null, cancellationToken).ConfigureAwait(false);
            }

            files.Add(new QualcommFileInfo
            {
                FileName = name,
                FullPath = path,
                SizeBytes = info.Length,
                Sha256 = sha,
                Kind = kind,
                Notes = notes
            });
        }

        if (rawPrograms.Count == 0)
        {
            checks.Add(new CompatibilityItem("rawprogram", CompatibilitySeverity.Warning,
                "В каталоге нет rawprogram*.xml — план программирования отсутствует."));
        }
        else
        {
            checks.Add(new CompatibilityItem("rawprogram", CompatibilitySeverity.Info,
                $"Найдено планов: {rawPrograms.Count}."));
        }

        if (!files.Any(f => f.Kind == "programmer"))
        {
            checks.Add(new CompatibilityItem("programmer", CompatibilitySeverity.Blocking,
                "Не найден programmer-файл (firehose), без него работа в EDL невозможна."));
        }
        else
        {
            checks.Add(new CompatibilityItem("programmer", CompatibilitySeverity.Warning,
                "Programmer-файл должен быть получен из официального источника и соответствовать платформе устройства."));
        }

        var referencedButMissing = rawPrograms
            .SelectMany(p => p.Programs)
            .Where(p => !string.IsNullOrWhiteSpace(p.FileName))
            .Select(p => p.FileName!)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Where(f => !files.Any(file => file.FileName.Equals(f, StringComparison.OrdinalIgnoreCase)))
            .ToArray();

        if (referencedButMissing.Length > 0)
        {
            warnings.Add($"Файлы из rawprogram отсутствуют в каталоге ({referencedButMissing.Length}): {string.Join(", ", referencedButMissing.Take(10))}");
        }

        _log.Info("Qualcomm", $"Проанализирован пакет: файлов {files.Count}, rawprogram {rawPrograms.Count}.");

        return new QualcommPackageAnalysis
        {
            Directory = directory,
            Files = files.OrderBy(f => f.Kind).ThenBy(f => f.FileName, StringComparer.OrdinalIgnoreCase).ToArray(),
            RawPrograms = rawPrograms,
            Checks = checks,
            Warnings = warnings
        };
    }

    public string BuildServiceReport(QualcommPackageAnalysis analysis, DeviceInfo? device)
    {
        var builder = new System.Text.StringBuilder();
        builder.AppendLine("# Qualcomm Service — отчёт перед сервисной операцией");
        builder.AppendLine();
        builder.AppendLine($"- Дата: {DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss zzz}");
        builder.AppendLine($"- Каталог пакета: `{analysis.Directory}`");
        builder.AppendLine($"- Устройство: {(device is null ? "не выбрано" : $"{device.DisplayName} [{device.ModeText}] · {device.MaskedSerial}")}");
        builder.AppendLine();
        builder.AppendLine("## Проверки");
        foreach (var check in analysis.Checks)
        {
            builder.AppendLine($"- **[{check.Severity}] {check.Check}:** {check.Message}");
        }

        if (analysis.Warnings.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine("## Предупреждения");
            foreach (var warning in analysis.Warnings)
            {
                builder.AppendLine($"- {warning}");
            }
        }

        builder.AppendLine();
        builder.AppendLine("## Файлы");
        builder.AppendLine();
        builder.AppendLine("| Файл | Тип | Размер | SHA-256 |");
        builder.AppendLine("|---|---|---|---|");
        foreach (var file in analysis.Files)
        {
            builder.AppendLine($"| {file.FileName} | {file.Kind} | {SizeFormatting.HumanReadable(file.SizeBytes)} | {file.Sha256 ?? "не вычислен"} |");
        }

        builder.AppendLine();
        builder.AppendLine("## Ограничения");
        builder.AppendLine("- Протокол Firehose/EDL в приложении не реализован.");
        builder.AppendLine("- Programmer-файлы не проверяются на подлинность: используйте только официальные источники.");
        builder.AppendLine("- Запись выполняется только авторизованным внешним инструментом с соответствующим разрешением.");
        return builder.ToString();
    }
}
