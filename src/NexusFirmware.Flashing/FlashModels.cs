using NexusFirmware.Core.Models;

namespace NexusFirmware.Flashing;

public sealed class FlashOptions
{
    /// <summary>Только предварительная проверка: устройство не изменяется.</summary>
    public bool DryRun { get; init; } = true;

    /// <summary>Разрешить операции, изменяющие устройство. По умолчанию запрещено.</summary>
    public bool AllowDeviceModification { get; init; }

    /// <summary>Продолжать, если состояние загрузчика не определено (рискованно).</summary>
    public bool AllowUnknownBootloader { get; init; }

    /// <summary>Стирание пользовательских данных (fastboot -w). Требует отдельного подтверждения.</summary>
    public bool WipeUserData { get; init; }

    public bool ConfirmDataWipe { get; init; }

    /// <summary>Проверять SHA-256 перед операцией.</summary>
    public bool VerifyIntegrity { get; init; } = true;

    /// <summary>Перезагрузить устройство после успешной операции.</summary>
    public bool RebootAfter { get; init; } = true;

    /// <summary>Ручной выбор разделов (имя файла → раздел).</summary>
    public IReadOnlyDictionary<string, string> ManualImageMapping { get; init; } = new Dictionary<string, string>();

    public bool IsExecution => !DryRun && AllowDeviceModification;
}

public sealed class FlashTarget
{
    public required string ImagePath { get; init; }
    public required string Partition { get; init; }
    public bool FromManualMapping { get; init; }
}

public sealed class FlashPlan
{
    public required string StrategyId { get; init; }
    public required string StrategyName { get; init; }
    public required OperationPlan Plan { get; init; }
    public required JobRequest Job { get; init; }
    public IReadOnlyList<FlashTarget> Targets { get; init; } = Array.Empty<FlashTarget>();
    public IReadOnlyList<string> PreparedDirectories { get; init; } = Array.Empty<string>();

    public bool IsExecutable => !Plan.HasBlockingIssues && Job.Steps.Count > 0;
}

public sealed class FlashPlanContext
{
    public required DeviceInfo Device { get; init; }
    public required FirmwarePackage Package { get; init; }
    public required FlashOptions Options { get; init; }
    public required DeviceDetection.Services.AdbService Adb { get; init; }
    public required DeviceDetection.Services.FastbootService Fastboot { get; init; }
    public required Firmware.Extractor.FirmwareExtractorService Extractor { get; init; }
    public required Firmware.Extractor.FirmwareAnalyzer Analyzer { get; init; }
    public required Core.Abstractions.ILogBus Log { get; init; }
    public string? DeviceBinaryRevision { get; init; }
    public string? PackageBinaryRevision { get; init; }
}

public interface IFlashStrategy
{
    string Id { get; }

    string Name { get; }

    /// <summary>Поддерживает ли стратегия данное сочетание устройства и пакета (без выполнения).</summary>
    bool CanHandle(DeviceInfo device, FirmwarePackage package);

    Task<FlashPlan> BuildPlanAsync(FlashPlanContext context, CancellationToken cancellationToken = default);
}

/// <summary>Известные образы и их разделы. Используется только для точного сопоставления имён.</summary>
public static class KnownPartitionMap
{
    private static readonly Dictionary<string, string> Map = new(StringComparer.OrdinalIgnoreCase)
    {
        ["boot"] = "boot",
        ["init_boot"] = "init_boot",
        ["vendor_boot"] = "vendor_boot",
        ["recovery"] = "recovery",
        ["dtbo"] = "dtbo",
        ["vbmeta"] = "vbmeta",
        ["vbmeta_system"] = "vbmeta_system",
        ["vbmeta_vendor"] = "vbmeta_vendor",
        ["super"] = "super",
        ["system"] = "system",
        ["vendor"] = "vendor",
        ["product"] = "product",
        ["odm"] = "odm",
        ["system_ext"] = "system_ext",
        ["modem"] = "modem",
        ["radio"] = "radio",
        ["logo"] = "logo",
        ["misc"] = "misc",
        ["persist"] = "persist",
        ["abl"] = "abl",
        ["xbl"] = "xbl",
        ["xbl_config"] = "xbl_config",
        ["tz"] = "tz",
        ["hyp"] = "hyp",
        ["keymaster"] = "keymaster",
        ["aop"] = "aop",
        ["devcfg"] = "devcfg",
        ["dsp"] = "dsp",
        ["featenabler"] = "featenabler",
        ["qupfw"] = "qupfw",
        ["uefisecapp"] = "uefisecapp",
        ["imagefv"] = "imagefv",
        ["multiimgoem"] = "multiimgoem",
        ["shrm"] = "shrm",
        ["storsec"] = "storsec",
        ["metadata"] = "metadata"
    };

    public static bool TryGetPartition(string imageFileName, out string partition)
    {
        var name = Path.GetFileNameWithoutExtension(imageFileName).ToLowerInvariant();
        name = name.Replace("-", "_");

        // Отбрасываем типичные суффиксы сборки: boot_a.img, boot-slot-a.img и т.п.
        foreach (var suffix in new[] { "_a", "_b", "-slot-a", "-slot-b" })
        {
            if (name.EndsWith(suffix, StringComparison.Ordinal))
            {
                name = name[..^suffix.Length];
                break;
            }
        }

        if (Map.TryGetValue(name, out var partitionName))
        {
            partition = partitionName;
            return true;
        }

        partition = string.Empty;
        return false;
    }

    public static IReadOnlyCollection<string> KnownImages => Map.Keys;
}
