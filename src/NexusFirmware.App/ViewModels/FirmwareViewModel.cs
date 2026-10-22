using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows.Data;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Comparison;
using NexusFirmware.Firmware.Library;
using NexusFirmware.Infrastructure.Configuration;

namespace NexusFirmware.App.ViewModels;

public sealed class NoteItem
{
    public required long Id { get; init; }
    public required DateTimeOffset CreatedAt { get; init; }
    public required string Text { get; init; }
    public string CreatedText => CreatedAt.ToLocalTime().ToString("yyyy-MM-dd HH:mm");
}

public sealed class FirmwareViewModel : PageViewModelBase
{
    private readonly FirmwareLibrary _library;
    private readonly DeviceSession _session;
    private readonly SettingsService _settings;
    private string _searchText = string.Empty;
    private string _selectedManufacturer = "Все";
    private FirmwarePackage? _selectedPackage;
    private FirmwarePackage? _leftPackage;
    private FirmwarePackage? _rightPackage;
    private string _noteDraft = string.Empty;
    private bool _isBusy;
    private string _busyText = string.Empty;
    private string _freeSpaceText = "—";
    private string _libraryRoot = "—";
    private VersionComparison? _comparison;
    private string _importStatus = "Файлы не импортированы в этой сессии.";

    public FirmwareViewModel(
        FirmwareLibrary library,
        DeviceSession session,
        SettingsService settings,
        ILogBus log,
        DialogService dialogs)
        : base(log, dialogs)
    {
        _library = library;
        _session = session;
        _settings = settings;

        PackagesView = CollectionViewSource.GetDefaultView(AllPackages);
        PackagesView.Filter = FilterPackage;

        ImportFileCommand = new AsyncRelayCommand(ImportFileAsync, () => !IsBusy, ex => Handle("Импорт прошивки", ex));
        ImportFolderCommand = new AsyncRelayCommand(ImportFolderAsync, () => !IsBusy, ex => Handle("Импорт каталога", ex));
        VerifyHashCommand = new AsyncRelayCommand(VerifyHashAsync, () => SelectedPackage is not null && !IsBusy, ex => Handle("Проверка SHA-256", ex));
        RemoveCommand = new RelayCommand(RemoveSelected, () => SelectedPackage is not null);
        AddNoteCommand = new RelayCommand(AddNote, () => SelectedPackage is not null && !string.IsNullOrWhiteSpace(NoteDraft));
        CheckCompatibilityCommand = new RelayCommand(CheckCompatibility, () => SelectedPackage is not null);
        CompareCommand = new RelayCommand(ComparePackages, () => LeftPackage is not null && RightPackage is not null);
        RefreshCommand = new RelayCommand(Reload, () => !IsBusy);
        OpenFlashingCommand = new RelayCommand(() => AppNavigation.Request("flashing"));
        OpenFolderCommand = new RelayCommand(() =>
        {
            var root = _settings.Current.FirmwareLibraryRoot;
            if (!string.IsNullOrWhiteSpace(root) && Directory.Exists(root))
            {
                ReportService.OpenInExplorer(root);
            }
            else
            {
                Dialogs.Info("Каталог прошивок", "Корневой каталог библиотеки прошивок не задан в настройках.");
            }
        });

        Reload();
    }

    public override string Title => "Центр прошивок";

    public ObservableCollection<FirmwarePackage> AllPackages { get; } = new();

    public ICollectionView PackagesView { get; }

    public ObservableCollection<DeviceDetailRow> Details { get; } = new();

    public ObservableCollection<NoteItem> Notes { get; } = new();

    public ObservableCollection<CompatibilityItem> CompatibilityChecks { get; } = new();

    public ObservableCollection<ComparisonRow> ComparisonRows { get; } = new();

    public ObservableCollection<string> OnlyInLeft { get; } = new();

    public ObservableCollection<string> OnlyInRight { get; } = new();

    public ObservableCollection<string> SizeDifferences { get; } = new();

