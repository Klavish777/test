using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Text;
using System.Windows.Data;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;

namespace NexusFirmware.App.ViewModels;

public sealed class LogsViewModel : PageViewModelBase
{
    private readonly ILogBus _logBus;
    private readonly ReportService _reports;
    private string _filterText = "";
    private string _status = "Журнал текущей сессии.";

    public LogsViewModel(ILogBus logBus, ReportService reports, DialogService dialogs)
        : base(logBus, dialogs)
    {
        _logBus = logBus;
        _reports = reports;
        EntriesView = CollectionViewSource.GetDefaultView(Entries);
        EntriesView.Filter = FilterEntry;

        foreach (var entry in logBus.Recent)
        {
            Entries.Add(entry);
        }

        logBus.Appended += (_, entry) =>
        {
            if (System.Windows.Application.Current?.Dispatcher is { } dispatcher && !dispatcher.CheckAccess())
            {
                dispatcher.BeginInvoke(new Action(() => Add(entry)));
            }
            else
            {
                Add(entry);
            }
        };

        ClearCommand = new RelayCommand(() =>
        {
            Entries.Clear();
            _logBus.Clear();
            Status = "Журнал очищен (файловые журналы сохранены).";
        });
        ExportCommand = new RelayCommand(Export);
        RefreshReportsCommand = new RelayCommand(LoadReports);
        OpenReportsFolderCommand = new RelayCommand(() => ReportService.OpenInExplorer(_reports.ReportsDirectory));
        OpenLogsFolderCommand = new RelayCommand(() => ReportService.OpenInExplorer(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "NexusFirmwareStudio", "logs")));

        LoadReports();
    }

    public override string Title => "Журналы и диагностика";

    public ObservableCollection<LogEntry> Entries { get; } = new();

    public ICollectionView EntriesView { get; }

    public ObservableCollection<ReportSummary> Reports { get; } = new();

    public string FilterText
    {
        get => _filterText;
        set
        {
            if (SetProperty(ref _filterText, value))
            {
                EntriesView.Refresh();
            }
        }
    }

    public string Status
    {
        get => _status;
        private set => SetProperty(ref _status, value);
    }

    public string EntriesCountText => $"Записей: {Entries.Count} · показано: {EntriesView.Cast<object>().Count()}";

    public RelayCommand ClearCommand { get; }

    public RelayCommand ExportCommand { get; }

    public RelayCommand RefreshReportsCommand { get; }

    public RelayCommand OpenReportsFolderCommand { get; }

    public RelayCommand OpenLogsFolderCommand { get; }

    public override void OnActivated() => LoadReports();

    private void Add(LogEntry entry)
    {
        Entries.Add(entry);
        while (Entries.Count > 2000)
        {
            Entries.RemoveAt(0);
        }

        OnPropertyChanged(nameof(EntriesCountText));
    }

    private bool FilterEntry(object item)
    {
        if (item is not LogEntry entry)
        {
            return false;
        }

        if (string.IsNullOrWhiteSpace(FilterText))
        {
            return true;
        }

        return (entry.Message + " " + entry.Source).Contains(FilterText, StringComparison.OrdinalIgnoreCase);
    }

    private void LoadReports()
    {
        Reports.Clear();
        foreach (var report in _reports.GetRecentReports())
        {
            Reports.Add(report);
        }

        Status = $"Отчётов в базе: {Reports.Count}.";
    }

    private void Export()
    {
        var path = Dialogs.SaveFile("Экспорт журнала", $"nexus_log_{DateTimeOffset.Now:yyyyMMdd_HHmmss}.txt", "Текст (*.txt)|*.txt");
        if (path is null)
        {
            return;
        }

        var builder = new StringBuilder();
        foreach (var entry in EntriesView.Cast<LogEntry>())
        {
            builder.AppendLine($"{entry.Timestamp:yyyy-MM-dd HH:mm:ss.fff} [{entry.LevelText}] {entry.Source}: {entry.Message}");
        }

        try
        {
            File.WriteAllText(path, builder.ToString());
            Status = "Журнал экспортирован: " + path;
        }
        catch (Exception ex)
        {
            Handle("Экспорт журнала", ex);
        }
    }
}
