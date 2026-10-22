using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Plugins;
using NexusFirmware.Infrastructure.Configuration;
using NexusFirmware.Infrastructure.Data;
using NexusFirmware.Plugins;

namespace NexusFirmware.App.ViewModels;

public sealed class PluginRow
{
    public required string Name { get; init; }
    public required string Id { get; init; }
    public required string Version { get; init; }
    public required string Publisher { get; init; }
    public required string Origin { get; init; }
    public required string Operations { get; init; }
    public required string Limitations { get; init; }
}

public sealed class PluginsViewModel : PageViewModelBase
{
    private readonly PluginHost _host;
    private readonly TrustRepository _trust;
    private readonly SettingsService _settings;
    private readonly AppPaths _paths;
    private string _newPublisher = "";
    private string _status = "Плагины не загружались в этой сессии.";
    private bool _allowLoading;

    public PluginsViewModel(
        PluginHost host,
        TrustRepository trust,
        SettingsService settings,
        AppPaths paths,
        ILogBus log,
        DialogService dialogs)
        : base(log, dialogs)
    {
        _host = host;
        _trust = trust;
        _settings = settings;
        _paths = paths;
        _allowLoading = settings.Current.AllowPluginLoading;

        RescanCommand = new RelayCommand(Rescan);
        AddTrustedCommand = new RelayCommand(AddTrusted, () => !string.IsNullOrWhiteSpace(NewPublisher));
        RevokeCommand = new RelayCommand(parameter =>
        {
            if (parameter is string publisher)
            {
                _trust.Revoke(publisher);
                LoadTrusted();
                Status = $"Издатель «{publisher}» удалён из доверенных.";
            }
        });
        OpenFolderCommand = new RelayCommand(() => ReportService.OpenInExplorer(_paths.Plugins));
        SaveLoadingFlagCommand = new RelayCommand(() =>
        {
            _settings.Update(s => s.AllowPluginLoading = AllowLoading);
            Status = AllowLoading
                ? "Загрузка плагинов разрешена. Проверка SHA-256 и издателя всё равно обязательна."
                : "Загрузка плагинов отключена.";
        });

        LoadTrusted();
        LoadRows();
    }

    public override string Title => "Плагины";

    public ObservableCollection<PluginRow> Plugins { get; } = new();

    public ObservableCollection<string> Rejected { get; } = new();

    public ObservableCollection<string> TrustedPublishers { get; } = new();

    public string PluginsDirectory => _paths.Plugins;

    public string NewPublisher
    {
        get => _newPublisher;
        set => SetProperty(ref _newPublisher, value);
    }

    public bool AllowLoading
    {
        get => _allowLoading;
        set => SetProperty(ref _allowLoading, value);
    }

    public string Status
    {
        get => _status;
        private set => SetProperty(ref _status, value);
    }

    public ObservableCollection<string> Policy { get; } = new()
    {
        "Загружаются только сборки, SHA-256 которых совпадает с манифестом *.plugin.json.",
        "Издатель должен быть в списке доверенных — иначе плагин отклоняется.",
        "Плагины не скачиваются автоматически и не загружаются из неизвестных источников.",
        "Плагин получает доступ только к контракту INexusPlugin: проверки совместимости и описание операций.",
        "Ограничения и требуемые разрешения отображаются до включения плагина."
    };

    public RelayCommand RescanCommand { get; }

    public RelayCommand AddTrustedCommand { get; }

    public RelayCommand RevokeCommand { get; }

    public RelayCommand OpenFolderCommand { get; }

    public RelayCommand SaveLoadingFlagCommand { get; }

    public override void OnActivated() => LoadRows();

    private void LoadRows()
    {
        Plugins.Clear();
        foreach (var plugin in _host.All)
        {
            Plugins.Add(new PluginRow
            {
                Name = plugin.Manifest.Name,
                Id = plugin.Manifest.Id,
                Version = plugin.Manifest.Version,
                Publisher = plugin.Manifest.Publisher ?? "не указан",
                Origin = plugin.IsBuiltIn ? "встроенный" : plugin.AssemblyPath,
                Operations = string.Join(", ", plugin.Manifest.Operations),
                Limitations = string.Join("; ", plugin.Manifest.Limitations)
            });
        }

        Rejected.Clear();
        foreach (var rejection in _host.LastRejected)
        {
            Rejected.Add($"[{rejection.Decision}] {rejection.Message}");
        }
    }

    private void LoadTrusted()
    {
        TrustedPublishers.Clear();
        foreach (var publisher in _trust.GetTrustedPublishers())
        {
            TrustedPublishers.Add(publisher);
        }
    }

    private void AddTrusted()
    {
        var publisher = NewPublisher.Trim();
        if (publisher.Length == 0)
        {
            return;
        }

        if (!Dialogs.Confirm("Доверенный издатель",
                $"Добавить издателя «{publisher}» в доверенные?\n\nДоверяйте только тем, чьи плагины вы получили из проверенного источника."))
        {
            return;
        }

        _trust.Trust(publisher, "Добавлен пользователем");
        NewPublisher = string.Empty;
        LoadTrusted();
        Status = $"Издатель «{publisher}» добавлен в доверенные.";
    }

    private void Rescan()
    {
        var result = _host.ScanAndLoad(_paths.Plugins, _trust.GetTrustedPublishers(), _settings.Current.AllowPluginLoading);
        LoadRows();
        Status = $"Активных модулей: {_host.All.Count}; внешних загружено: {result.Loaded.Count}; отклонено: {result.Rejected.Count}.";
    }
}
