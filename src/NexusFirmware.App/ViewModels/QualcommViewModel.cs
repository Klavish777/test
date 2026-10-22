using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Qualcomm;

namespace NexusFirmware.App.ViewModels;

public sealed class QualcommViewModel : PageViewModelBase
{
    private readonly QualcommService _service;
    private readonly DeviceSession _session;
    private readonly ReportService _reports;
    private string _packageDirectory = "";
    private bool _isBusy;
    private string _status = "Выберите каталог сервисного пакета (rawprogram XML, programmer-файлы).";
    private string _report = "";
    private QualcommPackageAnalysis? _analysis;

    public QualcommViewModel(QualcommService service, DeviceSession session, ReportService reports, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _service = service;
        _session = session;
        _reports = reports;
        _session.DevicesChanged += (_, _) => RefreshDevices();

        BrowseCommand = new RelayCommand(Browse);
        AnalyzeCommand = new AsyncRelayCommand(AnalyzeAsync, () => !IsBusy && !string.IsNullOrWhiteSpace(PackageDirectory), ex => Handle("Анализ пакета Qualcomm", ex));
        SaveReportCommand = new RelayCommand(SaveReport, () => _analysis is not null);
        RefreshDevicesCommand = new RelayCommand(RefreshDevices);

        RefreshDevices();
    }

    public override string Title => "Сервис Qualcomm";

    public ObservableCollection<DeviceInfo> EdlDevices { get; } = new();

    public ObservableCollection<QualcommFileInfo> Files { get; } = new();

    public ObservableCollection<CompatibilityItem> Checks { get; } = new();

    public ObservableCollection<string> Warnings { get; } = new();

    public ObservableCollection<string> Limitations { get; } = new()
    {
        "Протокол Firehose/EDL в приложении не реализован — диагностика и подготовка отчёта, не прошивка.",
        "Programmer-файлы (.mbn/.elf) не проверяются на подлинность: используйте только официальные источники.",
        "Запись возможна только авторизованным внешним инструментом (например, QFIL) с соответствующими правами.",
        "Приложение не обходит проверки подписи и не использует неподтверждённые programmer-файлы."
    };

    public string PackageDirectory
    {
        get => _packageDirectory;
        set => SetProperty(ref _packageDirectory, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
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

    public RelayCommand BrowseCommand { get; }

    public AsyncRelayCommand AnalyzeCommand { get; }

    public RelayCommand SaveReportCommand { get; }

    public RelayCommand RefreshDevicesCommand { get; }

    public override void OnActivated() => RefreshDevices();

    private void RefreshDevices()
    {
        EdlDevices.Clear();
        foreach (var device in _service.FindEdlDevices(_session.Devices))
        {
            EdlDevices.Add(device);
        }

        Status = EdlDevices.Count == 0
            ? "Устройства в режиме EDL (9008) не обнаружены. Показаны только реально найденные интерфейсы."
            : $"Обнаружено устройств EDL: {EdlDevices.Count}.";
    }

    private void Browse()
    {
        var folder = Dialogs.PickFolder("Каталог сервисного пакета Qualcomm");
        if (folder is not null)
        {
            PackageDirectory = folder;
        }
    }

    private async Task AnalyzeAsync()
    {
        IsBusy = true;
        Status = "Анализ пакета…";
        try
        {
            _analysis = await _service.AnalyzePackageAsync(PackageDirectory, computeHashes: true).ConfigureAwait(true);

            Files.Clear();
            foreach (var file in _analysis.Files)
            {
                Files.Add(file);
            }

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

            Report = _service.BuildServiceReport(_analysis, _session.SelectedDevice);
            Status = $"Файлов: {Files.Count}, планов rawprogram: {_analysis.RawPrograms.Count}, programmer: {(_analysis.HasProgrammer ? "найден" : "нет")}.";
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

        var path = _reports.SaveText("Qualcomm_Service_Report", Report);
        Status = "Отчёт сохранён: " + path;
        ReportService.OpenInExplorer(path);
    }
}
