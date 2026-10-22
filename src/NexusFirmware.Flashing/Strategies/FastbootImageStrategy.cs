using NexusFirmware.Core.Jobs;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Detection;

namespace NexusFirmware.Flashing.Strategies;

/// <summary>
/// Прошивка образов через fastboot. План всегда строится до выполнения; запись разделов
/// не начинается без явного подтверждения (AllowDeviceModification + отсутствие blocking-проверок).
/// </summary>
public sealed class FastbootImageStrategy : IFlashStrategy
{
    public string Id => "fastboot-images";

    public string Name => "Fastboot — запись образов";

    public bool CanHandle(DeviceInfo device, FirmwarePackage package)
    {
        if (device.Mode is not (DeviceMode.Fastboot or DeviceMode.Adb))
        {
            return false;
        }

        if (package.Format is not (FirmwareFormat.Zip or FirmwareFormat.Tar or FirmwareFormat.TarMd5 or
            FirmwareFormat.Image or FirmwareFormat.SparseImage))
        {
            return false;
        }

        return package.Format != FirmwareFormat.PayloadBin;
    }

    public Task<FlashPlan> BuildPlanAsync(FlashPlanContext context, CancellationToken cancellationToken = default)
    {
        var checks = StrategySupport.BaseChecks(context, requiresFastboot: true, requiresAdb: true);
        var warnings = new List<string>();
        var targets = new List<FlashTarget>();
        var archiveImageEntries = new List<string>();
        var workDirectory = Path.Combine(Path.GetTempPath(), "NexusFirmware", "flash_" + Guid.NewGuid().ToString("N"));

        var format = context.Package.Format;
        if (format is FirmwareFormat.Image or FirmwareFormat.SparseImage)
        {
            if (string.IsNullOrWhiteSpace(context.Package.FilePath) || !File.Exists(context.Package.FilePath))
            {
                checks.Add(new CompatibilityItem("Файл образа", CompatibilitySeverity.Blocking, "Файл образа недоступен."));
            }
            else if (TryResolveTarget(context, context.Package.FilePath, out var target, out var reason))
            {
                targets.Add(target!);
            }
            else
            {
                warnings.Add(reason ?? "Не удалось сопоставить образ с разделом.");
            }
        }
        else
        {
            var imageEntries = ListArchiveImages(context, checks, warnings);
            archiveImageEntries.AddRange(imageEntries);

            foreach (var entry in imageEntries)
            {
                if (TryResolveTarget(context, entry, out var target, out var reason))
                {
                    targets.Add(target!);
                }
                else
                {
                    warnings.Add(reason ?? $"Образ «{entry}» пропущен: раздел не определён.");
                }
            }
        }

        if (targets.Count == 0)
        {
            checks.Add(new CompatibilityItem("Образы", CompatibilitySeverity.Blocking,
                "Не найдено ни одного образа, который можно записать. Проверьте содержимое пакета."));
        }

        if (context.Device.BootloaderUnlocked is false)
        {
            checks.Add(new CompatibilityItem("Загрузчик", CompatibilitySeverity.Blocking,
                "Загрузчик заблокирован: fastboot flash недоступен."));
        }
        else if (context.Device.BootloaderUnlocked is null && !context.Options.AllowUnknownBootloader)
        {
            checks.Add(new CompatibilityItem("Загрузчик", CompatibilitySeverity.Blocking,
                "Состояние загрузчика не определено. Подтвердите риск или проверьте устройство в fastboot."));
        }

        var dryRun = context.Options.DryRun;
        var steps = new List<JobStepDefinition>();
        var operationSteps = new List<OperationStep>();

        void AddStep(OperationStep info, bool cancellable, Func<JobContext, CancellationToken, Task> execute, bool informationalOnly = false)
        {
            operationSteps.Add(info);
            steps.Add(new JobStepDefinition
            {
                Info = info,
                IsCancellable = cancellable,
                Execute = async (jobContext, cancellationToken) =>
                {
                    if (dryRun || informationalOnly)
                    {
                        jobContext.Log($"[Dry Run] {info.Title}" + (info.Detail is null ? "" : $": {info.Detail}"));
                        if (info.Command is not null)
                        {
                            jobContext.Log($"[Dry Run] Команда: adb/fastboot {info.Command}");
                        }

                        return;
                    }

                    await execute(jobContext, cancellationToken).ConfigureAwait(false);
                }
            });
        }

        AddStep(StrategySupport.Informational("Проверка целостности пакета",
            "Пересчёт SHA-256 файла прошивки и сравнение с сохранённым значением."), true,
            async (job, ct) =>
            {
                if (!context.Options.VerifyIntegrity || string.IsNullOrWhiteSpace(context.Package.Sha256))
                {
                    job.Log("SHA-256 не сохранён для этой сборки: проверка невозможна. Продолжение допускается только вручную.", LogLevel.Warning);
                    return;
                }

                if (!InputValidator.IsReadableFile(context.Package.FilePath))
                {
                    throw new FileNotFoundException("Файл прошивки недоступен.");
                }

                var actual = await Hashing.Sha256FileAsync(context.Package.FilePath!, null, ct).ConfigureAwait(false);
                if (!string.Equals(actual, context.Package.Sha256, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException("SHA-256 файла прошивки не совпадает. Операция остановлена.");
                }

                job.Log("SHA-256 подтверждён.");
            });

        if (archiveImageEntries.Count > 0)
        {
            AddStep(StrategySupport.Informational("Подготовка образов",
                $"Распаковка {archiveImageEntries.Count} образ(ов) во временный каталог (оригинал не изменяется)."), true,
                async (job, ct) =>
                {
                    PathSafety.TryDeleteDirectory(workDirectory);
                    Directory.CreateDirectory(workDirectory);
                    job.Log($"Временный каталог: {workDirectory}");

                    var extracted = await context.Extractor.ExtractAsync(context.Package.FilePath!, workDirectory, null, ct).ConfigureAwait(false);
                    job.Log($"Распаковано файлов: {extracted.Count}");

                    foreach (var target in targets)
                    {
                        var candidate = Directory.EnumerateFiles(workDirectory, Path.GetFileName(target.ImagePath), SearchOption.AllDirectories).FirstOrDefault();
                        if (candidate is null && !File.Exists(target.ImagePath))
                        {
                            throw new FileNotFoundException($"Образ «{Path.GetFileName(target.ImagePath)}» отсутствует после распаковки.");
                        }
                    }
                });
        }

        if (context.Device.Mode == DeviceMode.Adb)
        {
            AddStep(StrategySupport.DeviceChange("Перевод в fastboot", "Перезагрузка устройства в режим загрузчика.", "adb reboot bootloader"), false,
                async (job, ct) =>
                {
                    var result = await context.Adb.RebootAsync(context.Device.Serial!, DeviceDetection.Services.AdbRebootTarget.Bootloader, ct).ConfigureAwait(false);
                    if (!result.Started)
                    {
                        throw new InvalidOperationException("adb не запустился: " + result.StartError);
                    }

                    job.Log("Устройство перезагружается в fastboot. Ожидание до 60 секунд…");
                    for (var attempt = 0; attempt < 20; attempt++)
                    {
                        await Task.Delay(TimeSpan.FromSeconds(3), ct).ConfigureAwait(false);
                        var devices = await context.Fastboot.DevicesAsync(ct).ConfigureAwait(false);
                        if (devices.CombinedOutput.Contains(context.Device.Serial!, StringComparison.OrdinalIgnoreCase))
                        {
                            job.Log("Устройство обнаружено в fastboot.");
                            return;
                        }
                    }

                    throw new TimeoutException("Устройство не появилось в режиме fastboot. Проверьте кабель и драйвер.");
                });
        }

        var index = 0;
        foreach (var target in targets)
        {
            index++;
            var localIndex = index;
            AddStep(StrategySupport.DeviceChange($"Запись раздела {target.Partition}",
                    $"{Path.GetFileName(target.ImagePath)} → {target.Partition} (образ {localIndex} из {targets.Count})",
                    $"fastboot flash {target.Partition} {Path.GetFileName(target.ImagePath)}"),
                false,
                async (job, ct) =>
                {
                    var imagePath = ResolveActualImagePath(workDirectory, target.ImagePath);
                    job.Log($"Запись {target.Partition} из {Path.GetFileName(imagePath)}…");
                    var result = await context.Fastboot.FlashAsync(context.Device.Serial!, target.Partition, imagePath, ct).ConfigureAwait(false);

                    if (result.TimedOut)
                    {
                        throw new TimeoutException($"Тайм-аут записи раздела {target.Partition}.");
                    }

                    if (!result.Succeeded)
                    {
                        throw new InvalidOperationException(
                            $"fastboot flash {target.Partition} завершился с кодом {result.ExitCode}: {Trim(result.CombinedOutput)}");
                    }

                    job.Log($"Раздел {target.Partition} записан." + (string.IsNullOrWhiteSpace(result.CombinedOutput) ? "" : " " + Trim(result.CombinedOutput)));
                });
        }

        if (context.Options.WipeUserData)
        {
            AddStep(StrategySupport.Destructive("Стирание пользовательских данных",
                "Выполняется fastboot -w. Все данные устройства будут удалены безвозвратно."), false,
                async (job, ct) =>
                {
                    var result = await context.Fastboot.CustomCommandAsync(context.Device.Serial!, ["-w"], TimeSpan.FromMinutes(10), ct).ConfigureAwait(false);
                    if (!result.Succeeded)
                    {
                        throw new InvalidOperationException("fastboot -w завершился с ошибкой: " + Trim(result.CombinedOutput));
                    }

                    job.Log("Пользовательские данные стёрты.");
                });
        }

        AddStep(StrategySupport.Informational("Проверка результата", "Чтение переменных загрузчика после операции."), true,
            async (job, ct) =>
            {
                var vars = await context.Fastboot.GetVarAllAsync(context.Device.Serial!, ct).ConfigureAwait(false);
                var slot = vars.CombinedOutput.Split('\n').FirstOrDefault(l => l.Contains("current-slot", StringComparison.OrdinalIgnoreCase));
                job.Log("getvar выполнен." + (slot is null ? "" : " " + slot.Trim()));
            });

        if (context.Options.RebootAfter)
        {
            AddStep(StrategySupport.DeviceChange("Перезагрузка", "Устройство перезагружается в систему.", "fastboot reboot"), true,
                async (job, ct) =>
                {
                    var result = await context.Fastboot.RebootAsync(context.Device.Serial!, DeviceDetection.Services.FastbootRebootTarget.System, ct).ConfigureAwait(false);
                    job.Log(result.Succeeded ? "Команда перезагрузки отправлена." : "Команда перезагрузки вернула ошибку: " + Trim(result.CombinedOutput));
                });
        }

        AddStep(StrategySupport.Informational("Очистка временных файлов", "Удаление распакованных образов."), true,
            (job, _) =>
            {
                PathSafety.TryDeleteDirectory(workDirectory);
                job.Log("Временные файлы удалены.");
                return Task.CompletedTask;
            });

        var title = dryRun ? "Dry Run — план прошивки через Fastboot" : "Прошивка через Fastboot";
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

        var job = new JobRequest
        {
            Title = title,
            DeviceSummary = plan.DeviceSummary,
            FirmwareSummary = plan.FirmwareSummary,
            IsDryRun = dryRun,
            AllowCancellation = true,
            Steps = steps
        };

        return Task.FromResult(new FlashPlan
        {
            StrategyId = Id,
            StrategyName = Name,
            Plan = plan,
            Job = job,
            Targets = targets,
            PreparedDirectories = archiveImageEntries.Count > 0 ? [workDirectory] : Array.Empty<string>()
        });
    }

    private static IReadOnlyList<string> ListArchiveImages(FlashPlanContext context, List<CompatibilityItem> checks, List<string> warnings)
    {
        var images = new List<string>();
        var path = context.Package.FilePath;
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            checks.Add(new CompatibilityItem("Файл пакета", CompatibilitySeverity.Blocking, "Файл пакета недоступен."));
            return images;
        }

        var format = FormatDetector.Detect(path);
        try
        {
            IEnumerable<string> names = format switch
            {
                FirmwareFormat.Zip => ZipInspector.Inspect(path).Entries.Where(e => !e.IsDirectory).Select(e => e.FullName),
                FirmwareFormat.Tar or FirmwareFormat.TarMd5 => TarInspector.InspectFile(path).Entries.Where(e => !e.IsDirectory).Select(e => e.FullName),
                _ => Array.Empty<string>()
            };

            foreach (var name in names)
            {
                if (name.EndsWith(".img", StringComparison.OrdinalIgnoreCase) ||
                    name.EndsWith(".bin", StringComparison.OrdinalIgnoreCase) && name.Contains("vbmeta", StringComparison.OrdinalIgnoreCase))
                {
                    if (name.EndsWith(".bin", StringComparison.OrdinalIgnoreCase))
                    {
                        warnings.Add($"Файл «{name}» пропущен: формат .bin не трактуется как образ раздела автоматически.");
                        continue;
                    }

                    images.Add(name);
                }
            }

            if (images.Count == 0)
            {
                warnings.Add("В архиве не найдено .img файлов. Для Samsung-пакетов используйте соответствующий модуль.");
            }
        }
        catch (Exception ex) when (ex is IOException or InvalidDataException or InvalidOperationException)
        {
            checks.Add(new CompatibilityItem("Архив", CompatibilitySeverity.Blocking, "Архив не читается: " + ex.Message));
        }

        return images;
    }

