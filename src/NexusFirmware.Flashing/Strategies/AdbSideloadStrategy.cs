using NexusFirmware.Core.Jobs;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.Flashing.Strategies;

/// <summary>Установка OTA-пакета через adb sideload (разрешённый штатный механизм Android).</summary>
public sealed class AdbSideloadStrategy : IFlashStrategy
{
    public string Id => "adb-sideload";

    public string Name => "ADB Sideload — установка OTA";

    public bool CanHandle(DeviceInfo device, FirmwarePackage package)
    {
        if (device.Mode is not (DeviceMode.Sideload or DeviceMode.Adb))
        {
            return false;
        }

        return package.Format is FirmwareFormat.Zip or FirmwareFormat.PayloadBin;
    }

    public Task<FlashPlan> BuildPlanAsync(FlashPlanContext context, CancellationToken cancellationToken = default)
    {
        var checks = StrategySupport.BaseChecks(context, requiresFastboot: false, requiresAdb: true).ToList();
        var warnings = new List<string>
        {
            "Sideload требует подписанный производителем OTA-пакет. Неподписанный пакет будет отклонён устройством."
        };

        if (string.IsNullOrWhiteSpace(context.Package.FilePath) || !File.Exists(context.Package.FilePath))
        {
            checks.Add(new CompatibilityItem("Пакет", CompatibilitySeverity.Blocking, "Файл пакета недоступен."));
        }

        if (context.Package.Integrity != IntegrityState.Verified)
        {
            warnings.Add("SHA-256 пакета не подтверждён — проверьте файл перед установкой.");
        }

        var dryRun = context.Options.DryRun;
        var steps = new List<JobStepDefinition>();
        var operationSteps = new List<OperationStep>();

        void Add(OperationStep info, Func<JobContext, CancellationToken, Task> execute)
        {
            operationSteps.Add(info);
            steps.Add(new JobStepDefinition
            {
                Info = info,
                IsCancellable = info.Risk == OperationRisk.Informational,
                Execute = async (job, ct) =>
                {
                    if (dryRun)
                    {
                        job.Log($"[Dry Run] {info.Title}: {info.Detail}");
                        return;
                    }

                    await execute(job, ct).ConfigureAwait(false);
                }
            });
        }

        Add(StrategySupport.Informational("Проверка целостности", "SHA-256 пакета OTA."), (job, ct) =>
        {
            job.Log("Проверка SHA-256 запланирована в общем журнале операции.");
            return Task.CompletedTask;
        });

        if (context.Device.Mode == DeviceMode.Adb)
        {
            Add(StrategySupport.DeviceChange("Перевод в режим sideload", "adb reboot sideload", "adb reboot sideload"), async (job, ct) =>
            {
                var result = await context.Adb.RebootAsync(context.Device.Serial!, DeviceDetection.Services.AdbRebootTarget.Sideload, ct).ConfigureAwait(false);
                if (!result.Started)
                {
                    throw new InvalidOperationException("adb не запустился: " + result.StartError);
                }

                job.Log("Устройство перезагружается в режим sideload. Ожидание 15 секунд…");
                await Task.Delay(TimeSpan.FromSeconds(15), ct).ConfigureAwait(false);
            });
        }

        Add(StrategySupport.DeviceChange("Установка пакета", "adb sideload <пакет>", "adb sideload"), async (job, ct) =>
        {
            job.Log("Запуск sideload. Прогресс отображается в журнале устройства.");
            var result = await context.Adb.SideloadAsync(context.Device.Serial!, context.Package.FilePath!, ct).ConfigureAwait(false);

            if (result.TimedOut)
            {
                throw new TimeoutException("Sideload прерван по тайм-ауту.");
            }

            if (!result.Succeeded)
            {
                throw new InvalidOperationException("Sideload завершился ошибкой: " + result.CombinedOutput.Trim());
            }

            job.Log("Sideload завершён. Проверьте экран устройства.");
        });

        Add(StrategySupport.Informational("Ожидание завершения", "Устройство может выполнять установку несколько минут."), (job, ct) =>
        {
            job.Log("После установки устройство перезагрузится автоматически. Не отключайте кабель.");
            return Task.CompletedTask;
        });

        var title = dryRun ? "Dry Run — план ADB Sideload" : "Установка OTA через ADB Sideload";
        var plan = new OperationPlan
        {
            Title = title,
            DeviceSummary = StrategySupport.DeviceSummary(context.Device),
            FirmwareSummary = $"{context.Package.DisplayName} ({context.Package.FormatText}, {context.Package.SizeText})",
            Steps = operationSteps,
            Checks = checks,
            Warnings = warnings,
            IsDryRun = dryRun
        };

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
                IsDryRun = dryRun,
                Steps = steps
            }
        });
    }
}
