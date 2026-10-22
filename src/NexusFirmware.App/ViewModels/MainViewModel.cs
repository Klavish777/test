using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Threading;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Jobs;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Reporting;
using NexusFirmware.DeviceDetection;
using NexusFirmware.Infrastructure.Configuration;

namespace NexusFirmware.App.ViewModels;

/// <summary>Раздел, которому нужно обновиться при открытии.</summary>
public interface IPageViewModel
{
    string Title { get; }

    void OnActivated();
}

public sealed class NavigationItem : ObservableObject
{
    private bool _isActive;

    public required string Key { get; init; }
    public required string Title { get; init; }
    public required string Glyph { get; init; }
    public required object ViewModel { get; init; }
    public string? TitleEn { get; init; }

    public bool IsActive
    {
        get => _isActive;
        set => SetProperty(ref _isActive, value);
    }
}

public sealed class JobItem : ObservableObject
{
    private string _status = "В очереди";
    private double _percent;
    private string _state = "Queued";
    private string? _currentStep;

    public required Guid Id { get; init; }
    public required string Title { get; init; }
    public required bool IsDryRun { get; init; }

    public string Status
    {
        get => _status;
        set => SetProperty(ref _status, value);
    }

    public double Percent
    {
        get => _percent;
        set => SetProperty(ref _percent, value);
    }

    public string State
    {
        get => _state;
        set => SetProperty(ref _state, value);
    }

    public string? CurrentStep
    {
        get => _currentStep;
        set => SetProperty(ref _currentStep, value);
    }

    public string ModeText => IsDryRun ? "Dry Run" : "Реальное выполнение";
}

/// <summary>Главное окно: навигация, активное устройство, очередь операций и журнал.</summary>
public sealed class MainViewModel : ObservableObject
{
    private readonly DeviceDiscoveryService _discovery;
    private readonly DeviceSession _session;
    private readonly JobQueue _jobs;
    private readonly ILogBus _log;
    private readonly SettingsService _settings;
    private readonly ReportService _reports;
    private readonly DialogService _dialogs;
    private readonly DispatcherTimer _timer;
    private readonly HashSet<Guid> _reportedJobs = new();

    private NavigationItem? _selectedNavigation;
    private object? _current;
    private bool _isRefreshing;
    private bool _isLogPanelVisible = true;
    private string _adbStatus = "ADB: проверка…";
    private string _fastbootStatus = "Fastboot: проверка…";
    private string _deviceStatus = "Устройство не выбрано";
    private string _connectionStatus = "Нет подключения";
    private string _currentJobStatus = "Нет активных задач";
    private double _currentJobProgress;
    private JobItem? _currentJob;
    private bool _isInitialized;

