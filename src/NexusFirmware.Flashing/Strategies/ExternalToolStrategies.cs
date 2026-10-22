using NexusFirmware.Core.Jobs;
using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Detection;
using NexusFirmware.Firmware.Samsung;

namespace NexusFirmware.Flashing.Strategies;

/// <summary>
/// Базовый класс для режимов, где протокол прошивки закрыт и не реализован.
/// План честно помечается как заблокированный, а шаги описывают подготовку пакета
/// и передачу операции официальному/разрешённому инструменту.
/// </summary>
public abstract class ExternalToolStrategyBase : IFlashStrategy
{
    public abstract string Id { get; }

    public abstract string Name { get; }

    protected abstract string ProtocolName { get; }

    protected abstract string RequiredTool { get; }

    protected abstract string BlockingReason { get; }

    public abstract bool CanHandle(DeviceInfo device, FirmwarePackage package);

    protected virtual IReadOnlyList<string> ExtraWarnings(FirmwarePackage package) => Array.Empty<string>();

    public Task<FlashPlan> BuildPlanAsync(FlashPlanContext context, CancellationToken cancellationToken = default)
    {
        var checks = StrategySupport.BaseChecks(context, requiresFastboot: false, requiresAdb: false).ToList();
        checks.Add(new CompatibilityItem(ProtocolName, CompatibilitySeverity.Blocking, BlockingReason));

        var warnings = new List<string>(ExtraWarnings(context.Package))
        {
            $"Протокол {ProtocolName} не реализован в NEXUS Firmware Studio. План описывает только подготовку и проверки.",
            $"Выполнение выполняется внешним официальным инструментом: {RequiredTool}.",
            "Приложение не обходит проверки подписи, SLA/DAA и другие механизмы защиты производителя."
        };

        var steps = new List<OperationStep>
        {
            new() { Title = "Проверка целостности пакета", Detail = "SHA-256 компонентов и соответствие комплекта.", Risk = OperationRisk.Informational },
            new() { Title = "Проверка состава пакета", Detail = "Наличие обязательных компонентов и совпадение кода модели.", Risk = OperationRisk.Informational },
            new() { Title = "Подготовка пакета", Detail = "Файлы подготавливаются для передачи внешнему инструменту. Запись не выполняется.", Risk = OperationRisk.Informational },
            new() { Title = "Передача операции внешнему инструменту", Detail = $"Запуск выполняет пользователь в {RequiredTool}.", Risk = OperationRisk.Informational },
            new() { Title = "Фиксация результата", Detail = "Отчёт сохраняется в журнале NEXUS.", Risk = OperationRisk.Informational }
        };

        var title = $"Подготовка операции ({ProtocolName}) — выполнение внешним инструментом";
        var plan = new OperationPlan
        {
            Title = title,
            DeviceSummary = StrategySupport.DeviceSummary(context.Device),
            FirmwareSummary = $"{context.Package.DisplayName} ({context.Package.FormatText}, {context.Package.SizeText})",
            Steps = steps,
            Checks = checks,
            Warnings = warnings,
            IsDryRun = context.Options.DryRun
        };

        var jobSteps = steps.Select(s => new JobStepDefinition
        {
            Info = s,
            IsCancellable = true,
            Execute = (job, _) =>
            {
                job.Log($"[Подготовка] {s.Title}: {s.Detail}");
                return Task.CompletedTask;
            }
        }).ToArray();

        return Task.FromResult(new FlashPlan
        {
            StrategyId = Id,
            StrategyName = Name,
            Plan = plan,
            Job = new JobRequest
            {
                Title = title,
                DeviceSummary = plan.DeviceSummary,
                FirmwareSummary = plan.FirmwareSummary,
                IsDryRun = true,
                AllowCancellation = true,
                Steps = jobSteps
            }
        });
    }
}

/// <summary>Samsung Download mode (Odin-совместимый протокол). В приложении не реализован.</summary>
public sealed class SamsungExternalToolStrategy : ExternalToolStrategyBase
{
    public override string Id => "samsung-external";

    public override string Name => "Samsung — подготовка пакета (внешний инструмент)";

    protected override string ProtocolName => "Odin / Download mode";

    protected override string RequiredTool => "официальный инструмент Samsung (Odin/Smart Switch)";

    protected override string BlockingReason =>
        "Протокол Download mode не реализован. Пакеты AP/BL/CP/CSC можно проверить и подготовить, но не прошить из приложения.";

    public override bool CanHandle(DeviceInfo device, FirmwarePackage package)
    {
        var isSamsung = device.Manufacturer?.Contains("Samsung", StringComparison.OrdinalIgnoreCase) == true ||
                        package.Manufacturer?.Contains("Samsung", StringComparison.OrdinalIgnoreCase) == true;

        return device.Mode == DeviceMode.Download || (isSamsung && package.Format is FirmwareFormat.TarMd5 or FirmwareFormat.SamsungAp or FirmwareFormat.SamsungBl or FirmwareFormat.SamsungCp or FirmwareFormat.SamsungCsc or FirmwareFormat.SamsungHomeCsc);
    }

    protected override IReadOnlyList<string> ExtraWarnings(FirmwarePackage package)
    {
        if (string.IsNullOrWhiteSpace(package.FilePath) || !File.Exists(package.FilePath))
        {
            return ["Файл пакета недоступен."];
        }

        var analysis = SamsungPackageAnalyzer.AnalyzeFile(package.FilePath);
        var warnings = new List<string>();
        if (analysis.BootloaderBinary is not null)
        {
            warnings.Add($"Ревизия загрузчика в имени пакета (предположительно): {analysis.BootloaderBinary}. Понижение ревизии заблокировано производителем.");
        }

        warnings.AddRange(analysis.Warnings);
        return warnings;
    }
}

/// <summary>MediaTek (SP Flash Tool / BROM-протокол). В приложении не реализован.</summary>
public sealed class MediaTekExternalToolStrategy : ExternalToolStrategyBase
{
    public override string Id => "mtk-external";

    public override string Name => "MediaTek — подготовка пакета (внешний инструмент)";

    protected override string ProtocolName => "MediaTek BROM/Preloader";

    protected override string RequiredTool => "официальный SP Flash Tool с авторизованным доступом";

    protected override string BlockingReason =>
        "Протокол BROM и обход SLA/DAA не реализованы. Scatter-файл и образы можно проверить, но не прошить из приложения.";

    public override bool CanHandle(DeviceInfo device, FirmwarePackage package)
    {
        return device.Mode is DeviceMode.MediaTekBootrom or DeviceMode.MediaTekPreloader ||
               package.Format == FirmwareFormat.Scatter;
    }
}

/// <summary>Qualcomm EDL (Firehose). В приложении не реализован.</summary>
public sealed class QualcommEdlExternalToolStrategy : ExternalToolStrategyBase
{
    public override string Id => "qualcomm-external";

    public override string Name => "Qualcomm EDL — подготовка пакета (внешний инструмент)";

    protected override string ProtocolName => "Qualcomm EDL / Firehose";

    protected override string RequiredTool => "официальный/авторизованный инструмент Qualcomm (Firehose-программатор)";

    protected override string BlockingReason =>
        "Протокол Firehose не реализован. rawprogram XML и programmer-файлы можно проверить, но не использовать для записи.";

    public override bool CanHandle(DeviceInfo device, FirmwarePackage package)
    {
        return device.Mode == DeviceMode.QualcommEdl || package.Format == FirmwareFormat.RawProgramXml;
    }
}
