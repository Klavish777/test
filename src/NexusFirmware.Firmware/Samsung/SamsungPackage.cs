using System.Text.RegularExpressions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Detection;

namespace NexusFirmware.Firmware.Samsung;

/// <summary>
/// Анализ компонентов Samsung (AP/BL/CP/CSC/HOME_CSC). Формат имени разбирается по официальной
/// схеме «КОМПОНЕНТ_МОДЕЛЬ..._CL...», но трактуется как справочная информация:
/// точная совместимость подтверждается только на устройстве.
/// </summary>
public sealed class SamsungComponentInfo
{
    public required string FilePath { get; init; }
    public required string FileName { get; init; }
    public FirmwareFormat Format { get; init; }
    public string? Component { get; init; }
    public string? ModelCode { get; init; }
    public string? PdaVersion { get; init; }
    public string? CscVersion { get; init; }
    public string? BuildNumber { get; init; }
    public string? BootloaderBinary { get; init; }
    public long SizeBytes { get; init; }
    public string? Sha256 { get; init; }
    public IReadOnlyList<string> Entries { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
    public bool IsArchive { get; init; }
}

public sealed class SamsungPackageAnalysis
{
    public required IReadOnlyList<SamsungComponentInfo> Components { get; init; }
    public required IReadOnlyList<CompatibilityItem> Checks { get; init; }
    public IReadOnlyList<string> Notes { get; init; } = Array.Empty<string>();

    public bool IsComplete => Components.Any(c => c.Component == "AP") && Components.Any(c => c.Component == "BL");

    public bool HasBlockingIssues => Checks.Any(c => c.Severity == CompatibilitySeverity.Blocking);

    public string? ModelCode => Components.Select(c => c.ModelCode).FirstOrDefault(m => !string.IsNullOrWhiteSpace(m));

    public string? CombinedVersion => Components.Select(c => c.PdaVersion).FirstOrDefault(v => !string.IsNullOrWhiteSpace(v));
}

public static class SamsungPackageAnalyzer
{
    private static readonly Regex ComponentRegex = new(
        "^(?<component>HOME_CSC|AP|BL|CP|CSC)_(?<rest>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    private static readonly Regex PdaRegex = new(
        "^(?<pda>[A-Z0-9]{8,20})_CL(?<build>\\d+)_QB(?<qb>\\d+)",
        RegexOptions.CultureInvariant);

    // Коды моделей Samsung: SM-G973F, G973F, SM-A505FN, A505F, SM-N986B и т.п.
    private static readonly Regex ModelRegex = new("^(?<model>(?:SM-)?[A-Z]\\d{3,4}[A-Z0-9]?)", RegexOptions.CultureInvariant);