    public MainViewModel(
        DeviceDiscoveryService discovery,
        DeviceSession session,
        JobQueue jobs,
        ILogBus log,
        SettingsService settings,
        ReportService reports,
        DialogService dialogs,
        DashboardViewModel dashboard,
        DevicesViewModel devices,
        FirmwareViewModel firmware,
        FlashingViewModel flashing,
        AdbViewModel adb,
        QualcommViewModel qualcomm,
        MediaTekViewModel mediaTek,
        SamsungViewModel samsung,
        ExtractorViewModel extractor,
        PartitionsViewModel partitions,
        LogsViewModel logs,
        DriversViewModel drivers,
        PluginsViewModel plugins,
        SettingsViewModel settingsVm)
    {
        _discovery = discovery;
        _session = session;
        _jobs = jobs;
        _log = log;
        _settings = settings;
        _reports = reports;
        _dialogs = dialogs;

        Navigation =
        [
            new NavigationItem { Key = "dashboard", Title = "Панель управления", TitleEn = "Dashboard", Glyph = "◈", ViewModel = dashboard },
            new NavigationItem { Key = "devices", Title = "Диспетчер устройств", TitleEn = "Device Manager", Glyph = "▣", ViewModel = devices },
            new NavigationItem { Key = "firmware", Title = "Центр прошивок", TitleEn = "Firmware Center", Glyph = "▤", ViewModel = firmware },
            new NavigationItem { Key = "flashing", Title = "Станция прошивки", TitleEn = "Flashing Station", Glyph = "⇩", ViewModel = flashing },
            new NavigationItem { Key = "adb", Title = "ADB и Fastboot", TitleEn = "ADB & Fastboot", Glyph = "≫", ViewModel = adb },
            new NavigationItem { Key = "qualcomm", Title = "Сервис Qualcomm", TitleEn = "Qualcomm Service", Glyph = "Q", ViewModel = qualcomm },
            new NavigationItem { Key = "mediatek", Title = "Сервис MediaTek", TitleEn = "MediaTek Service", Glyph = "M", ViewModel = mediaTek },
            new NavigationItem { Key = "samsung", Title = "Сервис Samsung", TitleEn = "Samsung Service", Glyph = "S", ViewModel = samsung },
            new NavigationItem { Key = "extractor", Title = "Извлечение прошивок", TitleEn = "Firmware Extractor", Glyph = "⊞", ViewModel = extractor },
            new NavigationItem { Key = "partitions", Title = "Разделы", TitleEn = "Partitions", Glyph = "▥", ViewModel = partitions },
            new NavigationItem { Key = "logs", Title = "Журналы и диагностика", TitleEn = "Logs & Diagnostics", Glyph = "≡", ViewModel = logs },
            new NavigationItem { Key = "drivers", Title = "Центр драйверов", TitleEn = "Drivers Center", Glyph = "⊞", ViewModel = drivers },
            new NavigationItem { Key = "plugins", Title = "Плагины", TitleEn = "Plugins", Glyph = "◇", ViewModel = plugins },
            new NavigationItem { Key = "settings", Title = "Настройки", TitleEn = "Settings", Glyph = "⚙", ViewModel = settingsVm }
        ];

        SelectedNavigation = Navigation[0];

        _log.Appended += OnLogAppended;
        _session.SelectionChanged += (_, _) => OnDeviceSelectionChanged();
        _session.DevicesChanged += (_, _) => OnDevicesChanged();
        _jobs.JobChanged += OnJobChanged;
        _settings.Changed += (_, _) => ApplySettings();

        _timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(Math.Max(3, _settings.Current.DeviceRefreshSeconds)) };
        _timer.Tick += async (_, _) => await RefreshDevicesAsync(silent: true).ConfigureAwait(true);

