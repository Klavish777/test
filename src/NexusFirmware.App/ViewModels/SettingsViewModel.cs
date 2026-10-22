using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Net.Http;
using System.Text.Json;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Infrastructure.Configuration;

namespace NexusFirmware.App.ViewModels;

public sealed class SettingsViewModel : PageViewModelBase
{
    private readonly SettingsService _settings;
    private readonly AppPaths _paths;
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(10) };

    private bool _readOnlyMode;
    private bool _requireSerialConfirmation;
    private bool _allowPluginLoading;
    private bool _maskSerials;
    private string _language;
    private int _refreshSeconds;
    private string _adbPath = "";
    private string _fastbootPath = "";
    private string _libraryRoot = "";
    private string _licenseKey = "";
    private string _updateChannel = "stable";
    private string _status = "Изменения вступают в силу после сохранения.";
    private string _updateStatus = "Проверка обновлений не выполнялась.";
    private bool _isBusy;

    public SettingsViewModel(SettingsService settings, AppPaths paths, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _settings = settings;
        _paths = paths;
        LoadFromSettings();

        SaveCommand = new RelayCommand(Save);
        BrowseAdbCommand = new RelayCommand(() => AdbPath = Dialogs.PickFile("adb.exe", "adb.exe|adb.exe|Все файлы (*.*)|*.*") ?? AdbPath);
        BrowseFastbootCommand = new RelayCommand(() => FastbootPath = Dialogs.PickFile("fastboot.exe", "fastboot.exe|fastboot.exe|Все файлы (*.*)|*.*") ?? FastbootPath);
        BrowseLibraryCommand = new RelayCommand(() => LibraryRoot = Dialogs.PickFolder("Корневой каталог библиотеки прошивок") ?? LibraryRoot);
        OpenDataFolderCommand = new RelayCommand(() => ReportService.OpenInExplorer(_paths.Root));
        OpenProjectsPageCommand = new RelayCommand(() => OpenUrl("https://github.com/Klavish777/test"));
        CheckUpdatesCommand = new AsyncRelayCommand(CheckUpdatesAsync, () => !IsBusy, ex => Handle("Проверка обновлений", ex));
        ResetCommand = new RelayCommand(() =>
        {
            if (!Dialogs.Confirm("Сброс настроек", "Вернуть значения по умолчанию? Файлы и журналы не удаляются."))
            {
                return;
            }

            _settings.Save(new AppSettings());
            LoadFromSettings();
            Status = "Настройки сброшены к значениям по умолчанию.";
        });
    }

    public override string Title => "Настройки";

    public IReadOnlyList<string> Languages { get; } = new[] { "ru", "en" };

    public IReadOnlyList<string> UpdateChannels { get; } = new[] { "stable", "beta" };

    public ObservableCollection<string> LicenseNotes { get; } = new()
    {
        "Лицензирование локальное: ключ хранится на этом компьютере и не отправляется на сервер.",
        "Серверная активация/подписка не реализованы — не выдавайте локальный ключ за подтверждённую лицензию.",
        "Приложение не собирает телеметрию и не передаёт идентификаторы устройств."
    };

    public bool ReadOnlyMode
    {
        get => _readOnlyMode;
        set => SetProperty(ref _readOnlyMode, value);
    }

    public bool RequireSerialConfirmation
    {
        get => _requireSerialConfirmation;
        set => SetProperty(ref _requireSerialConfirmation, value);
    }

    public bool AllowPluginLoading
    {
        get => _allowPluginLoading;
        set => SetProperty(ref _allowPluginLoading, value);
    }

    public bool MaskSerials
    {
        get => _maskSerials;
        set => SetProperty(ref _maskSerials, value);
    }

    public string Language
    {
        get => _language;
        set => SetProperty(ref _language, value);
    }

    public int RefreshSeconds
    {
        get => _refreshSeconds;
        set => SetProperty(ref _refreshSeconds, value);
    }

    public string AdbPath
    {
        get => _adbPath;
        set => SetProperty(ref _adbPath, value);
    }

    public string FastbootPath
    {
        get => _fastbootPath;
        set => SetProperty(ref _fastbootPath, value);
    }

    public string LibraryRoot
    {
        get => _libraryRoot;
        set => SetProperty(ref _libraryRoot, value);
    }

    public string LicenseKey
    {
        get => _licenseKey;
        set => SetProperty(ref _licenseKey, value);
    }

    public string UpdateChannel
    {
        get => _updateChannel;
        set => SetProperty(ref _updateChannel, value);
    }

    public string Status
    {
        get => _status;
        private set => SetProperty(ref _status, value);
    }

    public string UpdateStatus
    {
        get => _updateStatus;
        private set => SetProperty(ref _updateStatus, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public string DataDirectory => _paths.Root;

    public string DatabasePath => _paths.Database;

    public string LogsDirectory => _paths.Logs;

    public RelayCommand SaveCommand { get; }

    public RelayCommand BrowseAdbCommand { get; }

    public RelayCommand BrowseFastbootCommand { get; }

    public RelayCommand BrowseLibraryCommand { get; }

    public RelayCommand OpenDataFolderCommand { get; }

    public RelayCommand OpenProjectsPageCommand { get; }

    public AsyncRelayCommand CheckUpdatesCommand { get; }

    public RelayCommand ResetCommand { get; }

    private void LoadFromSettings()
    {
        var s = _settings.Current;
        ReadOnlyMode = s.ReadOnlyMode;
        RequireSerialConfirmation = s.RequireSerialConfirmation;
        AllowPluginLoading = s.AllowPluginLoading;
        MaskSerials = s.MaskSerialsInLogs;
        Language = s.Language;
        RefreshSeconds = s.DeviceRefreshSeconds;
        AdbPath = s.AdbPath ?? "";
        FastbootPath = s.FastbootPath ?? "";
        LibraryRoot = s.FirmwareLibraryRoot ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NexusFirmware");
        LicenseKey = s.LicenseKey;
        UpdateChannel = s.UpdateChannel;
    }

    private void Save()
    {
        var current = _settings.Current;
        var updated = new AppSettings
        {
            ReadOnlyMode = ReadOnlyMode,
            RequireSerialConfirmation = RequireSerialConfirmation,
            AllowPluginLoading = AllowPluginLoading,
            MaskSerialsInLogs = MaskSerials,
            Language = Language,
            DeviceRefreshSeconds = Math.Clamp(RefreshSeconds, 0, 120),
            AdbPath = string.IsNullOrWhiteSpace(AdbPath) ? null : AdbPath.Trim(),
            FastbootPath = string.IsNullOrWhiteSpace(FastbootPath) ? null : FastbootPath.Trim(),
            FirmwareLibraryRoot = string.IsNullOrWhiteSpace(LibraryRoot) ? null : LibraryRoot.Trim(),
            LicenseKey = LicenseKey.Trim(),
            UpdateChannel = UpdateChannel,
            TrustedPluginPublishers = current.TrustedPluginPublishers,
            ExtractorOutputDirectory = current.ExtractorOutputDirectory,
            LogRetentionDays = current.LogRetentionDays
        };

        _settings.Save(updated);
        Core.Localization.Localizer.Current = Language == "en"
            ? Core.Localization.Localizer.Language.English
            : Core.Localization.Localizer.Language.Russian;

        Status = "Настройки сохранены.";
        Dialogs.Info("Настройки", "Настройки сохранены. Часть изменений вступает в силу после перезапуска приложения.");
    }

    private async Task CheckUpdatesAsync()
    {
        IsBusy = true;
        UpdateStatus = "Запрос к GitHub Releases…";
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, "https://api.github.com/repos/Klavish777/test/releases/latest");
            request.Headers.Add("User-Agent", "NexusFirmwareStudio");
            using var response = await Http.SendAsync(request).ConfigureAwait(true);

            if (!response.IsSuccessStatusCode)
            {
                UpdateStatus = $"Релизы недоступны (HTTP {(int)response.StatusCode}). Проверьте подключение или страницу проекта.";
                return;
            }

            var json = await response.Content.ReadAsStringAsync().ConfigureAwait(true);
            using var document = JsonDocument.Parse(json);
            var tag = document.RootElement.TryGetProperty("tag_name", out var tagElement) ? tagElement.GetString() : null;
            var url = document.RootElement.TryGetProperty("html_url", out var urlElement) ? urlElement.GetString() : null;

            UpdateStatus = tag is null
                ? "Релиз найден, но тег не указан."
                : $"Последний релиз: {tag}. Текущая версия: {System.Reflection.Assembly.GetExecutingAssembly().GetName().Version}." +
                  (url is null ? "" : Environment.NewLine + url);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException)
        {
            UpdateStatus = "Не удалось проверить обновления: " + ex.Message;
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void OpenUrl(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo { FileName = url, UseShellExecute = true });
        }
        catch (Exception ex)
        {
            Handle("Открытие ссылки", ex);
        }
    }
}
