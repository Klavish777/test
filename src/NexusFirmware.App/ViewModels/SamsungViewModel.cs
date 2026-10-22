using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Samsung;
using System.IO;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace NexusFirmware.App.ViewModels;

public sealed class SamsungViewModel : PageViewModelBase
{
    private readonly SamsungService _service;
    private readonly DeviceSession _session;
    private readonly ReportService _reports;
    private readonly List<string> _files = new();
    private string _status = "Добавьте файлы AP/BL/CP/CSC/HOME_CSC или цельный TAR.MD5.";
    private string _report = "";
    private bool _isBusy;
    private SamsungPackageResult? _result;

    public SamsungViewModel(SamsungService service, DeviceSession session, ReportService reports, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _service = service;
        _session = session;
        _reports = reports;
        _session.SelectionChanged += (_, _) => OnPropertyChanged(nameof(DeviceText));

        AddFilesCommand = new RelayCommand(AddFiles);
        ClearFilesCommand = new RelayCommand(() =>
        {
            _files.Clear();
            Files.Clear();
            Status = "Список файлов очищен.";
        });
        AnalyzeCommand = new AsyncRelayCommand(AnalyzeAsync, () => !IsBusy && _files.Count > 0, ex => Handle("Анализ пакета Samsung", ex));
        SaveReportCommand = new RelayCommand(SaveReport, () => _result is not null);
        RefreshDownloadDevicesCommand = new RelayCommand(RefreshDownloadDevices);

        RefreshDownloadDevices();
    }

    public override string Title => "Сервис Samsung";

    public ObservableCollection<string> Files { get; } = new();

    public ObservableCollection<DeviceInfo> DownloadModeDevices { get; } = new();

    public ObservableCollection<DeviceDetailRow> Components { get; } = new();

    public ObservableCollection<CompatibilityItem> PackageChecks { get; } = new();

    public ObservableCollection<CompatibilityItem> DeviceChecks { get; } = new();

    public ObservableCollection<DeviceDetailRow> ExternalLayout { get; } = new();

    public ObservableCollection<string> Notes { get; } = new();

    public string DeviceText => _session.SelectedDevice is null
        ? "Устройство не выбрано"
        : $"{_session.SelectedDevice.DisplayName} · {_session.SelectedDevice.ModeText}";

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

    public RelayCommand AddFilesCommand { get; }

    public RelayCommand ClearFilesCommand { get; }

    public AsyncRelayCommand AnalyzeCommand { get; }

    public RelayCommand SaveReportCommand { get; }

    public RelayCommand RefreshDownloadDevicesCommand { get; }

    public override void OnActivated()
    {
        RefreshDownloadDevices();
        OnPropertyChanged(nameof(DeviceText));
    }

    private void RefreshDownloadDevices()
    {
        DownloadModeDevices.Clear();
        foreach (var device in _service.FindDownloadModeDevices(_session.Devices))
        {
            DownloadModeDevices.Add(device);
        }
    }

    private void AddFiles()
    {
        var selected = Dialogs.PickFiles("Файлы прошивки Samsung",
            "Пакеты Samsung (*.tar;*.md5;*.tar.md5;*.zip;*.ap;*.bl;*.cp;*.csc)|*.tar;*.md5;*.tar.md5;*.zip;*.ap;*.bl;*.cp;*.csc|Все файлы (*.*)|*.*");

        foreach (var file in selected)
        {
            if (_files.Contains(file, StringComparer.OrdinalIgnoreCase))
            {
                continue;
            }

            _files.Add(file);
            Files.Add(Path.GetFileName(file));
        }

        Status = $"Файлов в пакете: {_files.Count}.";
    }

    private async Task AnalyzeAsync()
    {
        IsBusy = true;
        Status = "Анализ пакета…";
        try
        {
            var progress = new Progress<(double Percent, string Message)>(p => Status = p.Message);
            _result = await _service.AnalyzePackageAsync(_files, _session.SelectedDevice, progress).ConfigureAwait(true);

            Components.Clear();
            foreach (var component in _result.Analysis.Components)
            {
                Components.Add(new DeviceDetailRow
                {
                    Label = $"{component.Component ?? "?"} · {component.FileName}",
                    Value = $"модель {component.ModelCode ?? "—"} · PDA {component.PdaVersion ?? "—"} · binary {component.BootloaderBinary ?? "—"} · {SizeFormatting.HumanReadable(component.SizeBytes)}"
                });
            }

            PackageChecks.Clear();
            foreach (var check in _result.Analysis.Checks)
            {
                PackageChecks.Add(check);
            }

            DeviceChecks.Clear();
            foreach (var check in _result.DeviceChecks)
            {
                DeviceChecks.Add(check);
            }

            ExternalLayout.Clear();
            foreach (var (slot, fileName, size, sha) in _service.BuildExternalToolLayout(_result))
            {
                ExternalLayout.Add(new DeviceDetailRow { Label = $"{slot}: {fileName}", Value = $"{size} · SHA-256 {sha}" });
            }

            Notes.Clear();
            foreach (var note in _result.Notes)
            {
                Notes.Add(note);
            }

            Report = _service.BuildReport(_result, _session.SelectedDevice);
            Status = $"Пакет проанализирован. Модель: {_result.Analysis.ModelCode ?? "не определена"}; отсутствуют: {(_result.MissingComponents.Count == 0 ? "нет" : string.Join(", ", _result.MissingComponents))}.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void SaveReport()
    {
        if (_result is null)
        {
            return;
        }

        var path = _reports.SaveText("Samsung_Package_Report", Report);
        Status = "Отчёт сохранён: " + path;
        ReportService.OpenInExplorer(path);
    }
}
