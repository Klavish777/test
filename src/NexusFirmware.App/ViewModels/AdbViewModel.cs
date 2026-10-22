using System.Collections.ObjectModel;
using System.Text;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection.Services;

namespace NexusFirmware.App.ViewModels;

/// <summary>Консоль ADB и Fastboot: только диагностические операции с проверкой аргументов.</summary>
public sealed class AdbViewModel : PageViewModelBase
{
    private readonly AdbService _adb;
    private readonly FastbootService _fastboot;
    private readonly DeviceSession _session;
    private string _output = "Готово. Выберите устройство и выполните диагностическую операцию.";
    private string _customCommand = "";
    private bool _isBusy;
    private string _adbVersion = "не проверялся";
    private string _fastbootVersion = "не проверялся";

    public AdbViewModel(AdbService adb, FastbootService fastboot, DeviceSession session, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _adb = adb;
        _fastboot = fastboot;
        _session = session;
        _session.SelectionChanged += (_, _) => OnPropertyChanged(nameof(SelectedDevice));

        CheckToolsCommand = new AsyncRelayCommand(CheckToolsAsync, () => !IsBusy, ex => Handle("Проверка инструментов", ex));
        GetPropsCommand = new AsyncRelayCommand(GetPropsAsync, () => CanUseAdb, ex => Handle("Чтение свойств", ex));
        BatteryCommand = new AsyncRelayCommand(BatteryAsync, () => CanUseAdb, ex => Handle("Состояние батареи", ex));
        LogcatCommand = new AsyncRelayCommand(LogcatAsync, () => CanUseAdb, ex => Handle("logcat", ex));
        RebootSystemCommand = new AsyncRelayCommand(() => RebootAsync(AdbRebootTarget.System), () => CanUseAdb, ex => Handle("Перезагрузка", ex));
        RebootBootloaderCommand = new AsyncRelayCommand(() => RebootAsync(AdbRebootTarget.Bootloader), () => CanUseAdb, ex => Handle("Перезагрузка в fastboot", ex));
        RebootRecoveryCommand = new AsyncRelayCommand(() => RebootAsync(AdbRebootTarget.Recovery), () => CanUseAdb, ex => Handle("Перезагрузка в recovery", ex));
        FastbootVarsCommand = new AsyncRelayCommand(FastbootVarsAsync, () => CanUseFastboot, ex => Handle("fastboot getvar", ex));
        FastbootPartitionsCommand = new AsyncRelayCommand(FastbootPartitionsAsync, () => CanUseFastboot, ex => Handle("Разделы fastboot", ex));
        ClearOutputCommand = new RelayCommand(() => Output = "");
        RunCustomCommand = new AsyncRelayCommand(RunCustomAsync, () => !IsBusy && !string.IsNullOrWhiteSpace(CustomCommand), ex => Handle("Пользовательская команда", ex));
        OpenFlashingCommand = new RelayCommand(() => AppNavigation.Request("flashing"));
    }

    public override string Title => "ADB и Fastboot";

    public ObservableCollection<DeviceInfo> Devices => _session.Devices;

    public ObservableCollection<PartitionRow> Partitions { get; } = new();

    public ObservableCollection<DeviceDetailRow> FastbootVariables { get; } = new();

    public DeviceInfo? SelectedDevice
    {
        get => _session.SelectedDevice;
        set => _session.Select(value);
    }

    public bool CanUseAdb => SelectedDevice is { Mode: DeviceMode.Adb or DeviceMode.Recovery or DeviceMode.Sideload, Serial: not null };

    public bool CanUseFastboot => SelectedDevice is { Mode: DeviceMode.Fastboot, Serial: not null };

    public string AdbVersion
    {
        get => _adbVersion;
        private set => SetProperty(ref _adbVersion, value);
    }

    public string FastbootVersion
    {
        get => _fastbootVersion;
        private set => SetProperty(ref _fastbootVersion, value);
    }

    public string Output
    {
        get => _output;
        private set => SetProperty(ref _output, value);
    }

