using System.Collections.ObjectModel;
using System.Diagnostics;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Drivers;
using System.Threading.Tasks;

namespace NexusFirmware.App.ViewModels;

public sealed class DriversViewModel : PageViewModelBase
{
    private readonly DriverCenterService _service;
    private string _status = "Проверка драйверов не выполнялась.";
    private string _installerPath = "";
    private string _signatureText = "Подпись не проверялась.";
    private bool _isBusy;

    public DriversViewModel(DriverCenterService service, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _service = service;

        foreach (var source in service.OfficialSources)
        {
            Sources.Add(source);
        }

        foreach (var step in service.GetReinstallGuidance())
        {
            Guidance.Add(step);
        }

        RefreshCommand = new AsyncRelayCommand(RefreshAsync, () => !IsBusy, ex => Handle("Проверка драйверов", ex));
        PickInstallerCommand = new RelayCommand(PickInstaller);
        VerifySignatureCommand = new AsyncRelayCommand(VerifySignatureAsync, () => !IsBusy && !string.IsNullOrWhiteSpace(InstallerPath), ex => Handle("Проверка подписи", ex));
        OpenUrlCommand = new RelayCommand(parameter =>
        {
            if (parameter is string url)
            {
                OpenUrl(url);
            }
        });
        OpenDeviceManagerCommand = new RelayCommand(() => Open("devmgmt.msc"));
    }

    public override string Title => "Центр драйверов";

    public ObservableCollection<DriverInventoryItem> Inventory { get; } = new();

    public ObservableCollection<string> ToolchainMessages { get; } = new();

    public ObservableCollection<DriverSource> Sources { get; } = new();

    public ObservableCollection<string> Guidance { get; } = new();

    public string Status
    {
        get => _status;
        private set => SetProperty(ref _status, value);
    }

    public string InstallerPath
    {
        get => _installerPath;
        set => SetProperty(ref _installerPath, value);
    }

    public string SignatureText
    {
        get => _signatureText;
        private set => SetProperty(ref _signatureText, value);
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set => SetProperty(ref _isBusy, value);
    }

    public AsyncRelayCommand RefreshCommand { get; }

    public RelayCommand PickInstallerCommand { get; }

    public AsyncRelayCommand VerifySignatureCommand { get; }

    public RelayCommand OpenUrlCommand { get; }

    public RelayCommand OpenDeviceManagerCommand { get; }

    public override void OnActivated() => _ = RefreshAsync();

    private async Task RefreshAsync()
    {
        IsBusy = true;
        Status = "Опрос USB-устройств и инструментов…";
        try
        {
            var inventory = await _service.GetInventoryAsync().ConfigureAwait(true);
            Inventory.Clear();
            foreach (var item in inventory)
            {
                Inventory.Add(item);
            }

            ToolchainMessages.Clear();
            foreach (var message in await _service.CheckToolchainAsync().ConfigureAwait(true))
            {
                ToolchainMessages.Add(message);
            }

            Status = inventory.Count == 0
                ? "USB-устройства известных производителей не обнаружены. Инвентаризация драйверов доступна в Windows."
                : $"USB-устройств: {inventory.Count}. Проблемных: {inventory.Count(i => i.Status == Core.Models.DriverStatus.Problem)}.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void PickInstaller()
    {
        var path = Dialogs.PickFile("Установочный пакет драйвера", "Установщики (*.exe;*.msi;*.inf;*.zip)|*.exe;*.msi;*.inf;*.zip|Все файлы (*.*)|*.*");
        if (path is not null)
        {
            InstallerPath = path;
            SignatureText = "Подпись не проверялась.";
        }
    }

    private async Task VerifySignatureAsync()
    {
        IsBusy = true;
        try
        {
            var result = await _service.VerifyInstallerSignatureAsync(InstallerPath).ConfigureAwait(true);
            SignatureText = $"{result.Status}: {result.Message}" +
                            (result.SignerSubject is null ? "" : $"{Environment.NewLine}Издатель: {result.SignerSubject}") +
                            (result.Thumbprint is null ? "" : $"{Environment.NewLine}Отпечаток: {result.Thumbprint}") +
                            (result.Timestamp is null ? "" : $"{Environment.NewLine}Метка времени: {result.Timestamp}");

            Dialogs.Info("Проверка подписи",
                result.IsValid
                    ? "Цифровая подпись пакета действительна." + Environment.NewLine + result.Message
                    : "Подпись не подтверждена." + Environment.NewLine + result.Message +
                      Environment.NewLine + Environment.NewLine + "Приложение не отключает проверку подписи драйверов.");
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

    private void Open(string target)
    {
        try
        {
            Process.Start(new ProcessStartInfo { FileName = target, UseShellExecute = true });
        }
        catch (Exception ex)
        {
            Handle("Открытие системного инструмента", ex);
        }
    }
}
