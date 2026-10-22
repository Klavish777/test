using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Scatter;

namespace NexusFirmware.MediaTek;

public sealed class MtkPackageAnalysis
{
    public required string Directory { get; init; }
    public ScatterFile? Scatter { get; init; }
    public IReadOnlyList<ScatterFileCheck> FileChecks { get; init; } = Array.Empty<ScatterFileCheck>();
    public IReadOnlyList<CompatibilityItem> Checks { get; init; } = Array.Empty<CompatibilityItem>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> ImageFiles { get; init; } = Array.Empty<string>();

    public long TotalImageBytes { get; init; }

    public bool CanPlanFlashing => Scatter is not null && Checks.All(c => c.Severity != CompatibilitySeverity.Blocking);
}

/// <summary>
/// Сервис MediaTek: анализ scatter-пакетов, диагностика режимов Preloader/BootROM, проверка
/// соответствия файлов. Обход Secure Boot, SLA и DAA не выполняется и не планируется.
/// </summary>
public sealed class MediaTekService
{
    private readonly ILogBus _log;

    public MediaTekService(ILogBus log)
    {
        _log = log;
    }

    public IReadOnlyList<DeviceInfo> FindMediaTekDevices(IEnumerable<DeviceInfo> devices) =>
        devices.Where(d =>
            d.Mode is DeviceMode.MediaTekBootrom or DeviceMode.MediaTekPreloader ||
            (d.VendorId?.Equals("0E8D", StringComparison.OrdinalIgnoreCase) ?? false)).ToArray();

    /// <summary>Признаки необходимости авторизации для текущего режима (не выполняет никаких действий).</summary>
    public IReadOnlyList<string> DescribeAuthorizationRequirements(DeviceInfo? device)
    {
        var list = new List<string>
        {
            "Операции записи в BROM требуют совместимого DA-файла (Download Agent) из официального источника.",
            "Устройства с включённой защитой SLA/DAA требуют авторизации производителя: приложение такие проверки не обходит."
        };

        if (device?.Mode == DeviceMode.MediaTekBootrom)
        {
            list.Add("Устройство сообщает режим BootROM: типично для аварийного восстановления, требует особой осторожности.");
        }
        else if (device?.Mode == DeviceMode.MediaTekPreloader)
        {
            list.Add("Устройство в режиме Preloader: доступны только операции, разрешённые текущей политикой безопасности чипа.");
        }

        return list;
    }

    public async Task<MtkPackageAnalysis> AnalyzePackageAsync(
        string directory,
        bool computeHashes = false,
        CancellationToken cancellationToken = default)
    {
        if (!PathSafety.IsExistingDirectory(directory))
        {
            throw new DirectoryNotFoundException(directory);
        }

        var checks = new List<CompatibilityItem>();
        var warnings = new List<string>();

        var scatterPath = Directory.EnumerateFiles(directory, "*scatter*.txt", SearchOption.TopDirectoryOnly)
            .Concat(Directory.EnumerateFiles(directory, "MT*.txt", SearchOption.TopDirectoryOnly))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();

        ScatterFile? scatter = null;
        if (scatterPath is null)
        {
            checks.Add(new CompatibilityItem("Scatter", CompatibilitySeverity.Blocking,
                "Scatter-файл не найден. Пакет нельзя сопоставить с таблицей разделов."));
        }
        else
        {
            scatter = ScatterParser.Parse(scatterPath);
            checks.Add(new CompatibilityItem("Scatter", CompatibilitySeverity.Info,
                $"Scatter прочитан: платформа {scatter.Platform ?? "не указана"}, разделов {scatter.Partitions.Count}."));
            warnings.AddRange(scatter.Warnings);

            if (scatter.Partitions.Count > 0)
            {
                var withFiles = scatter.Partitions.Count(p => !string.IsNullOrWhiteSpace(p.FileName));
                checks.Add(new CompatibilityItem("Файлы разделов", CompatibilitySeverity.Info,
                    $"Разделов с файлами: {withFiles} из {scatter.Partitions.Count}."));
            }
        }

        var fileChecks = scatter is null
            ? Array.Empty<ScatterFileCheck>()
            : ScatterParser.VerifyFiles(scatter, directory);

        var missing = fileChecks.Where(c => !c.FileExists).ToArray();
        if (missing.Length > 0)
        {
            checks.Add(new CompatibilityItem("Файлы образов", CompatibilitySeverity.Warning,
                $"Отсутствуют файлы для {missing.Length} разделов: {string.Join(", ", missing.Take(8).Select(m => m.FileName))}"));
        }

        var images = Directory.EnumerateFiles(directory, "*.img", SearchOption.TopDirectoryOnly)
            .Concat(Directory.EnumerateFiles(directory, "*.bin", SearchOption.TopDirectoryOnly))
            .ToArray();

        long total = 0;
        foreach (var image in images)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var info = new FileInfo(image);
            total += info.Length;

            if (computeHashes)
            {
                await Hashing.Sha256FileAsync(image, null, cancellationToken).ConfigureAwait(false);
            }
        }

