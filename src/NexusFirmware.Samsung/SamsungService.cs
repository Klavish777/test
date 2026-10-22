using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Samsung;

namespace NexusFirmware.Samsung;

public sealed class SamsungPackageResult
{
    public required SamsungPackageAnalysis Analysis { get; init; }
    public IReadOnlyList<string> RequiredComponents { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> MissingComponents { get; init; } = Array.Empty<string>();
    public IReadOnlyList<CompatibilityItem> DeviceChecks { get; init; } = Array.Empty<CompatibilityItem>();
    public IReadOnlyList<string> Notes { get; init; } = Array.Empty<string>();
}

/// <summary>
/// Сервис Samsung: анализ пакетов AP/BL/CP/CSC/HOME_CSC, проверка совместимости, подготовка
/// отчёта для официального инструмента прошивки. Протокол Download mode не реализован.
/// </summary>
public sealed class SamsungService
{
    private static readonly string[] Required = ["AP", "BL", "CP", "CSC"];

    private readonly ILogBus _log;

    public SamsungService(ILogBus log)
    {
        _log = log;
    }

    public IReadOnlyList<DeviceInfo> FindDownloadModeDevices(IEnumerable<DeviceInfo> devices) =>
        devices.Where(d => d.Mode == DeviceMode.Download ||
                           (d.VendorId?.Equals("04E8", StringComparison.OrdinalIgnoreCase) == true &&
                            d.DriverName?.Contains("Download", StringComparison.OrdinalIgnoreCase) == true)).ToArray();