    public string CustomCommand
    {
        get => _customCommand;
        set => SetProperty(ref _customCommand, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public AsyncRelayCommand CheckToolsCommand { get; }

    public AsyncRelayCommand GetPropsCommand { get; }

    public AsyncRelayCommand BatteryCommand { get; }

    public AsyncRelayCommand LogcatCommand { get; }

    public AsyncRelayCommand RebootSystemCommand { get; }

    public AsyncRelayCommand RebootBootloaderCommand { get; }

    public AsyncRelayCommand RebootRecoveryCommand { get; }

    public AsyncRelayCommand FastbootVarsCommand { get; }

    public AsyncRelayCommand FastbootPartitionsCommand { get; }

    public AsyncRelayCommand RunCustomCommand { get; }

    public RelayCommand ClearOutputCommand { get; }

    public RelayCommand OpenFlashingCommand { get; }

    public override void OnActivated()
    {
        OnPropertyChanged(nameof(SelectedDevice));
        _ = CheckToolsAsync();
    }

    private async Task CheckToolsAsync()
    {
        IsBusy = true;
        try
        {
            var adbOk = await _adb.CheckAsync().ConfigureAwait(true);
            var fastbootOk = await _fastboot.CheckAsync().ConfigureAwait(true);
            AdbVersion = adbOk ? "доступен" : "не найден";
            FastbootVersion = fastbootOk ? "доступен" : "не найден";
            Output = $"ADB: {AdbVersion}{Environment.NewLine}Fastboot: {FastbootVersion}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task GetPropsAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var all = await _adb.GetPropAsync(device.Serial).ConfigureAwait(true);
            var interestingKeys = new[]
            {
                "ro.product.manufacturer", "ro.product.model", "ro.product.device", "ro.build.version.release",
                "ro.build.display.id", "ro.bootloader", "ro.boot.flash.locked", "ro.boot.verifiedbootstate",
                "ro.board.platform", "ro.boot.slot_suffix", "ro.product.locale.region", "ro.csc.country_code"
            };

            var props = DeviceDetection.Adb.AdbProvider.ParseProps(all.StandardOutput);
            var sb = new StringBuilder();
            sb.AppendLine("Свойства устройства (избранные):");
            foreach (var key in interestingKeys)
            {
                var value = props.GetValueOrDefault(key);
                sb.AppendLine($"  {key,-32} {(string.IsNullOrWhiteSpace(value) ? "—" : value)}");
            }

            sb.AppendLine();
            sb.AppendLine($"Всего свойств: {props.Count}. Полный вывод адресован в журнал (с маскированием).");
            Output = sb.ToString();
            Log.Info(Title, "Прочитаны свойства Android.");
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task BatteryAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var result = await _adb.ShellAsync(device.Serial, ["dumpsys", "battery"]).ConfigureAwait(true);
            Output = result.CombinedOutput;
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LogcatAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var result = await _adb.LogcatAsync(device.Serial, 300).ConfigureAwait(true);
            Output = result.CombinedOutput;
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task RebootAsync(AdbRebootTarget target)
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        if (target != AdbRebootTarget.System && !Dialogs.Confirm("Перезагрузка", $"Перезагрузить устройство в режим {target}?"))
        {
            return;
        }

        IsBusy = true;
        try
        {
            var result = await _adb.RebootAsync(device.Serial, target).ConfigureAwait(true);
            Output = result.Succeeded
                ? $"Команда перезагрузки ({target}) отправлена."
                : $"Ошибка перезагрузки: {result.CombinedOutput}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task FastbootVarsAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var result = await _fastboot.GetVarAllAsync(device.Serial).ConfigureAwait(true);
            FastbootVariables.Clear();
            foreach (var line in result.CombinedOutput.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            {
                var trimmed = line.Trim();
                if (trimmed.Length == 0)
                {
                    continue;
                }

                var separator = trimmed.IndexOf(':');
                if (separator > 0)
                {
                    FastbootVariables.Add(new DeviceDetailRow
                    {
                        Label = trimmed[..separator].Trim().Replace("(bootloader) ", ""),
                        Value = trimmed[(separator + 1)..].Trim()
                    });
                }
            }

            Output = $"Переменных fastboot: {FastbootVariables.Count}.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task FastbootPartitionsAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var partitions = await _fastboot.GetPartitionsAsync(device.Serial).ConfigureAwait(true);
            Partitions.Clear();
            foreach (var (name, size) in partitions.OrderBy(p => p.Partition))
            {
                Partitions.Add(new PartitionRow
                {
                    Name = name,
                    Size = size is null ? "недоступно" : SizeFormatting.HumanReadable(size.Value),
                    Source = "fastboot getvar all"
                });
            }

            Output = $"Разделов: {Partitions.Count}.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task RunCustomAsync()
    {
        var args = CustomCommand.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (args.Length == 0)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var device = SelectedDevice;
            var result = device?.Mode == DeviceMode.Fastboot
                ? await _fastboot.CustomCommandAsync(device.Serial, args).ConfigureAwait(true)
                : await _adb.CustomCommandAsync(device?.Serial, args).ConfigureAwait(true);

            Output = $"$ {string.Join(' ', args)}{Environment.NewLine}" +
                     $"Код возврата: {result.ExitCode}{(result.TimedOut ? " (тайм-аут)" : "")}{Environment.NewLine}{Environment.NewLine}" +
                     result.CombinedOutput;
        }
        finally
        {
            IsBusy = false;
        }
    }
}
