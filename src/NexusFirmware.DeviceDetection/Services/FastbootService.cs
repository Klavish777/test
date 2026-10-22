using System.Text.RegularExpressions;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.DeviceDetection.Services;

public enum FastbootRebootTarget
{
    System,
    Bootloader,
    Recovery
}

/// <summary>
/// Операции Fastboot. Запись разделов выполняется только по явному плану, после подтверждения
/// пользователем и только для разблокированного загрузчика (проверка в планировщике).
/// </summary>
public sealed class FastbootService
{
    private readonly IProcessRunner _runner;
    private readonly IToolLocator _locator;
    private readonly ILogBus _log;

    public FastbootService(IProcessRunner runner, IToolLocator locator, ILogBus log)
    {
        _runner = runner;
        _locator = locator;
        _log = log;
    }

    public string? FastbootPath => _locator.Find("fastboot");

    public bool IsAvailable => FastbootPath is not null;

    public async Task<bool> CheckAsync(CancellationToken cancellationToken = default)
    {
        if (FastbootPath is null)
        {
            return false;
        }

        var result = await RunAsync(["--version"], TimeSpan.FromSeconds(10), cancellationToken).ConfigureAwait(false);
        if (result.Started)
        {
            _log.Info("Fastboot", "fastboot доступен: " + FirstLine(result.CombinedOutput));
            return true;
        }

        _log.Error("Fastboot", "fastboot не запускается: " + result.StartError);
        return false;
    }

    public Task<ProcessResult> DevicesAsync(CancellationToken cancellationToken = default) =>
        RunAsync(["devices"], TimeSpan.FromSeconds(12), cancellationToken);

    public Task<ProcessResult> GetVarAllAsync(string serial, CancellationToken cancellationToken = default) =>
        RunForDeviceAsync(serial, ["getvar", "all"], TimeSpan.FromSeconds(25), cancellationToken);

    public Task<ProcessResult> GetVarAsync(string serial, string variable, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(variable) || !Regex.IsMatch(variable, "^[A-Za-z0-9_.:-]{1,64}$"))
        {
            throw new ArgumentException("Недопустимое имя переменной fastboot.", nameof(variable));
        }

