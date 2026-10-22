using System.Collections.ObjectModel;
using System.Diagnostics;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection;
using System.Linq;
using System.Threading.Tasks;

namespace NexusFirmware.App.ViewModels;

public sealed class DeviceDetailRow
{
    public required string Label { get; init; }
    public required string Value { get; init; }
}

public sealed class DevicesViewModel : PageViewModelBase
{
    private readonly DeviceDiscoveryService _discovery;
    private readonly DeviceSession _session;
    private bool _isScanning;
    private DeviceInfo? _selected;

    public DevicesViewModel(DeviceDiscoveryService discovery, DeviceSession session, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _discovery = discovery;
        _session = session;
        _session.DevicesChanged += (_, _) => RebuildDetails();
        _session.SelectionChanged += (_, _) =>
        {
            Selected = _session.SelectedDevice;
            RebuildDetails();
        };

        ScanCommand = new AsyncRelayCommand(ScanAsync, () => !IsScanning, ex => Handle("Сканирование устройств", ex));
        OpenDeviceManagerCommand = new RelayCommand(() => OpenWindowsTool("devmgmt.msc"));
        OpenAdbConsoleCommand = new RelayCommand(() => AppNavigation.Request("adb"));
        OpenFlashingCommand = new RelayCommand(() => AppNavigation.Request("flashing"));
        UpdateSelectionCommand = new RelayCommand(() =>
        {
            if (Selected is not null)
            {
                _session.RefreshSelection(Selected);
            }
        });
    }

    public override string Title => "Диспетчер устройств";

    public ObservableCollection<DeviceInfo> Devices => _session.Devices;

    public ObservableCollection<ProviderStatus> Providers { get; } = new();

    public ObservableCollection<DeviceDetailRow> Details { get; } = new();

    public ObservableCollection<string> Capabilities { get; } = new();

    public ObservableCollection<string> Warnings { get; } = new();

    public bool HasWarnings => Warnings.Count > 0;

    public bool IsScanning
    {
        get => _isScanning;
        private set => SetProperty(ref _isScanning, value);
    }

    public DeviceInfo? Selected
    {
        get => _selected;
        set
        {
            if (SetProperty(ref _selected, value))
            {
                _session.Select(value);
                RebuildDetails();
            }
        }
    }

    public string EmptyText => Devices.Count == 0
        ? "Устройства не обнаружены. Проверьте кабель, режим USB и драйверы."
        : "";

    public AsyncRelayCommand ScanCommand { get; }

    public RelayCommand OpenDeviceManagerCommand { get; }

    public RelayCommand OpenAdbConsoleCommand { get; }

    public RelayCommand OpenFlashingCommand { get; }

    public RelayCommand UpdateSelectionCommand { get; }

    public override void OnActivated()
    {
        Selected = _session.SelectedDevice;
        RebuildDetails();
        _ = ScanAsync();
    }

    private async Task ScanAsync()
    {
        IsScanning = true;
        try
        {
            var snapshot = await _discovery.ScanAsync().ConfigureAwait(true);
            _session.ReplaceDevices(snapshot.Devices);

            Providers.Clear();
            foreach (var provider in snapshot.Providers)
            {
                Providers.Add(provider);
            }

            if (Selected is null || !snapshot.Devices.Any(d => d.Id == Selected.Id))
            {
                Selected = _session.SelectedDevice;
            }

            RebuildDetails();
            OnPropertyChanged(nameof(EmptyText));
            Notify($"Сканирование: найдено устройств {snapshot.Devices.Count}.");
        }
        finally
        {
            IsScanning = false;
        }
    }

    private void RebuildDetails()
    {
        Details.Clear();
        Capabilities.Clear();
        Warnings.Clear();

        var device = Selected;
        if (device is null)
        {
            OnPropertyChanged(nameof(HasWarnings));
            return;
        }

        Details.Add(new DeviceDetailRow { Label = "Производитель", Value = device.Manufacturer ?? "недоступно" });
        Details.Add(new DeviceDetailRow { Label = "Модель", Value = device.Model ?? "недоступно" });
        Details.Add(new DeviceDetailRow { Label = "Кодовое имя", Value = device.Codename ?? "недоступно" });
        Details.Add(new DeviceDetailRow { Label = "Серийный номер", Value = device.MaskedSerial });
        Details.Add(new DeviceDetailRow { Label = "Android", Value = device.AndroidVersion ?? "недоступно" });
        Details.Add(new DeviceDetailRow { Label = "Сборка", Value = device.BuildId ?? "недоступно" });
        Details.Add(new DeviceDetailRow { Label = "Загрузчик", Value = device.BootloaderVersion ?? "недоступно" });
        Details.Add(new DeviceDetailRow
        {
            Label = "Состояние загрузчика",
            Value = device.BootloaderUnlocked switch
            {
                true => "разблокирован",
                false => "заблокирован",
                _ => "не определено"
            }
        });
        Details.Add(new DeviceDetailRow { Label = "Слот", Value = device.Slot ?? "недоступно" });
        Details.Add(new DeviceDetailRow
        {
            Label = "Заряд",
            Value = device.BatteryLevel is null ? "недоступно" : $"{device.BatteryLevel}%"
        });
        Details.Add(new DeviceDetailRow { Label = "Режим", Value = device.ModeText });
        Details.Add(new DeviceDetailRow { Label = "Транспорт", Value = device.Transport.ToString() });
        Details.Add(new DeviceDetailRow { Label = "Соединение", Value = device.ConnectionText });
        Details.Add(new DeviceDetailRow { Label = "Драйвер", Value = device.DriverText + (device.DriverName is null ? "" : $" · {device.DriverName}") });
        Details.Add(new DeviceDetailRow { Label = "VID / PID", Value = $"{device.VendorId ?? "—"} / {device.ProductId ?? "—"}" });
        Details.Add(new DeviceDetailRow { Label = "USB-путь", Value = device.UsbDevicePath ?? "недоступно" });
        Details.Add(new DeviceDetailRow { Label = "Обнаружено", Value = device.DetectedAt.ToString("HH:mm:ss") });

        foreach (var capability in device.Capabilities)
        {
            Capabilities.Add(capability);
        }

        foreach (var warning in device.Warnings)
        {
            Warnings.Add(warning);
        }

        OnPropertyChanged(nameof(HasWarnings));

        if (device.Capabilities.Count == 0)
        {
            Capabilities.Add("Операции не определены — устройство недоступно для диагностики.");
        }
    }

    private void OpenWindowsTool(string tool)
    {
        try
        {
            Process.Start(new ProcessStartInfo { FileName = tool, UseShellExecute = true });
        }
        catch (Exception ex)
        {
            Handle("Открытие системного инструмента", ex);
        }
    }
}
