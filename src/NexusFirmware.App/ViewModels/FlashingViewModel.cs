using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Jobs;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection.Services;
using NexusFirmware.Firmware.Extractor;
using NexusFirmware.Firmware.Library;
using NexusFirmware.Flashing;
using NexusFirmware.Infrastructure.Configuration;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace NexusFirmware.App.ViewModels;

/// <summary>Мастер прошивки: обнаружение → проверки → план → подтверждение → выполнение → отчёт.</summary>
public sealed class FlashingViewModel : PageViewModelBase
{
    private readonly FlashPlanner _planner;
    private readonly FirmwareLibrary _library;
    private readonly DeviceSession _session;
    private readonly JobQueue _jobs;
    private readonly SettingsService _settings;
    private readonly AdbService _adb;
    private readonly FastbootService _fastboot;
    private readonly FirmwareExtractorService _extractor;
    private readonly FirmwareAnalyzer _analyzer;

    private FirmwarePackage? _selectedPackage;
    private FlashPlan? _plan;
    private bool _isDryRun = true;
    private bool _allowModification;
    private bool _allowUnknownBootloader;
    private bool _wipeUserData;
    private bool _confirmDataWipe;
    private bool _verifyIntegrity = true;
    private bool _rebootAfter = true;
    private string _mappingText = "";
    private bool _isBusy;
    private string _statusText = "Шаг 1: выберите устройство и прошивку, затем постройте план.";
    private string _strategyText = "—";

    public FlashingViewModel(
        FlashPlanner planner,
        FirmwareLibrary library,
        DeviceSession session,
        JobQueue jobs,
        SettingsService settings,
        AdbService adb,
        FastbootService fastboot,
        FirmwareExtractorService extractor,
        FirmwareAnalyzer analyzer,
        ILogBus log,
        DialogService dialogs)
        : base(log, dialogs)
    {
        _planner = planner;
        _library = library;
        _session = session;
        _jobs = jobs;
        _settings = settings;
        _adb = adb;
        _fastboot = fastboot;
        _extractor = extractor;
        _analyzer = analyzer;

        _session.DevicesChanged += (_, _) => OnPropertyChanged(nameof(SelectedDevice));
        _session.SelectionChanged += (_, _) => OnPropertyChanged(nameof(SelectedDevice));

        BuildPlanCommand = new AsyncRelayCommand(BuildPlanAsync, () => !IsBusy, ex => Handle("Построение плана", ex));
        RunDryRunCommand = new AsyncRelayCommand(RunDryRunAsync, () => !IsBusy && _plan is not null, ex => Handle("Dry Run", ex));
        ExecuteCommand = new AsyncRelayCommand(ExecuteAsync, () => !IsBusy && _plan is not null, ex => Handle("Прошивка", ex));
        ReloadPackagesCommand = new RelayCommand(LoadPackages);
        OpenFirmwareCenterCommand = new RelayCommand(() => AppNavigation.Request("firmware"));
        OpenAdbConsoleCommand = new RelayCommand(() => AppNavigation.Request("adb"));

        LoadPackages();
    }

    public override string Title => "Станция прошивки";

    public ObservableCollection<FirmwarePackage> Packages { get; } = new();

    public ObservableCollection<OperationStep> PlanSteps { get; } = new();

    public ObservableCollection<CompatibilityItem> PlanChecks { get; } = new();

    public ObservableCollection<string> PlanWarnings { get; } = new();

    public ObservableCollection<string> Targets { get; } = new();

    public ObservableCollection<DeviceInfo> Devices => _session.Devices;

    public DeviceInfo? SelectedDevice
    {
        get => _session.SelectedDevice;
        set => _session.Select(value);
    }

    public FirmwarePackage? SelectedPackage
    {
        get => _selectedPackage;
        set
        {
            if (SetProperty(ref _selectedPackage, value))
            {
                _plan = null;
                PlanSteps.Clear();
                PlanChecks.Clear();
                PlanWarnings.Clear();
                Targets.Clear();
                OnPropertyChanged(nameof(CanExecute));
            }
        }
    }

    public bool IsDryRun
    {
        get => _isDryRun;
        set => SetProperty(ref _isDryRun, value);
    }

    public bool AllowModification
    {
        get => _allowModification;
        set
        {
            if (SetProperty(ref _allowModification, value))
            {
                OnPropertyChanged(nameof(CanExecute));
            }
        }
    }

    public bool AllowUnknownBootloader
    {
        get => _allowUnknownBootloader;
        set => SetProperty(ref _allowUnknownBootloader, value);
    }

    public bool WipeUserData
    {
        get => _wipeUserData;
        set => SetProperty(ref _wipeUserData, value);
    }

