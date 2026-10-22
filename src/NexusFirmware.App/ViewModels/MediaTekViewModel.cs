using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.MediaTek;

namespace NexusFirmware.App.ViewModels;

public sealed class MediaTekViewModel : PageViewModelBase
{
    private readonly MediaTekService _service;
    private readonly DeviceSession _session;
    private readonly ReportService _reports;
    private string _packageDirectory = "";
    private string _status = "Выберите каталог пакета MediaTek (scatter-файл + образы).";
    private string _report = "";
    private bool _isBusy;
    private MtkPackageAnalysis? _analysis;

    public MediaTekViewModel(MediaTekService service, DeviceSession session, ReportService reports, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _service = service;
        _session = session;
        _reports = reports;
        _session.DevicesChanged += (_, _) => RefreshDevices();

        BrowseCommand = new RelayCommand(Browse);
        AnalyzeCommand = new AsyncRelayCommand(AnalyzeAsync, () => !IsBusy && !string.IsNullOrWhiteSpace(PackageDirectory), ex => Handle("Анализ пакета MediaTek", ex));
        SaveReportCommand = new RelayCommand(SaveReport, () => _analysis is not null);
        RefreshDevicesCommand = new RelayCommand(RefreshDevices);

        RefreshDevices();
    }

    public override string Title => "Сервис MediaTek";

    public ObservableCollection<DeviceInfo> Devices { get; } = new();

    public ObservableCollection<PartitionRow> Partitions { get; } = new();

    public ObservableCollection<CompatibilityItem> Checks { get; } = new();

    public ObservableCollection<string> Warnings { get; } = new();

    public ObservableCollection<string> AuthorizationRequirements { get; } = new();

    public ObservableCollection<string> PlanSteps { get; } = new();

    public ObservableCollection<string> Limitations { get; } = new()
    {
        "Протокол BROM/Preloader не реализован: приложение выполняет анализ и подготовку пакета.",
        "Secure Boot, SLA и DAA не обходятся: при необходимости будет показано требование официальной авторизации.",
        "Запись выполняется только SP Flash Tool (или другим официальным инструментом) с совместимым DA-файлом.",
        "Scatter-файл не гарантирует совместимость с конкретным устройством: проверяйте платформу и проект."
    };

    public string PackageDirectory
    {
        get => _packageDirectory;
        set => SetProperty(ref _packageDirectory, value);
    }

    public string Status
    {
        get => _status;
        private set => SetProperty(ref _status, value);
    }

    public string Report
    {
        get => _report;
        private set => SetProperty(ref _report, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public RelayCommand BrowseCommand { get; }

    public AsyncRelayCommand AnalyzeCommand { get; }

    public RelayCommand SaveReportCommand { get; }

    public RelayCommand RefreshDevicesCommand { get; }

    public override void OnActivated() => RefreshDevices();

    private void RefreshDevices()
    {
        Devices.Clear();
        foreach (var device in _service.FindMediaTekDevices(_session.Devices))
        {
            Devices.Add(device);
        }

        AuthorizationRequirements.Clear();
        foreach (var requirement in _service.DescribeAuthorizationRequirements(Devices.FirstOrDefault()))
        {
            AuthorizationRequirements.Add(requirement);
        }

        if (Devices.Count == 0)
        {
            Status = "Устройства MediaTek в сервисных режимах не обнаружены (проверено USB-перечисление).";
        }
    }

    private void Browse()
    {
        var folder = Dialogs.PickFolder("Каталог пакета MediaTek");
        if (folder is not null)
        {
            PackageDirectory = folder;
        }
    }

    private async Task AnalyzeAsync()
    {
        IsBusy = true;
        Status = "Анализ scatter-пакета…";
        try
        {
            _analysis = await _service.AnalyzePackageAsync(PackageDirectory, computeHashes: true).ConfigureAwait(true);

            Checks.Clear();
            foreach (var check in _analysis.Checks)
            {
                Checks.Add(check);
            }

            Warnings.Clear();
            foreach (var warning in _analysis.Warnings)
            {
                Warnings.Add(warning);
            }

            Partitions.Clear();
            if (_analysis.Scatter is not null)
            {
                foreach (var partition in _analysis.Scatter.Partitions)
                {
                    Partitions.Add(new PartitionRow
                    {
                        Name = partition.PartitionName,
                        Size = partition.PartitionSize is null ? "недоступно" : SizeFormatting.HumanReadable(partition.PartitionSize.Value),
                        Source = partition.FileName ?? "—",
                        Detail = partition.OperationType
                    });
                }
            }

            PlanSteps.Clear();
            foreach (var step in _service.BuildPreparationPlan(_analysis))
            {
                PlanSteps.Add($"{step.Title}: {step.Detail}");
            }

            Report = _service.BuildReport(_analysis, _session.SelectedDevice);
            Status = $"Разделов: {Partitions.Count}, образов: {_analysis.ImageFiles.Count}, платформа: {_analysis.Scatter?.Platform ?? "не указана"}.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void SaveReport()
    {
        if (_analysis is null)
        {
            return;
        }

        var path = _reports.SaveText("MediaTek_Service_Report", Report);
        Status = "Отчёт сохранён: " + path;
        ReportService.OpenInExplorer(path);
    }
}