    private static bool TryResolveTarget(FlashPlanContext context, string imagePathOrEntry, out FlashTarget? target, out string? reason)
    {
        target = null;
        reason = null;
        var fileName = Path.GetFileName(imagePathOrEntry.Replace('\\', '/'));

        if (context.Options.ManualImageMapping.TryGetValue(fileName, out var manual))
        {
            if (!InputValidator.IsValidPartitionName(manual))
            {
                reason = $"Ручное сопоставление для «{fileName}» содержит недопустимое имя раздела.";
                return false;
            }

            target = new FlashTarget { ImagePath = imagePathOrEntry, Partition = manual, FromManualMapping = true };
            return true;
        }

        if (KnownPartitionMap.TryGetPartition(fileName, out var partition))
        {
            target = new FlashTarget { ImagePath = imagePathOrEntry, Partition = partition };
            return true;
        }

        reason = $"Образ «{fileName}» пропущен: раздел не определён (используйте ручное сопоставление).";
        return false;
    }

    private static string ResolveActualImagePath(string workDirectory, string imagePath)
    {
        if (File.Exists(imagePath))
        {
            return imagePath;
        }

        var name = Path.GetFileName(imagePath.Replace('\\', '/'));
        var candidate = Directory.Exists(workDirectory)
            ? Directory.EnumerateFiles(workDirectory, name, SearchOption.AllDirectories).FirstOrDefault()
            : null;

        return candidate ?? imagePath;
    }

    private static string Trim(string text) =>
        text.Length > 400 ? text[..400] + "…" : text.Trim();
}