    public static SamsungComponentInfo AnalyzeFile(string path)
    {
        var fileName = Path.GetFileName(path);
        var info = new FileInfo(path);
        var format = FormatDetector.Detect(path);
        var match = ComponentRegex.Match(fileName);

        var component = match.Success ? match.Groups["component"].Value.ToUpperInvariant() : null;
        var warnings = new List<string>();
        var entries = new List<string>();

        string? modelCode = null;
        string? pdaVersion = null;
        string? buildNumber = null;
        string? cscVersion = null;
        string? bootloaderBinary = null;

        if (!match.Success)
        {
            warnings.Add("Имя файла не соответствует схеме Samsung (AP_/BL_/CP_/CSC_/HOME_CSC_).");
        }
        else
        {
            var rest = match.Groups["rest"].Value;

            if (component is "CSC" or "HOME_CSC")
            {
                // CSC_<CSC-код>_<PDA>_... или CSC_<PDA>_...
                var parts = rest.Split('_', StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length >= 2)
                {
                    cscVersion = parts[0];
                    pdaVersion = parts[1];
                }
                else if (parts.Length == 1)
                {
                    cscVersion = parts[0];
                }
            }
            else
            {
                var pdaMatch = PdaRegex.Match(rest);
                if (pdaMatch.Success)
                {
                    pdaVersion = pdaMatch.Groups["pda"].Value;
                    buildNumber = pdaMatch.Groups["build"].Value;
                }
                else
                {
                    var parts = rest.Split('_', StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length > 0)
                    {
                        pdaVersion = parts[0];
                    }
                }
            }

            var versionForModel = pdaVersion ?? rest;
            var modelMatch = ModelRegex.Match(versionForModel);
            if (modelMatch.Success)
            {
                modelCode = modelMatch.Groups["model"].Value;
            }
            else if (versionForModel.Length >= 4)
            {
                modelCode = versionForModel[..Math.Min(6, versionForModel.Length)];
            }

            if (pdaVersion is not null)
            {
                bootloaderBinary = ExtractBinaryRevision(pdaVersion);
            }
        }

        var isArchive = format is FirmwareFormat.Tar or FirmwareFormat.TarMd5 or FirmwareFormat.Zip;
        if (isArchive)
        {
            try
            {
                if (format == FirmwareFormat.Zip)
                {
                    using var archive = System.IO.Compression.ZipFile.OpenRead(path);
                    entries.AddRange(archive.Entries.Where(e => !string.IsNullOrEmpty(e.Name)).Select(e => e.FullName));
                }
                else
                {
                    var inspection = TarInspector.InspectFile(path);
                    entries.AddRange(inspection.Entries.Where(e => !e.IsDirectory).Select(e => e.FullName));
                    if (!inspection.SafeToExtract)
                    {
                        warnings.AddRange(inspection.BlockingIssues);
                    }
                }
            }
            catch (Exception ex) when (ex is IOException or InvalidDataException)
            {
                warnings.Add("Не удалось прочитать содержимое контейнера: " + ex.Message);
            }
        }

        return new SamsungComponentInfo
        {
            FilePath = path,
            FileName = fileName,
            Format = format,
            Component = component,
            ModelCode = modelCode,
            PdaVersion = pdaVersion,
            CscVersion = cscVersion,
            BuildNumber = buildNumber,
            BootloaderBinary = bootloaderBinary,
            SizeBytes = info.Length,
            Entries = entries,
            Warnings = warnings,
            IsArchive = isArchive,
            Sha256 = null
        };
    }

    public static async Task<SamsungComponentInfo> AnalyzeFileWithHashAsync(string path, CancellationToken cancellationToken = default)
    {
        var info = AnalyzeFile(path);
        var hash = await Hashing.Sha256FileAsync(path, null, cancellationToken).ConfigureAwait(false);
        return new SamsungComponentInfo
        {
            FilePath = info.FilePath,
            FileName = info.FileName,
            Format = info.Format,
            Component = info.Component,
            ModelCode = info.ModelCode,
            PdaVersion = info.PdaVersion,
            CscVersion = info.CscVersion,
            BuildNumber = info.BuildNumber,
            BootloaderBinary = info.BootloaderBinary,
            SizeBytes = info.SizeBytes,
            Entries = info.Entries,
            Warnings = info.Warnings,
            IsArchive = info.IsArchive,
            Sha256 = hash
        };
    }

