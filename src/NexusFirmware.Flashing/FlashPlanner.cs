using NexusFirmware.Core.Models;
using NexusFirmware.Flashing.Strategies;

namespace NexusFirmware.Flashing;

/// <summary>
/// Выбор стратегии прошивки и построение плана. Ни одна стратегия не выполняется здесь:
/// результат — только план и (для Dry Run) информационные шаги.
/// </summary>
public sealed class FlashPlanner
{
    private readonly IReadOnlyList<IFlashStrategy> _strategies;

    public FlashPlanner(IEnumerable<IFlashStrategy>? strategies = null)
    {
        _strategies = (strategies ?? new IFlashStrategy[]
        {
            new FastbootImageStrategy(),
            new AdbSideloadStrategy(),
            new SamsungExternalToolStrategy(),
            new MediaTekExternalToolStrategy(),
            new QualcommEdlExternalToolStrategy()
        }).ToArray();
    }

    public IReadOnlyList<IFlashStrategy> Strategies => _strategies;

    public async Task<FlashPlan> BuildPlanAsync(FlashPlanContext context, CancellationToken cancellationToken = default)
    {
        var strategy = _strategies.FirstOrDefault(s => s.CanHandle(context.Device, context.Package))
                       ?? _strategies.OfType<UnsupportedStrategy>().FirstOrDefault();

        if (strategy is null)
        {
            var checks = new List<CompatibilityItem>
            {
                new("Стратегия", CompatibilitySeverity.Blocking,
                    "Для выбранного режима устройства и формата прошивки нет реализованной стратегии. Возможности ограничены честно.")
            };

            var emptyPlan = new OperationPlan
            {
                Title = "Прошивка невозможна",
                DeviceSummary = context.Device.DisplayName,
                FirmwareSummary = context.Package.DisplayName,
                Steps = Array.Empty<OperationStep>(),
                Checks = checks,
                Warnings = ["Операция не будет выполнена."],
                IsDryRun = context.Options.DryRun
            };

            return new FlashPlan
            {
                StrategyId = "none",
                StrategyName = "Не реализовано",
                Plan = emptyPlan,
                Job = new JobRequest { Title = emptyPlan.Title, Steps = Array.Empty<JobStepDefinition>() }
            };
        }

        return await strategy.BuildPlanAsync(context, cancellationToken).ConfigureAwait(false);
    }
}

/// <summary>Стратегия-заглушка для случаев, когда ни один модуль не подходит.</summary>
public sealed class UnsupportedStrategy : IFlashStrategy
{
    public string Id => "unsupported";

    public string Name => "Неподдерживаемая комбинация";

    public bool CanHandle(DeviceInfo device, FirmwarePackage package) => false;

    public Task<FlashPlan> BuildPlanAsync(FlashPlanContext context, CancellationToken cancellationToken = default) =>
        throw new NotSupportedException("Стратегия не реализована.");
}