    public ObservableCollection<string> ComparisonNotes { get; } = new();

    public ObservableCollection<string> Manufacturers { get; } = new() { "Все" };

    public FirmwarePackage? SelectedPackage
    {
        get => _selectedPackage;
        set
        {
            if (SetProperty(ref _selectedPackage, value))
            {
                OnPropertyChanged(nameof(HasSelection));
                RebuildDetails();
            }
        }
    }

    public bool HasSelection => SelectedPackage is not null;

    public string SearchText
    {
        get => _searchText;
        set
        {
            if (SetProperty(ref _searchText, value))
            {
                PackagesView.Refresh();
            }
        }
    }

    public string SelectedManufacturer
    {
        get => _selectedManufacturer;
        set
        {
            if (SetProperty(ref _selectedManufacturer, value))
            {
                PackagesView.Refresh();
            }
        }
    }

    public FirmwarePackage? LeftPackage
    {
        get => _leftPackage;
        set => SetProperty(ref _leftPackage, value);
    }

    public FirmwarePackage? RightPackage
    {
        get => _rightPackage;
        set => SetProperty(ref _rightPackage, value);
    }

    public string NoteDraft
    {
        get => _noteDraft;
        set => SetProperty(ref _noteDraft, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public string BusyText
    {
        get => _busyText;
        private set => SetProperty(ref _busyText, value);
    }

    public string FreeSpaceText
    {
        get => _freeSpaceText;
        private set => SetProperty(ref _freeSpaceText, value);
    }

    public string LibraryRoot
    {
        get => _libraryRoot;
        private set => SetProperty(ref _libraryRoot, value);
    }

    public string ImportStatus
    {
        get => _importStatus;
        private set => SetProperty(ref _importStatus, value);
    }

    public string CountText => $"Сборок: {AllPackages.Count} · отфильтровано: {PackagesView.Cast<object>().Count()}";

    public AsyncRelayCommand ImportFileCommand { get; }

    public AsyncRelayCommand ImportFolderCommand { get; }

    public AsyncRelayCommand VerifyHashCommand { get; }

    public RelayCommand RemoveCommand { get; }

    public RelayCommand AddNoteCommand { get; }

    public RelayCommand CheckCompatibilityCommand { get; }

    public RelayCommand CompareCommand { get; }

    public RelayCommand RefreshCommand { get; }

    public RelayCommand OpenFlashingCommand { get; }

    public RelayCommand OpenFolderCommand { get; }

    public override void OnActivated() => Reload();

    private bool FilterPackage(object item)
    {
        if (item is not FirmwarePackage package)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(SearchText))
        {
            var query = SearchText.Trim();
            var haystack = string.Join(' ', package.DisplayName, package.Manufacturer, package.Model, package.Version,
                package.BuildNumber, package.Region, package.Sha256, package.Codename);
            if (!haystack.Contains(query, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
        }

        if (SelectedManufacturer != "Все" && !string.Equals(package.Manufacturer, SelectedManufacturer, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        return true;
    }

    private void Reload()
    {
        var selectedId = SelectedPackage?.Id;

        AllPackages.Clear();
        foreach (var package in _library.GetPackages())
        {
            AllPackages.Add(package);
        }

        Manufacturers.Clear();
        Manufacturers.Add("Все");
        foreach (var manufacturer in AllPackages.Select(p => p.Manufacturer).Where(m => !string.IsNullOrWhiteSpace(m)).Distinct().OrderBy(m => m))
        {
            Manufacturers.Add(manufacturer!);
        }

        PackagesView.Refresh();
        SelectedPackage = AllPackages.FirstOrDefault(p => p.Id == selectedId) ?? AllPackages.FirstOrDefault();
        LeftPackage ??= AllPackages.FirstOrDefault();
        RightPackage ??= AllPackages.Skip(1).FirstOrDefault();

        var root = _settings.Current.FirmwareLibraryRoot
                   ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NexusFirmware");
        LibraryRoot = root;
        var (free, driveRoot) = FirmwareLibrary.GetFreeSpace(Directory.Exists(root) ? root : Path.GetTempPath());
        FreeSpaceText = free > 0 ? $"{SizeFormatting.HumanReadable(free)} свободно на {driveRoot}" : "нет данных";

        OnPropertyChanged(nameof(CountText));
    }

    private void RebuildDetails()
    {
        Details.Clear();
        Notes.Clear();
        CompatibilityChecks.Clear();

        if (SelectedPackage is null)
        {
            return;
        }

        var package = SelectedPackage;
        Details.Add(new DeviceDetailRow { Label = "Название", Value = package.DisplayName });
        Details.Add(new DeviceDetailRow { Label = "Производитель", Value = package.Manufacturer ?? "неизвестно" });
        Details.Add(new DeviceDetailRow { Label = "Модель", Value = package.Model ?? "неизвестно" });
        Details.Add(new DeviceDetailRow { Label = "Кодовое имя", Value = package.Codename ?? "неизвестно" });
        Details.Add(new DeviceDetailRow { Label = "Версия", Value = package.Version ?? "неизвестно" });
        Details.Add(new DeviceDetailRow { Label = "Сборка", Value = package.BuildNumber ?? "неизвестно" });
        Details.Add(new DeviceDetailRow { Label = "Регион", Value = package.Region ?? "неизвестно" });
        Details.Add(new DeviceDetailRow { Label = "Формат", Value = package.FormatText });
        Details.Add(new DeviceDetailRow { Label = "Размер", Value = package.SizeText });
        Details.Add(new DeviceDetailRow { Label = "SHA-256", Value = package.Sha256 ?? "не вычислен" });
        Details.Add(new DeviceDetailRow { Label = "Целостность", Value = package.IntegrityText });
        Details.Add(new DeviceDetailRow { Label = "Путь", Value = package.FilePath ?? "файл не привязан" });
        Details.Add(new DeviceDetailRow { Label = "Импортировано", Value = package.ImportedAt.ToLocalTime().ToString("yyyy-MM-dd HH:mm") });
        Details.Add(new DeviceDetailRow { Label = "Проверено", Value = package.LastCheckedAt.ToLocalTime().ToString("yyyy-MM-dd HH:mm") });

        foreach (var pair in package.Metadata.OrderBy(p => p.Key))
        {
            Details.Add(new DeviceDetailRow { Label = "meta:" + pair.Key, Value = pair.Value });
        }

        foreach (var note in _library.GetNotes(package.Id))
        {
            Notes.Add(new NoteItem { Id = note.Id, CreatedAt = note.CreatedAt, Text = note.Text });
        }
    }

    private async Task ImportFileAsync()
    {
        var path = Dialogs.PickFile("Выберите файл прошивки",
            "Прошивки (*.zip;*.tar;*.md5;*.tar.md5;*.gz;*.lz4;*.img;*.bin;*.xml;*.txt)|*.zip;*.tar;*.md5;*.tar.md5;*.gz;*.lz4;*.img;*.bin;*.xml;*.txt|Все файлы (*.*)|*.*");

        if (path is null)
        {
            return;
        }

        await ImportPathsAsync([path]);
    }

    private async Task ImportFolderAsync()
    {
        var folder = Dialogs.PickFolder("Выберите каталог с прошивками");
        if (folder is null)
        {
            return;
        }

        IsBusy = true;
        BusyText = "Импорт каталога…";
        try
        {
            var progress = new Progress<(double Percent, string Message)>(p => BusyText = $"Импорт: {p.Percent:0}% · {p.Message}");
            var results = await _library.ImportDirectoryAsync(folder, recursive: false, new ImportOptions(), progress).ConfigureAwait(true);
            ImportStatus = $"Импортировано файлов: {results.Count}. Дубликатов: {results.Count(r => r.IsDuplicate)}.";
            Reload();
        }
        finally
        {
            IsBusy = false;
            BusyText = string.Empty;
        }
    }

    private async Task ImportPathsAsync(IReadOnlyList<string> paths)
    {
        IsBusy = true;
        BusyText = "Импорт…";
        try
        {
            var messages = new List<string>();
            foreach (var path in paths)
            {
                var progress = new Progress<(double Percent, string Message)>(p =>
                    BusyText = $"{Path.GetFileName(path)}: {p.Percent:0}% · {p.Message}");
                var result = await _library.ImportAsync(path, new ImportOptions { ComputeHash = true }, progress).ConfigureAwait(true);
                messages.Add(result.IsDuplicate
                    ? $"{Path.GetFileName(path)}: уже в каталоге."
                    : $"{Path.GetFileName(path)}: импортировано ({result.Package.FormatText}).");
                messages.AddRange(result.Messages);
            }

            ImportStatus = string.Join(Environment.NewLine, messages);
            Reload();
            SelectedPackage = AllPackages.FirstOrDefault(p => p.DisplayName == Path.GetFileName(paths[0])) ?? SelectedPackage;
        }
        finally
        {
            IsBusy = false;
            BusyText = string.Empty;
        }
    }

    private async Task VerifyHashAsync()
    {
        if (SelectedPackage is null)
        {
            return;
        }

        IsBusy = true;
        BusyText = "Проверка SHA-256…";
        try
        {
            var id = SelectedPackage.Id;
            var ok = await _library.VerifyIntegrityAsync(id).ConfigureAwait(true);
            Reload();
            SelectedPackage = AllPackages.FirstOrDefault(p => p.Id == id);
            ImportStatus = ok ? "SHA-256 подтверждён." : "SHA-256 не совпадает или файл недоступен.";
            Dialogs.Info("Проверка целостности", ImportStatus);
        }
        finally
        {
            IsBusy = false;
            BusyText = string.Empty;
        }
    }

    private void RemoveSelected()
    {
        if (SelectedPackage is null)
        {
            return;
        }

        if (!Dialogs.Confirm("Удаление записи", "Удалить запись из каталога? Файл на диске не будет удалён.", danger: true))
        {
            return;
        }

        _library.Remove(SelectedPackage.Id);
        Reload();
    }

    private void AddNote()
    {
        if (SelectedPackage is null || string.IsNullOrWhiteSpace(NoteDraft))
        {
            return;
        }

        _library.AddNote(SelectedPackage.Id, NoteDraft.Trim());
        NoteDraft = string.Empty;
        RebuildDetails();
    }

    private void CheckCompatibility()
    {
        if (SelectedPackage is null)
        {
            return;
        }

        CompatibilityChecks.Clear();
        var result = Firmware.Compatibility.FirmwareCompatibility.Check(_session.SelectedDevice, SelectedPackage);
        foreach (var item in result.Items)
        {
            CompatibilityChecks.Add(item);
        }

        if (_session.SelectedDevice is null)
        {
            Notify("Совместимость проверена без устройства: выбрано «не выбрано».");
        }
    }

    private void ComparePackages()
    {
        if (LeftPackage is null || RightPackage is null)
        {
            return;
        }

        ComparisonRows.Clear();
        OnlyInLeft.Clear();
        OnlyInRight.Clear();
        SizeDifferences.Clear();
        ComparisonNotes.Clear();

        _comparison = FirmwareComparer.Compare(LeftPackage, RightPackage);
        foreach (var row in _comparison.Rows)
        {
            ComparisonRows.Add(row);
        }

        foreach (var item in _comparison.OnlyInLeft.Take(200))
        {
            OnlyInLeft.Add(item);
        }

        foreach (var item in _comparison.OnlyInRight.Take(200))
        {
            OnlyInRight.Add(item);
        }

        foreach (var item in _comparison.SizeDifferences.Take(200))
        {
            SizeDifferences.Add(item);
        }

        foreach (var note in _comparison.Notes)
        {
            ComparisonNotes.Add(note);
        }
    }
}
