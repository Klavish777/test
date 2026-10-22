using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.DeviceDetection.Services;

public enum AdbRebootTarget
{
    System,
    Bootloader,
    Recovery,
    Sideload,
    Fastboot
}

/// <summary>
/// Разрешённые диагностические операции ADB. Команды запускаются отдельным процессом,
/// аргументы передаются списком, ввод пользователя проверяется. Обход авторизации ADB невозможен.
/// </summary>
public sealed class AdbService
{
    private readonly IProcessRunner _runner;
    private readonly IToolLocator _locator;
    private readonly ILogBus _log;

    public AdbService(IProcessRunner runner, IToolLocator locator, ILogBus log)
    {
        _runner = runner;
        _locator = locator;
        _log = log;
    }

    public string? AdbPath => _locator.Find("adb");

    public bool IsAvailable => AdbPath is not null;

    public async Task<bool> CheckAsync(CancellationToken cancellationToken = default)
    {
        if (AdbPath is null)
        {
            return false;
        }

        var result = await RunAsync(["version"], TimeSpan.FromSeconds(10), cancellationToken).ConfigureAwait(false);
        if (result.Started)
        {
            _log.Info("ADB", $"Версия adb: {FirstLine(result.StandardOutput)}");
            return true;
        }

        _log.Error("ADB", "adb не запускается: " + result.StartError);
        return false;
    }

    public Task<ProcessResult> DevicesAsync(CancellationToken cancellationToken = default) =>
        RunAsync(["devices", "-l"], TimeSpan.FromSeconds(12), cancellationToken);

    public Task<ProcessResult> GetPropAsync(string serial, CancellationToken cancellationToken = default) =>
        RunForDeviceAsync(serial, ["shell", "getprop"], TimeSpan.FromSeconds(15), cancellationToken);

    public Task<ProcessResult> GetPropAsync(string serial, string key, CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsValidPropertyKey(key))
        {
            throw new ArgumentException("Недопустимое имя свойства Android.", nameof(key));
        }

        return RunForDeviceAsync(serial, ["shell", "getprop", key], TimeSpan.FromSeconds(10), cancellationToken);
    }

    public Task<ProcessResult> ShellAsync(string serial, IReadOnlyList<string> command, CancellationToken cancellationToken = default)
    {
        if (command.Count == 0)
        {
            throw new ArgumentException("Команда оболочки не указана.", nameof(command));
        }

        var args = new List<string> { "shell" };
        args.AddRange(command);
        return RunForDeviceAsync(serial, args, TimeSpan.FromSeconds(30), cancellationToken);
    }

    public Task<ProcessResult> LogcatAsync(string serial, int lines = 200, CancellationToken cancellationToken = default)
    {
        var safeLines = Math.Clamp(lines, 10, 5000);
        return RunForDeviceAsync(serial, ["logcat", "-d", "-t", safeLines.ToString()], TimeSpan.FromSeconds(45), cancellationToken);
    }

    public Task<ProcessResult> RebootAsync(string serial, AdbRebootTarget target, CancellationToken cancellationToken = default)
    {
        var argument = target switch
        {
            AdbRebootTarget.System => null,
            AdbRebootTarget.Bootloader => "bootloader",
            AdbRebootTarget.Recovery => "recovery",
            AdbRebootTarget.Sideload => "sideload",
            AdbRebootTarget.Fastboot => "fastboot",
            _ => null
        };

        var args = argument is null ? new[] { "reboot" } : new[] { "reboot", argument };
        _log.Info("ADB", $"Перезагрузка устройства в режим {target}.");
        return RunForDeviceAsync(serial, args, TimeSpan.FromSeconds(20), cancellationToken);
    }

    public Task<ProcessResult> SideloadAsync(string serial, string packagePath, CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsReadableFile(packagePath))
        {
            throw new FileNotFoundException("Пакет для sideload не найден.", packagePath);
        }

        _log.Info("ADB", $"Sideload пакета {Path.GetFileName(packagePath)}.");
        return RunForDeviceAsync(serial, ["sideload", packagePath], TimeSpan.FromMinutes(30), cancellationToken);
    }

    /// <summary>Пользовательская диагностическая команда. Опасные операции записи не выполняются.</summary>
    public Task<ProcessResult> CustomCommandAsync(string? serial, IReadOnlyList<string> arguments, TimeSpan? timeout = null, CancellationToken cancellationToken = default)
    {
        if (arguments.Count == 0)
        {
            throw new ArgumentException("Не указаны аргументы команды.", nameof(arguments));
        }

        var blocked = new[] { "root", "unroot", "remount", "disable-verity", "enable-verity", "fastboot", "push", "pull", "install", "uninstall" };
        if (blocked.Contains(arguments[0], StringComparer.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"Команда «{arguments[0]}» не входит в разрешённый набор диагностических операций.");
        }

        if (arguments[0].Equals("shell", StringComparison.OrdinalIgnoreCase))
        {
            var shellCommand = string.Join(' ', arguments.Skip(1)).ToLowerInvariant();
            var forbidden = new[] { "rm ", "dd ", "mkfs", "format", "mount -o rw", "> /system", "> /data" };
            if (forbidden.Any(f => shellCommand.Contains(f, StringComparison.Ordinal)))
            {
                throw new InvalidOperationException("Команда изменяет данные устройства и заблокирована в диагностическом режиме.");
            }
        }

        var args = new List<string>();
        if (!string.IsNullOrWhiteSpace(serial))
        {
            if (!InputValidator.IsValidSerial(serial))
            {
                throw new ArgumentException("Недопустимый серийный номер.", nameof(serial));
            }

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
        var adb = AdbPath ?? throw new InvalidOperationException("ADB не найден. Установите Android Platform Tools и укажите путь в настройках.");

        return _runner.RunAsync(new ProcessRequest
        {
            FileName = adb,
            Arguments = arguments,
            Timeout = timeout,
            Description = "adb " + string.Join(' ', arguments.Take(3))
        }, cancellationToken);
    }

    private static string FirstLine(string text) =>
        text.Split('\n', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault()?.Trim() ?? "";
}