    /// <summary>Проверка совместимости набора компонентов пакета между собой (не с устройством).</summary>
    public static SamsungPackageAnalysis AnalyzePackage(IReadOnlyList<SamsungComponentInfo> components)
    {
        var checks = new List<CompatibilityItem>();
        var notes = new List<string>();

        if (components.Count == 0)
        {
            checks.Add(new CompatibilityItem("Состав пакета", CompatibilitySeverity.Blocking, "Не добавлено ни одного файла."));
            return new SamsungPackageAnalysis { Components = components, Checks = checks, Notes = notes };
        }

        var missingNames = components.Where(c => string.IsNullOrWhiteSpace(c.Component)).ToArray();
        if (missingNames.Length > 0)
        {
            checks.Add(new CompatibilityItem("Имена компонентов", CompatibilitySeverity.Warning,
                $"{missingNames.Length} файл(ов) не распознаны как AP/BL/CP/CSC: {string.Join(", ", missingNames.Select(c => c.FileName))}"));
        }

        var models = components
            .Where(c => !string.IsNullOrWhiteSpace(c.ModelCode))
            .GroupBy(c => c.ModelCode!, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        if (models.Length > 1)
        {
            checks.Add(new CompatibilityItem("Модель", CompatibilitySeverity.Blocking,
                $"Компоненты относятся к разным моделям: {string.Join(", ", models.Select(g => g.Key))}."));
        }
        else if (models.Length == 1)
        {
            checks.Add(new CompatibilityItem("Модель", CompatibilitySeverity.Info,
                $"Все компоненты относятся к модели {models[0].Key} (определено по имени файла)."));
        }
        else
        {
            checks.Add(new CompatibilityItem("Модель", CompatibilitySeverity.Warning,
                "Не удалось определить модель по именам файлов."));
        }

        var duplicated = components
            .Where(c => !string.IsNullOrWhiteSpace(c.Component))
            .GroupBy(c => c.Component!)
            .Where(g => g.Count() > 1)
            .ToArray();

        if (duplicated.Length > 0)
        {
            checks.Add(new CompatibilityItem("Дубли компонентов", CompatibilitySeverity.Warning,
                $"Несколько файлов одного типа: {string.Join(", ", duplicated.Select(g => g.Key))}."));
        }

        var cscComponents = components.Where(c => c.Component is "CSC" or "HOME_CSC").ToArray();
        if (cscComponents.Length == 0)
        {
            checks.Add(new CompatibilityItem("CSC", CompatibilitySeverity.Warning,
                "CSC/HOME_CSC отсутствует: регион и настройки оператора не будут обновлены."));
        }
        else if (cscComponents.Any(c => c.Component == "CSC"))
        {
            notes.Add("Выбран CSC (не HOME_CSC): при прошивке выполняется сброс данных устройства. HOME_CSC сохраняет пользовательские данные.");
        }

        if (!components.Any(c => c.Component == "AP"))
        {
            checks.Add(new CompatibilityItem("AP", CompatibilitySeverity.Blocking,
                "Отсутствует AP — основной образ системы. Прошивка без AP невозможна."));
        }

        if (!components.Any(c => c.Component == "BL"))
        {
            checks.Add(new CompatibilityItem("BL", CompatibilitySeverity.Warning,
                "Отсутствует BL — загрузчик не будет обновлён."));
        }

        var binaries = components
            .Where(c => !string.IsNullOrWhiteSpace(c.BootloaderBinary))
            .Select(c => c.BootloaderBinary!)
            .Distinct()
            .ToArray();

        if (binaries.Length > 1)
        {
            checks.Add(new CompatibilityItem("Версия загрузчика", CompatibilitySeverity.Warning,
                $"Компоненты содержат разные ревизии загрузчика: {string.Join(", ", binaries)}. Проверьте комплект."));
        }

        foreach (var component in components)
        {
            foreach (var warning in component.Warnings)
            {
                checks.Add(new CompatibilityItem($"Файл {component.FileName}", CompatibilitySeverity.Warning, warning));
            }
        }

        if (components.Any(c => c.Entries.Count == 0 && c.IsArchive))
        {
            notes.Add("Контейнер TAR.MD5 может содержать вложенные образы, которые не перечислены: проверьте извлечение.");
        }

        return new SamsungPackageAnalysis { Components = components, Checks = checks, Notes = notes };
    }

    /// <summary>Ревизия загрузчика в PDA-версии (эвристика Samsung, обозначается как предположение).</summary>
    public static string? ExtractBinaryRevision(string pdaVersion)
    {
        var normalized = pdaVersion.Trim().ToUpperInvariant();
        if (normalized.StartsWith("SM-", StringComparison.Ordinal))
        {
            normalized = normalized[3..];
        }

        var match = Regex.Match(normalized, @"^[A-Z0-9]{4,8}([A-Z]{2})([A-Z])(\d)", RegexOptions.CultureInvariant);
        return match.Success ? match.Groups[3].Value : null;
    }
}