    public async Task<SamsungPackageResult> AnalyzePackageAsync(
        IReadOnlyList<string> filePaths,
        DeviceInfo? device = null,
        IProgress<(double Percent, string Message)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (filePaths.Count == 0)
        {
            throw new ArgumentException("Не передано ни одного файла пакета.", nameof(filePaths));
        }

        var components = new List<SamsungComponentInfo>();
        for (var i = 0; i < filePaths.Count; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            progress?.Report(((double)i / filePaths.Count * 100, $"Анализ {Path.GetFileName(filePaths[i])}…"));
            components.Add(await SamsungPackageAnalyzer.AnalyzeFileWithHashAsync(filePaths[i], cancellationToken).ConfigureAwait(false));
        }

        progress?.Report((90, "Проверка совместимости…"));
        var analysis = SamsungPackageAnalyzer.AnalyzePackage(components);

        var present = components.Select(c => c.Component).Where(c => c is not null).Select(c => c!).Distinct().ToArray();
        var missing = Required.Where(r => !present.Contains(r)).ToArray();

        var deviceChecks = new List<CompatibilityItem>();
        if (device is not null)
        {
            var packageModel = analysis.ModelCode;
            if (packageModel is not null && device.Model is not null)
            {
                var matches = device.Model.Replace("-", "").Contains(packageModel.Replace("-", ""), StringComparison.OrdinalIgnoreCase) ||
                              packageModel.Replace("-", "").Contains(device.Model.Replace("-", ""), StringComparison.OrdinalIgnoreCase);
                deviceChecks.Add(new CompatibilityItem("Модель устройства", matches ? CompatibilitySeverity.Info : CompatibilitySeverity.Blocking,
                    matches
                        ? $"Пакет подходит к модели {device.Model} (по коду {packageModel})."
                        : $"Пакет для {packageModel}, устройство {device.Model}."));
            }
            else
            {
                deviceChecks.Add(new CompatibilityItem("Модель устройства", CompatibilitySeverity.Warning,
                    "Не удалось сравнить модель устройства и пакета."));
            }

            var deviceBinary = ExtractBinaryRevision(device.BootloaderVersion);
            var packageBinary = components.Select(c => c.BootloaderBinary).FirstOrDefault(b => !string.IsNullOrWhiteSpace(b));

            if (deviceBinary is not null && packageBinary is not null &&
                int.TryParse(deviceBinary, out var dBin) && int.TryParse(packageBinary, out var pBin))
            {
                if (pBin < dBin)
                {
                    deviceChecks.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Blocking,
                        $"Ревизия пакета {pBin} ниже ревизии устройства {dBin}: понижение версии заблокировано загрузчиком Samsung."));
                }
                else
                {
                    deviceChecks.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Info,
                        $"Ревизия пакета {pBin}, устройства {dBin}: понижение не требуется."));
                }
            }
            else
            {
                deviceChecks.Add(new CompatibilityItem("Anti-rollback", CompatibilitySeverity.Warning,
                    "Ревизия загрузчика устройства или пакета не определена — проверьте вручную перед прошивкой."));
            }

            var dataLoss = components.Any(c => c.Component == "CSC");
            deviceChecks.Add(new CompatibilityItem("Пользовательские данные",
                dataLoss ? CompatibilitySeverity.Warning : CompatibilitySeverity.Info,
                dataLoss
                    ? "В пакете CSC (не HOME_CSC): при прошивке данные пользователя будут удалены."
                    : "HOME_CSC или CSC отсутствует: сброс данных не обязателен, уточните в инструменте прошивки."));
        }

        var notes = new List<string>(analysis.Notes)
        {
            "Протокол Download mode (Odin) не реализован в NEXUS Firmware Studio.",
            "Прошивка выполняется официальным инструментом Samsung; приложение готовит проверенный пакет и отчёт."
        };

        _log.Info("Samsung", $"Проанализирован пакет из {filePaths.Count} файл(ов); модель: {analysis.ModelCode ?? "не определена"}.");
        progress?.Report((100, "Анализ завершён"));

        return new SamsungPackageResult
        {
            Analysis = analysis,
            RequiredComponents = Required,
            MissingComponents = missing,
            DeviceChecks = deviceChecks,
            Notes = notes
        };
    }

    /// <summary>Порядок передачи компонентов внешнему инструменту (не выполняется приложением).</summary>
    public IReadOnlyList<(string Slot, string FileName, string Size, string Sha256)> BuildExternalToolLayout(SamsungPackageResult result)
    {
        var order = new[] { "BL", "AP", "CP", "CSC", "HOME_CSC" };
        return result.Analysis.Components
            .OrderBy(c => Array.IndexOf(order, c.Component) is var index && index >= 0 ? index : order.Length)
            .Select(c => (
                Slot: c.Component ?? "?",
                FileName: c.FileName,
                Size: SizeFormatting.HumanReadable(c.SizeBytes),
                Sha256: c.Sha256 ?? "не вычислен"))
            .ToArray();
    }

    public string BuildReport(SamsungPackageResult result, DeviceInfo? device)
    {
        var sb = new System.Text.StringBuilder();
        sb.AppendLine("# Samsung Service — отчёт по пакету");
        sb.AppendLine();
        sb.AppendLine($"- Дата: {DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss zzz}");
        sb.AppendLine($"- Устройство: {(device is null ? "не выбрано" : $"{device.DisplayName} [{device.ModeText}] · {device.MaskedSerial}")}");
        sb.AppendLine($"- Код модели пакета: {result.Analysis.ModelCode ?? "не определён"}");
        sb.AppendLine($"- Версия (PDA): {result.Analysis.CombinedVersion ?? "не определена"}");
        sb.AppendLine();
        sb.AppendLine("## Компоненты");
        sb.AppendLine();
        sb.AppendLine("| Слот | Файл | Размер | Ревизия загрузчика | SHA-256 |");
        sb.AppendLine("|---|---|---|---|---|");
        foreach (var component in result.Analysis.Components)
        {
            sb.AppendLine($"| {component.Component ?? "?"} | {component.FileName} | {SizeFormatting.HumanReadable(component.SizeBytes)} | {component.BootloaderBinary ?? "—"} | {component.Sha256 ?? "не вычислен"} |");
        }

        sb.AppendLine();
        sb.AppendLine("## Проверки пакета");
        foreach (var check in result.Analysis.Checks)
        {
            sb.AppendLine($"- **[{check.Severity}] {check.Check}:** {check.Message}");
        }

        if (result.DeviceChecks.Count > 0)
        {
            sb.AppendLine();
            sb.AppendLine("## Проверки относительно устройства");
            foreach (var check in result.DeviceChecks)
            {
                sb.AppendLine($"- **[{check.Severity}] {check.Check}:** {check.Message}");
            }
        }

        if (result.MissingComponents.Count > 0)
        {
            sb.AppendLine();
            sb.AppendLine($"**Отсутствуют компоненты:** {string.Join(", ", result.MissingComponents)}");
        }

        sb.AppendLine();
        sb.AppendLine("## Ограничения");
        foreach (var note in result.Notes)
        {
            sb.AppendLine($"- {note}");
        }

        return sb.ToString();
    }

    /// <summary>Ревизия загрузчика из строки версии загрузчика Samsung (эвристика, помечается как предположение).</summary>
    public static string? ExtractBinaryRevision(string? bootloaderVersion)
    {
        if (string.IsNullOrWhiteSpace(bootloaderVersion))
        {
            return null;
        }

        return SamsungPackageAnalyzer.ExtractBinaryRevision(bootloaderVersion.Trim());
    }
}