    public bool ConfirmDataWipe
    {
        get => _confirmDataWipe;
        set => SetProperty(ref _confirmDataWipe, value);
    }

    public bool VerifyIntegrity
    {
        get => _verifyIntegrity;
        set => SetProperty(ref _verifyIntegrity, value);
    }

    public bool RebootAfter
    {
        get => _rebootAfter;
        set => SetProperty(ref _rebootAfter, value);
    }

    public string MappingText
    {
        get => _mappingText;
        set => SetProperty(ref _mappingText, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetProperty(ref _isBusy, value))
            {
                OnPropertyChanged(nameof(CanExecute));
            }
        }
    }

    public string StatusText
    {
        get => _statusText;
        private set => SetProperty(ref _statusText, value);
    }

    public string StrategyText
    {
        get => _strategyText;
        private set => SetProperty(ref _strategyText, value);
    }

    public string PlanTitle => _plan?.Plan.Title ?? "План не построен";

    public string PlanSummary => _plan is null
        ? "Сначала постройте план: приложение проверит совместимость, целостность и загрузчик."
        : $"{_plan.Plan.DeviceSummary} · {_plan.Plan.FirmwareSummary}";

    public bool CanExecute => _plan is not null && !_plan.Plan.HasBlockingIssues && !IsBusy;

    public bool HasBlocking => _plan?.Plan.HasBlockingIssues ?? false;

    public string ReadOnlyBanner => _settings.Current.ReadOnlyMode
        ? "Глобальный режим только чтения включён: реальная запись заблокирована в настройках."
        : "Режим только чтения выключен. Реальная запись требует подтверждения серийного номера.";

    public AsyncRelayCommand BuildPlanCommand { get; }

    public AsyncRelayCommand RunDryRunCommand { get; }

    public AsyncRelayCommand ExecuteCommand { get; }

    public RelayCommand ReloadPackagesCommand { get; }

    public RelayCommand OpenFirmwareCenterCommand { get; }

    public RelayCommand OpenAdbConsoleCommand { get; }

    public override void OnActivated()
    {
        LoadPackages();
        OnPropertyChanged(nameof(SelectedDevice));
        OnPropertyChanged(nameof(ReadOnlyBanner));
    }

    private void LoadPackages()
    {
        Packages.Clear();
        foreach (var package in _library.GetPackages())
        {
            Packages.Add(package);
        }

        SelectedPackage ??= Packages.FirstOrDefault();
    }

    private IReadOnlyDictionary<string, string> ParseMapping()
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in MappingText.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var trimmed = line.Trim();
            if (trimmed.Length == 0 || trimmed.StartsWith('#'))
            {
                continue;
            }

            var parts = trimmed.Split('=', 2, StringSplitOptions.TrimEntries);
            if (parts.Length == 2 && parts[0].Length > 0 && parts[1].Length > 0)
            {
                map[parts[0]] = parts[1];
            }
        }

        return map;
    }

    private async Task BuildPlanAsync()
    {
        if (SelectedDevice is null)
        {
            Dialogs.Warn("Станция прошивки", "Устройство не выбрано. Подключите устройство и обновите список.");
            return;
        }

        if (SelectedPackage is null)
        {
            Dialogs.Warn("Станция прошивки", "Прошивка не выбрана. Импортируйте файл в Центре прошивок.");
            return;
        }

        IsBusy = true;
        StatusText = "Построение плана и проверка условий…";
        try
        {
            var options = new FlashOptions
            {
                DryRun = !AllowModification,
                AllowDeviceModification = AllowModification && !_settings.Current.ReadOnlyMode,
                AllowUnknownBootloader = AllowUnknownBootloader,
                WipeUserData = WipeUserData,
                ConfirmDataWipe = ConfirmDataWipe,
                VerifyIntegrity = VerifyIntegrity,
                RebootAfter = RebootAfter,
                ManualImageMapping = ParseMapping()
            };

            var deviceRevision = Samsung.SamsungService.ExtractBinaryRevision(SelectedDevice.BootloaderVersion);
            SelectedPackage.Metadata.TryGetValue("samsung.binary", out var packageRevision);

            var context = new FlashPlanContext
            {
                Device = SelectedDevice,
                Package = SelectedPackage,
                Options = options,
                Adb = _adb,
                Fastboot = _fastboot,
                Extractor = _extractor,
                Analyzer = _analyzer,
                Log = Log,
                DeviceBinaryRevision = deviceRevision,
                PackageBinaryRevision = packageRevision
            };

            _plan = await _planner.BuildPlanAsync(context).ConfigureAwait(true);

            PlanSteps.Clear();
            foreach (var step in _plan.Plan.Steps)
            {
                PlanSteps.Add(step);
            }

            PlanChecks.Clear();
            foreach (var check in _plan.Plan.Checks)
            {
                PlanChecks.Add(check);
            }

            PlanWarnings.Clear();
            foreach (var warning in _plan.Plan.Warnings)
            {
                PlanWarnings.Add(warning);
            }

            Targets.Clear();
            foreach (var target in _plan.Targets)
            {
                Targets.Add($"{Path.GetFileName(target.ImagePath)} → {target.Partition}" + (target.FromManualMapping ? " (вручную)" : ""));
            }

            StrategyText = $"{_plan.StrategyName} ({_plan.StrategyId})";
            StatusText = _plan.Plan.HasBlockingIssues
                ? "План построен, но содержит блокирующие замечания — выполнение запрещено."
                : _plan.Plan.IsDryRun
                    ? "План построен в режиме Dry Run: устройство не будет изменено."
                    : "План построен. Проверьте список операций и подтвердите выполнение.";

            OnPropertyChanged(nameof(PlanTitle));
            OnPropertyChanged(nameof(PlanSummary));
            OnPropertyChanged(nameof(CanExecute));
            OnPropertyChanged(nameof(HasBlocking));
            Log.Info(Title, $"План прошивки: {StrategyText}, шагов {PlanSteps.Count}, блокирующих замечаний {_plan.Plan.Checks.Count(c => c.Severity == CompatibilitySeverity.Blocking)}.");
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task RunDryRunAsync()
    {
        if (_plan is null)
        {
            return;
        }

        var dryPlan = _plan;
        if (!dryPlan.Plan.IsDryRun)
        {
            var context = new FlashPlanContext
            {
                Device = SelectedDevice!,
                Package = SelectedPackage!,
                Options = new FlashOptions
                {
                    DryRun = true,
                    AllowDeviceModification = false,
                    AllowUnknownBootloader = AllowUnknownBootloader,
                    VerifyIntegrity = VerifyIntegrity,
                    RebootAfter = false,
                    ManualImageMapping = ParseMapping()
                },
                Adb = _adb,
                Fastboot = _fastboot,
                Extractor = _extractor,
                Analyzer = _analyzer,
                Log = Log
            };

            dryPlan = await _planner.BuildPlanAsync(context).ConfigureAwait(true);
        }

        var job = _jobs.Enqueue(dryPlan.Job);
        StatusText = $"Dry Run добавлен в очередь (задание {job.Id.ToString()[..8]}). Устройство не изменяется.";
        Log.Info(Title, "Запущен Dry Run: шаги выполняются без команд записи.");
    }

    private async Task ExecuteAsync()
    {
        if (_plan is null || SelectedDevice is null)
        {
            return;
        }

        if (_settings.Current.ReadOnlyMode)
        {
            Dialogs.Warn("Только чтение", "В настройках включён режим только чтения. Отключите его, чтобы разрешить реальную запись.");
            return;
        }

        if (_plan.Plan.HasBlockingIssues)
        {
            Dialogs.Warn("Выполнение запрещено", "План содержит блокирующие замечания. Устраните их и постройте план заново.");
            return;
        }

        if (_plan.Plan.IsDryRun)
        {
            await RunDryRunAsync().ConfigureAwait(true);
            return;
        }

        if (!_plan.RequiresExplicitConfirmation)
        {
            Dialogs.Warn("Выполнение", "План не содержит операций, изменяющих устройство.");
            return;
        }

        var confirmed = _settings.Current.RequireSerialConfirmation && SelectedDevice.Serial is not null
            ? Dialogs.ConfirmWithSerial(
                "Подтверждение прошивки",
                $"Будет выполнена запись на устройство {SelectedDevice.DisplayName} ({SelectedDevice.ModeText}).\n" +
                "Прерывание операции может привести к неработоспособному устройству. Убедитесь, что выбрано правильное устройство.",
                SelectedDevice.Serial)
            : Dialogs.Confirm("Подтверждение прошивки",
                $"Выполнить запись на {SelectedDevice.DisplayName}? Операция изменяет устройство.", danger: true);

        if (!confirmed)
        {
            Log.Warn(Title, "Операция отменена пользователем на этапе подтверждения.");
            return;
        }

        var job = _jobs.Enqueue(_plan.Job);
        StatusText = $"Операция добавлена в очередь (задание {job.Id.ToString()[..8]}). Прогресс — в нижней панели.";
        Log.Warn(Title, $"Запущена реальная операция прошивки: {_plan.StrategyName}.");
        await Task.CompletedTask.ConfigureAwait(true);
    }
}
