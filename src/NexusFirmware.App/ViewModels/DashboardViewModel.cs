using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection;
using NexusFirmware.Firmware.Library;
using NexusFirmware.Infrastructure.Configuration;
using NexusFirmware.Infrastructure.Data;

namespace NexusFirmware.App.ViewModels;

public sealed class DashboardViewModel : PageViewModelBase
{
    private readonly DeviceDiscoveryService _discovery;
    private readonly DeviceSession _session;
    private readonly FirmwareLibrary _library;
    private readonly SettingsService _settings;
    private readonly ReportService _reports;
    private int _deviceCount;
    private int _firmwareCount;
    private string _freeSpace = "—";
    private string _adbState = "проверка";
    private string _fastbootState = "проверка";
    private string _deviceSummary = "Устройство не выбрано";
    private string _libraryRoot = "—";

    public DashboardViewModel(
        DeviceDiscoveryService discovery,
        DeviceSession session,
        FirmwareLibrary library,
        SettingsService settings,
        ReportService reports,
        ILogBus log,
        DialogService dialogs)
        : base(log, dialogs)
    {
        _discovery = discovery;
        _session = session;
        _library = library;
        _settings = settings;
        _reports = reports;

        RefreshCommand = new AsyncRelayCommand(RefreshAsync, onError: ex => Handle("Обновление панели", ex));
        OpenFirmwareCommand = new RelayCommand(() => AppNavigation.Request("firmware"));
        OpenDevicesCommand = new RelayCommand(() => AppNavigation.Request("devices"));
        OpenFlashingCommand = new RelayCommand(() => AppNavigation.Request("flashing"));
        OpenLogsCommand = new RelayCommand(() => AppNavigation.Request("logs"));
        OpenReportsFolderCommand = new RelayCommand(() => ReportService.OpenInExplorer(_reports.ReportsDirectory));
    }

    public override string Title => "Панель управления";

    public ObservableCollection<ReportSummary> RecentReports { get; } = new();

    public ObservableCollection<string> QuickFacts { get; } = new();

    public AsyncRelayCommand RefreshCommand { get; }

    public RelayCommand OpenFirmwareCommand { get; }

    public RelayCommand OpenDevicesCommand { get; }

    public RelayCommand OpenFlashingCommand { get; }

    public RelayCommand OpenLogsCommand { get; }

    public RelayCommand OpenReportsFolderCommand { get; }

    public int DeviceCount
    {
        get => _deviceCount;
        private set => SetProperty(ref _deviceCount, value);
    }

    public int FirmwareCount
    {
        get => _firmwareCount;
        private set => SetProperty(ref _firmwareCount, value);
    }

    public string FreeSpace
    {
        get => _freeSpace;
        private set => SetProperty(ref _freeSpace, value);
    }

    public string AdbState
    {
        get => _adbState;
        private set => SetProperty(ref _adbState, value);
    }

    public string FastbootState
    {
        get => _fastbootState;
        private set => SetProperty(ref _fastbootState, value);
    }

    public string DeviceSummary
    {
        get => _deviceSummary;
        private set => SetProperty(ref _deviceSummary, value);
    }

    public string LibraryRoot
    {
        get => _libraryRoot;
        private set => SetProperty(ref _libraryRoot, value);
    }

    public string ReadOnlyState => _settings.Current.ReadOnlyMode
        ? "Режим только чтения включён — запись на устройство заблокирована настройками."
        : "Режим только чтения выключен — операции записи требуют отдельного подтверждения.";

    public string Disclaimer =>
        "NEXUS Firmware Studio не является клоном UnlockTool, Chimera, EFT Pro или TSM Pro. " +
        "Закрытые сервисные протоколы (Odin, Firehose, BROM) не реализованы: такие операции выполняются только " +
        "официальными инструментами производителя. Приложение не обходит проверки подписи, блокировки аккаунтов и " +
        "не извлекает личные данные пользователя.";

    public override void OnActivated() => _ = RefreshAsync();

    public Task RefreshAsync()
    {
        try
        {
            var packages = _library.GetPackages();
            FirmwareCount = packages.Count;

            var root = _settings.Current.FirmwareLibraryRoot ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            var (free, driveRoot) = FirmwareLibrary.GetFreeSpace(root);
            FreeSpace = free > 0 ? $"{SizeFormatting.HumanReadable(free)} свободно на {driveRoot}" : "нет данных";
            LibraryRoot = root;

            AdbState = _discovery.AdbAvailable ? "доступен" : "не найден (нужны Android Platform Tools)";
            FastbootState = _discovery.FastbootAvailable ? "доступен" : "не найден";
            DeviceCount = _session.Devices.Count;
            DeviceSummary = _session.SelectedDevice is null
                ? "Устройство не выбрано — подключите смартфон в режиме ADB или Fastboot"
                : $"{_session.SelectedDevice.DisplayName} · {_session.SelectedDevice.ModeText} · {_session.SelectedDevice.ConnectionText}";

            RecentReports.Clear();
            foreach (var report in _reports.GetRecentReports().Take(6))
            {
                RecentReports.Add(report);
            }

            QuickFacts.Clear();
            QuickFacts.Add($"Прошивок в каталоге: {packages.Count}");
            QuickFacts.Add($"Демонстрационных записей: 0 (данные не выдумываются)");
            QuickFacts.Add($"Платформа: {Environment.OSVersion.VersionString}");
            QuickFacts.Add($"Каталог данных: {Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "NexusFirmwareStudio")}");
            QuickFacts.Add($"Драйверы ADB: {(_discovery.AdbAvailable ? "инструменты найдены" : "не найдены")}");

            OnPropertyChanged(nameof(ReadOnlyState));
        }
        catch (Exception ex)
        {
            Handle("Обновление панели", ex);
        }

        return Task.CompletedTask;
    }
}