        if (scatter?.Storage is not null)
        {
            checks.Add(new CompatibilityItem("Носитель", CompatibilitySeverity.Info,
                $"Тип носителя по scatter: {scatter.Storage}."));
        }

        warnings.Add("Запись через BROM/Preloader в приложении не реализована. План носит подготовительный характер.");

        _log.Info("MediaTek", $"Проанализирован пакет: образов {images.Length}, scatter: {(scatter is null ? "нет" : "есть")}.");

        return new MtkPackageAnalysis
        {
            Directory = directory,
            Scatter = scatter,
            FileChecks = fileChecks,
            Checks = checks,
            Warnings = warnings,
            ImageFiles = images.Select(Path.GetFileName).Where(n => n is not null).Select(n => n!).ToArray(),
            TotalImageBytes = total
        };
    }

    /// <summary>Подробный план подготовки (без выполнения записи).</summary>
    public IReadOnlyList<OperationStep> BuildPreparationPlan(MtkPackageAnalysis analysis)
    {
        var steps = new List<OperationStep>
        {
            new() { Title = "Проверка scatter-файла", Detail = "Сопоставление разделов и файлов, контроль размеров.", Risk = OperationRisk.Informational },
            new() { Title = "Проверка образов", Detail = "Наличие файлов и SHA-256 (по запросу).", Risk = OperationRisk.Informational },
            new() { Title = "Проверка авторизации", Detail = "SLA/DAA: при необходимости требуется официальный доступ.", Risk = OperationRisk.Informational },
            new() { Title = "Передача пакета внешнему инструменту", Detail = "SP Flash Tool запускается пользователем вручную.", Risk = OperationRisk.Informational }
        };

        if (analysis.Scatter is not null)
        {
            steps.Add(new OperationStep
            {
                Title = "Разделы, которые будут записаны (внешним инструментом)",
                Detail = string.Join(", ", analysis.Scatter.Partitions.Where(p => !string.IsNullOrWhiteSpace(p.FileName)).Take(20).Select(p => p.PartitionName)),
                Risk = OperationRisk.Informational
            });
        }

        return steps;
    }

    public string BuildReport(MtkPackageAnalysis analysis, DeviceInfo? device)
    {
        var sb = new System.Text.StringBuilder();
        sb.AppendLine("# MediaTek Service — отчёт подготовки");
        sb.AppendLine();
        sb.AppendLine($"- Дата: {DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss zzz}");
        sb.AppendLine($"- Каталог: `{analysis.Directory}`");
        sb.AppendLine($"- Устройство: {(device is null ? "не выбрано" : $"{device.DisplayName} [{device.ModeText}]")}");
        sb.AppendLine($"- Платформа (scatter): {analysis.Scatter?.Platform ?? "не указана"}");
        sb.AppendLine();
        sb.AppendLine("## Проверки");
        foreach (var check in analysis.Checks)
        {
            sb.AppendLine($"- **[{check.Severity}] {check.Check}:** {check.Message}");
        }

        sb.AppendLine();
        sb.AppendLine("## Разделы scatter");
        sb.AppendLine();
        sb.AppendLine("| # | Раздел | Файл | Размер | Файл найден |");
        sb.AppendLine("|---|---|---|---|---|");
        foreach (var partition in analysis.Scatter?.Partitions ?? Array.Empty<ScatterEntry>())
        {
            var check = analysis.FileChecks.FirstOrDefault(c => c.PartitionName == partition.PartitionName);
            sb.AppendLine($"| {partition.Index} | {partition.PartitionName} | {partition.FileName ?? "—"} | {SizeFormatting.HumanReadable(partition.PartitionSize ?? 0)} | {(check is null ? "—" : check.FileExists ? "да" : "нет")} |");
        }

        sb.AppendLine();
        sb.AppendLine("## Ограничения");
        sb.AppendLine("- Протокол BROM/Preloader не реализован.");
        sb.AppendLine("- Обход Secure Boot, SLA и DAA не выполняется.");
        sb.AppendLine("- Запись выполняется только официальным инструментом с авторизацией.");
        return sb.ToString();
    }
}