        return RunForDeviceAsync(serial, ["getvar", variable], TimeSpan.FromSeconds(10), cancellationToken);
    }

    /// <summary>Список разделов из вывода getvar all (partition-size:xxx).</summary>
    public async Task<IReadOnlyList<(string Partition, long? SizeBytes)>> GetPartitionsAsync(string serial, CancellationToken cancellationToken = default)
    {
        var result = await GetVarAllAsync(serial, cancellationToken).ConfigureAwait(false);
        return ParsePartitions(result.CombinedOutput);
    }

    public static IReadOnlyList<(string Partition, long? SizeBytes)> ParsePartitions(string output)
    {
        var list = new List<(string, long?)>();
        if (string.IsNullOrWhiteSpace(output))
        {
            return list;
        }

        foreach (var line in output.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var match = Regex.Match(line, @"partition-size:(?<name>[A-Za-z0-9_\-]+):(?<size>0x[0-9A-Fa-f]+|\d+)", RegexOptions.CultureInvariant);
            if (!match.Success)
            {
                continue;
            }

            var name = match.Groups["name"].Value;
            var sizeText = match.Groups["size"].Value;
            long? size = null;

            if (sizeText.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            {
                if (long.TryParse(sizeText[2..], System.Globalization.NumberStyles.HexNumber, null, out var hex))
                {
                    size = hex;
                }
            }
            else if (long.TryParse(sizeText, out var dec))
            {
                size = dec;
            }

            list.Add((name, size));
        }

        return list;
    }

    public Task<ProcessResult> FlashAsync(string serial, string partition, string imagePath, CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsValidPartitionName(partition))
        {
            throw new ArgumentException("Недопустимое имя раздела.", nameof(partition));
        }

        if (!InputValidator.IsReadableFile(imagePath))
        {
            throw new FileNotFoundException("Образ не найден или пуст.", imagePath);
        }

        _log.Warn("Fastboot", $"Запись раздела {partition} из {Path.GetFileName(imagePath)}.");
        return RunForDeviceAsync(serial, ["flash", partition, imagePath], TimeSpan.FromMinutes(20), cancellationToken);
    }

    /// <summary>Запись sparse-образа в super/логический раздел (fastboot 30+).</summary>
    public Task<ProcessResult> FlashSparseAsync(string serial, string partition, string imagePath, CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsValidPartitionName(partition))
        {
            throw new ArgumentException("Недопустимое имя раздела.", nameof(partition));
        }

        if (!InputValidator.IsReadableFile(imagePath))
        {
            throw new FileNotFoundException("Образ не найден или пуст.", imagePath);
        }

        return RunForDeviceAsync(serial, ["flash", partition, imagePath], TimeSpan.FromMinutes(30), cancellationToken);
    }

    public Task<ProcessResult> EraseAsync(string serial, string partition, CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsValidPartitionName(partition))
        {
            throw new ArgumentException("Недопустимое имя раздела.", nameof(partition));
        }

        _log.Warn("Fastboot", $"Стирание раздела {partition}.");
        return RunForDeviceAsync(serial, ["erase", partition], TimeSpan.FromMinutes(5), cancellationToken);
    }

    public Task<ProcessResult> RebootAsync(string serial, FastbootRebootTarget target, CancellationToken cancellationToken = default)
    {
        var args = target switch
        {
            FastbootRebootTarget.Bootloader => new[] { "reboot-bootloader" },
            FastbootRebootTarget.Recovery => new[] { "reboot", "recovery" },
            _ => new[] { "reboot" }
        };

        return RunForDeviceAsync(serial, args, TimeSpan.FromSeconds(30), cancellationToken);
    }

    public Task<ProcessResult> RebootFastbootdAsync(string serial, CancellationToken cancellationToken = default) =>
        RunForDeviceAsync(serial, ["reboot", "fastboot"], TimeSpan.FromSeconds(30), cancellationToken);

    public Task<ProcessResult> SetActiveSlotAsync(string serial, string slot, CancellationToken cancellationToken = default)
    {
        if (slot is not ("a" or "b"))
        {
            throw new ArgumentException("Слот должен быть «a» или «b».", nameof(slot));
        }

        return RunForDeviceAsync(serial, ["--set-active=" + slot], TimeSpan.FromSeconds(30), cancellationToken);
    }

    public Task<ProcessResult> CustomCommandAsync(string? serial, IReadOnlyList<string> arguments, TimeSpan? timeout = null, CancellationToken cancellationToken = default)
    {
        var blocked = new[] { "oem", "flashing", "unlock", "unlock_critical", "lock", "format", "wipe" };
        if (arguments.Count > 0 && blocked.Contains(arguments[0], StringComparer.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"Команда «{arguments[0]}» изменяет состояние загрузчика и недоступна в диагностическом режиме.");
        }

        var args = new List<string>();
        if (!string.IsNullOrWhiteSpace(serial))
        {
            args.Add("-s");
            args.Add(serial);
        }

        args.AddRange(arguments);
        return RunAsync(args, timeout ?? TimeSpan.FromSeconds(45), cancellationToken);
    }

    private Task<ProcessResult> RunForDeviceAsync(string serial, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
    {
        if (!InputValidator.IsValidSerial(serial))
        {
            throw new ArgumentException("Недопустимый серийный номер устройства.", nameof(serial));
        }

        var args = new List<string> { "-s", serial };
        args.AddRange(arguments);
        return RunAsync(args, timeout, cancellationToken);
    }

    private Task<ProcessResult> RunAsync(IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
    {
        var fastboot = FastbootPath ?? throw new InvalidOperationException("Fastboot не найден. Установите Android Platform Tools.");

        return _runner.RunAsync(new ProcessRequest
        {
            FileName = fastboot,
            Arguments = arguments,
            Timeout = timeout,
            Description = "fastboot " + string.Join(' ', arguments.Take(3))
        }, cancellationToken);
    }

    private static string FirstLine(string text) =>
        text.Split('\n', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault()?.Trim() ?? "";
}