        foreach (var entry in _log.Recent)
        {
            LogEntries.Add(entry);
        }
    }

    public ObservableCollection<NavigationItem> Navigation { get; }

    public ObservableCollection<LogEntry> LogEntries { get; } = new();

    public ObservableCollection<JobItem> Jobs { get; } = new();

    public ObservableCollection<ProviderStatus> ProviderStatuses { get; } = new();

    public ObservableCollection<DeviceInfo> Devices => _session.Devices;

    public string AppTitle => "NEXUS Firmware Studio";

    public string AppSubtitle => "Firmware · Diagnostics · Service";

    public string VersionText => "v" + (System.Reflection.Assembly.GetExecutingAssembly().GetName().Version?.ToString(3) ?? "1.0.0");

    public NavigationItem? SelectedNavigation
    {
        get => _selectedNavigation;
        set
        {
            if (!SetProperty(ref _selectedNavigation, value))
            {
                return;
            }

            foreach (var item in Navigation)
            {
                item.IsActive = ReferenceEquals(item, value);
            }

            Current = value?.ViewModel;
            if (value?.ViewModel is IPageViewModel page)
            {
                try
                {
                    page.OnActivated();
                }
                catch (Exception ex)
                {
                    _log.Error("UI", $"Ошибка активации раздела «{value.Title}»: {ex.Message}");
                }
            }
        }
    }

    public object? Current
    {
        get => _current;
        private set => SetProperty(ref _current, value);
    }

    public bool IsRefreshing
    {
        get => _isRefreshing;
        private set
        {
            if (SetProperty(ref _isRefreshing, value))
            {
                OnPropertyChanged(nameof(RefreshButtonText));
            }
        }
    }

    public string RefreshButtonText => IsRefreshing ? "Сканирование…" : "Обновить устройства";

    public DeviceInfo? SelectedDevice
    {
        get => _session.SelectedDevice;
        set
        {
            if (ReferenceEquals(_session.SelectedDevice, value))
            {
                return;
            }

            _session.Select(value);
        }
    }

    public string SelectedDeviceTitle => SelectedDevice is null ? "Устройство не выбрано" : SelectedDevice.DisplayName;

    public string DeviceStatus
    {
        get => _deviceStatus;
        private set => SetProperty(ref _deviceStatus, value);
    }

    public string ConnectionStatus
    {
        get => _connectionStatus;
        private set => SetProperty(ref _connectionStatus, value);
    }

    public string AdbStatus
    {
        get => _adbStatus;
        private set => SetProperty(ref _adbStatus, value);
    }

    public string FastbootStatus
    {
        get => _fastbootStatus;
        private set => SetProperty(ref _fastbootStatus, value);
    }

    public bool IsLogPanelVisible
    {
        get => _isLogPanelVisible;
        set => SetProperty(ref _isLogPanelVisible, value);
    }

    public string LogPanelToggleText => IsLogPanelVisible ? "Скрыть журнал" : "Показать журнал";

    public JobItem? CurrentJob
    {
        get => _currentJob;
        private set => SetProperty(ref _currentJob, value);
    }

    public string CurrentJobStatus
    {
        get => _currentJobStatus;
        private set => SetProperty(ref _currentJobStatus, value);
    }

    public double CurrentJobProgress
    {
        get => _currentJobProgress;
        private set => SetProperty(ref _currentJobProgress, value);
    }

    public bool HasActiveJob => CurrentJob is not null && CurrentJob.State is "Running" or "Queued";

    public string SettingsSummary => $"Режим только чтения: {(_settings.Current.ReadOnlyMode ? "вкл." : "выкл.")} · Язык: {(_settings.Current.IsRussian ? "RU" : "EN")}";

    public RelayCommand RefreshDevicesCommand => new(async () => await RefreshDevicesAsync(silent: false), () => !IsRefreshing);

    public RelayCommand ToggleLogPanelCommand => new(() =>
    {
        IsLogPanelVisible = !IsLogPanelVisible;
        OnPropertyChanged(nameof(LogPanelToggleText));
    });

    public RelayCommand ClearLogCommand => new(() =>
    {
        LogEntries.Clear();
    });

    public RelayCommand CancelJobCommand => new(() =>
    {
        if (CurrentJob is null)
        {
            return;
        }

        if (!_jobs.Cancel(CurrentJob.Id))
        {
            _dialogs.Warn("Отмена недоступна", "Отмена невозможна: операция уже завершена или находится на неразрывном шаге (например, запись раздела).");
        }
    }, () => CurrentJob is not null && HasActiveJob);

    public RelayCommand NavigateCommand => new(parameter =>
    {
        if (parameter is NavigationItem item)
        {
            SelectedNavigation = item;
        }
    });

    public RelayCommand OpenReportsCommand => new(() => ReportService.OpenInExplorer(_reports.ReportsDirectory));

    public RelayCommand OpenLogsCommand => new(() =>
        ReportService.OpenInExplorer(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "NexusFirmwareStudio", "logs")));

    public async Task InitializeAsync()
    {
        if (_isInitialized)
        {
            return;
        }

        _isInitialized = true;
        ApplySettings();
        _timer.Start();
        await RefreshDevicesAsync(silent: true).ConfigureAwait(true);
    }

    private void ApplySettings()
    {
        _timer.Interval = TimeSpan.FromSeconds(Math.Max(3, _settings.Current.DeviceRefreshSeconds));
        OnPropertyChanged(nameof(SettingsSummary));

        if (_settings.Current.DeviceRefreshSeconds <= 0)
        {
            _timer.Stop();
        }
        else if (_isInitialized)
        {
            _timer.Start();
        }
    }

    private async Task RefreshDevicesAsync(bool silent)
    {
        if (IsRefreshing)
        {
            return;
        }

        IsRefreshing = true;
        try
        {
            var snapshot = await _discovery.ScanAsync().ConfigureAwait(true);
            _session.ReplaceDevices(snapshot.Devices);

            ProviderStatuses.Clear();
            foreach (var status in snapshot.Providers)
            {
                ProviderStatuses.Add(status);
            }

            var adb = snapshot.Providers.FirstOrDefault(p => p.ProviderId == "adb");
            var fastboot = snapshot.Providers.FirstOrDefault(p => p.ProviderId == "fastboot");

            AdbStatus = adb is null || !adb.Available ? "ADB: нет" : _discovery.AdbAvailable ? "ADB: OK" : "ADB: ошибка";
            FastbootStatus = fastboot is null || !fastboot.Available ? "Fastboot: нет" : _discovery.FastbootAvailable ? "Fastboot: OK" : "Fastboot: ошибка";

            if (!silent)
            {
                _log.Info("Devices", $"Сканирование завершено: устройств {snapshot.Devices.Count}.");
            }
        }
        catch (Exception ex)
        {
            _log.Error("Devices", "Ошибка сканирования устройств: " + ex.Message);
            if (!silent)
            {
                _dialogs.Error("Сканирование устройств", ex.Message);
            }
        }
        finally
        {
            IsRefreshing = false;
            OnDevicesChanged();
        }
    }

    private void OnLogAppended(object? sender, LogEntry entry)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null || dispatcher.CheckAccess())
        {
            AppendLog(entry);
            return;
        }

        dispatcher.BeginInvoke(new Action(() => AppendLog(entry)));
    }

    private void AppendLog(LogEntry entry)
    {
        LogEntries.Add(entry);
        while (LogEntries.Count > 1500)
        {
            LogEntries.RemoveAt(0);
        }
    }

    private void OnDevicesChanged()
    {
        var device = _session.SelectedDevice;
        DeviceStatus = device is null
            ? $"Устройств: {_session.Devices.Count} · устройство не выбрано"
            : $"{device.DisplayName} · {device.ModeText}";

        ConnectionStatus = device switch
        {
            null => "Нет подключения",
            { Connection: ConnectionState.Connected } => "Подключено",
            { Connection: ConnectionState.Unauthorized } => "Ожидает подтверждения ADB",
            { Connection: ConnectionState.NoPermissions } => "Нет прав доступа",
            _ => "Нет связи"
        };

        OnPropertyChanged(nameof(SelectedDeviceTitle));
        OnPropertyChanged(nameof(SelectedDevice));
    }

    private void OnDeviceSelectionChanged()
    {
        OnPropertyChanged(nameof(SelectedDevice));
        OnPropertyChanged(nameof(SelectedDeviceTitle));
        OnDevicesChanged();
    }

    private void OnJobChanged(object? sender, JobStateChangedEventArgs e)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is not null && !dispatcher.CheckAccess())
        {
            dispatcher.BeginInvoke(new Action(() => ApplyJobState(e.Job)));
            return;
        }

        ApplyJobState(e.Job);
    }

    private void ApplyJobState(JobRun run)
    {
        var item = Jobs.FirstOrDefault(j => j.Id == run.Id);
        if (item is null)
        {
            item = new JobItem { Id = run.Id, Title = run.Request.Title, IsDryRun = run.Request.IsDryRun };
            Jobs.Insert(0, item);
        }

        item.Status = run.StatusMessage;
        item.Percent = run.Percent;
        item.State = run.State.ToString();
        item.CurrentStep = run.CurrentStep;

        if (!run.IsTerminal)
        {
            CurrentJob = item;
            CurrentJobStatus = run.StatusMessage;
            CurrentJobProgress = run.Percent;
        }
        else
        {
            CurrentJobStatus = $"{run.Request.Title}: {ReportWriter.StateText(run.State)}";
            if (run.State == OperationState.Succeeded)
            {
                CurrentJobProgress = 100;
            }

            CurrentJob = null;

            if (_reportedJobs.Add(run.Id))
            {
                try
                {
                    var report = _jobs.BuildReport(run);
                    var saved = _reports.Save(report);
                    _log.Info("Reports", $"Отчёт операции сохранён: {Path.GetFileName(saved.MarkdownPath)}");
                }
                catch (Exception ex)
                {
                    _log.Error("Reports", "Не удалось сохранить отчёт: " + ex.Message);
                }
            }
        }

        OnPropertyChanged(nameof(HasActiveJob));
    }
}
