using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Extractor;
using System.IO;
using System.Threading.Tasks;

namespace NexusFirmware.App.ViewModels;

public sealed class ExtractorViewModel : PageViewModelBase
{
    private readonly FirmwareAnalyzer _analyzer;
    private readonly FirmwareExtractorService _extractor;
    private string _sourcePath = "";
    private string _summary = "Файл не выбран.";
    private string _progressText = "";
    private string _lastOutputDirectory = "";
    private bool _isBusy;
    private bool _computeHash;
    private FirmwareAnalysis? _analysis;

    public ExtractorViewModel(FirmwareAnalyzer analyzer, FirmwareExtractorService extractor, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _analyzer = analyzer;
        _extractor = extractor;

        PickFileCommand = new RelayCommand(PickFile);
        AnalyzeCommand = new AsyncRelayCommand(AnalyzeAsync, () => !IsBusy && !string.IsNullOrWhiteSpace(SourcePath), ex => Handle("Анализ прошивки", ex));
        ExtractCommand = new AsyncRelayCommand(ExtractAsync, () => !IsBusy && !string.IsNullOrWhiteSpace(SourcePath), ex => Handle("Извлечение прошивки", ex));
        ExportJsonCommand = new RelayCommand(() => Export(".json"), () => _analysis is not null);
        ExportCsvCommand = new RelayCommand(() => Export(".csv"), () => _analysis is not null);
        OpenOutputCommand = new RelayCommand(() =>
        {
            if (!string.IsNullOrWhiteSpace(LastOutputDirectory))
            {
                ReportService.OpenInExplorer(LastOutputDirectory);
            }
        });
        ClearCommand = new RelayCommand(() =>
        {
            Sections.Clear();
            Warnings.Clear();
            Limitations.Clear();
            _analysis = null;
            Summary = "Файл не выбран.";
        });
    }

    public override string Title => "Извлечение прошивок";

    public ObservableCollection<AnalysisSection> Sections { get; } = new();

    public ObservableCollection<string> Warnings { get; } = new();

    public bool HasWarnings => Warnings.Count > 0;

    public ObservableCollection<string> Limitations { get; } = new();

    public string SourcePath
    {
        get => _sourcePath;
        set => SetProperty(ref _sourcePath, value);
    }

    public string Summary
    {
        get => _summary;
        private set => SetProperty(ref _summary, value);
    }

    public string ProgressText
    {
        get => _progressText;
        private set => SetProperty(ref _progressText, value);
    }

    public string LastOutputDirectory
    {
        get => _lastOutputDirectory;
        private set => SetProperty(ref _lastOutputDirectory, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public bool ComputeHash
    {
        get => _computeHash;
        set => SetProperty(ref _computeHash, value);
    }

    public RelayCommand PickFileCommand { get; }

    public AsyncRelayCommand AnalyzeCommand { get; }

    public AsyncRelayCommand ExtractCommand { get; }

    public RelayCommand ExportJsonCommand { get; }

    public RelayCommand ExportCsvCommand { get; }

    public RelayCommand OpenOutputCommand { get; }

    public RelayCommand ClearCommand { get; }

    private void PickFile()
    {
        var path = Dialogs.PickFile("Файл прошивки для анализа",
            "Прошивки (*.zip;*.tar;*.md5;*.tar.md5;*.gz;*.lz4;*.img;*.bin;*.xml;*.txt)|*.zip;*.tar;*.md5;*.tar.md5;*.gz;*.lz4;*.img;*.bin;*.xml;*.txt|Все файлы (*.*)|*.*");

        if (path is not null)
        {
            SourcePath = path;
            _ = AnalyzeAsync();
        }
    }

    private async Task AnalyzeAsync()
    {
        IsBusy = true;
        ProgressText = "Анализ файла…";
        try
        {
            var path = SourcePath;
            var computeHash = ComputeHash;
            var analysis = await Task.Run(() => _analyzer.Inspect(path, computeHash)).ConfigureAwait(true);

            _analysis = analysis;
            Sections.Clear();
            foreach (var section in analysis.Sections)
            {
                Sections.Add(section);
            }

            Warnings.Clear();
            foreach (var warning in analysis.Warnings)
            {
                Warnings.Add(warning);
            }

            Limitations.Clear();
            foreach (var limitation in analysis.Limitations)
            {
                Limitations.Add(limitation);
            }

            OnPropertyChanged(nameof(HasWarnings));
            Summary = analysis.Summary;
            ProgressText = "Анализ завершён. Оригинальный файл не изменялся.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task ExtractAsync()
    {
        var destination = Dialogs.PickFolder("Куда извлечь содержимое? Рекомендуется отдельный каталог");
        if (destination is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var progress = new Progress<(double Percent, string Message)>(p =>
            {
                ProgressText = $"{p.Percent:0}% · {p.Message}";
            });

            var files = await _extractor.ExtractAsync(SourcePath, destination, progress).ConfigureAwait(true);
            LastOutputDirectory = destination;
            ProgressText = $"Извлечено файлов: {files.Count}. Каталог: {destination}";
            Notify($"Извлечение завершено: {files.Count} файл(ов).");
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void Export(string extension)
    {
        if (_analysis is null)
        {
            return;
        }

        var defaultName = Path.GetFileNameWithoutExtension(_analysis.FileName) + "_analysis" + extension;
        var filter = extension == ".json" ? "JSON (*.json)|*.json" : "CSV (*.csv)|*.csv";
        var path = Dialogs.SaveFile("Экспорт результатов анализа", defaultName, filter);
        if (path is null)
        {
            return;
        }

        try
        {
            File.WriteAllText(path, extension == ".json" ? FirmwareAnalyzer.ToJson(_analysis) : FirmwareAnalyzer.ToCsv(_analysis));
            ProgressText = "Результат сохранён: " + path;
            Notify("Экспорт анализа: " + Path.GetFileName(path));
        }
        catch (Exception ex)
        {
            Handle("Экспорт анализа", ex);
        }
    }
}
