using System.Collections.ObjectModel;
using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection.Services;
using NexusFirmware.Firmware.Qualcomm;
using NexusFirmware.Firmware.Scatter;
using System.IO;
using System.Linq;
using System.Threading.Tasks;

namespace NexusFirmware.App.ViewModels;

/// <summary>Просмотр таблиц разделов: fastboot, /proc/partitions (ADB), scatter, rawprogram XML.</summary>
public sealed class PartitionsViewModel : PageViewModelBase
{
    private readonly FastbootService _fastboot;
    private readonly AdbService _adb;
    private readonly DeviceSession _session;
    private string _status = "Выберите источник данных о разделах.";
    private bool _isBusy;

    public PartitionsViewModel(FastbootService fastboot, AdbService adb, DeviceSession session, ILogBus log, DialogService dialogs)
        : base(log, dialogs)
    {
        _fastboot = fastboot;
        _adb = adb;
        _session = session;
        _session.SelectionChanged += (_, _) => OnPropertyChanged(nameof(SelectedDevice));

        LoadFastbootCommand = new AsyncRelayCommand(LoadFastbootAsync, () => CanUseDevice && !IsBusy, ex => Handle("Разделы fastboot", ex));
        LoadAdbCommand = new AsyncRelayCommand(LoadAdbAsync, () => SelectedDevice is not null && !IsBusy, ex => Handle("Разделы ADB", ex));
        LoadScatterCommand = new RelayCommand(LoadScatter);
        LoadRawProgramCommand = new RelayCommand(LoadRawProgram);
        ClearCommand = new RelayCommand(() =>
        {
            Partitions.Clear();
            Status = "Таблица очищена.";
        });
    }

    public override string Title => "Разделы";

    public ObservableCollection<PartitionRow> Partitions { get; } = new();

    public ObservableCollection<DeviceInfo> Devices => _session.Devices;

    public DeviceInfo? SelectedDevice
    {
        get => _session.SelectedDevice;
        set => _session.Select(value);
    }

    public bool CanUseDevice => SelectedDevice is not null;

    public string DeviceModeText => SelectedDevice is null ? "Устройство не выбрано" : SelectedDevice.ModeText;

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

    public AsyncRelayCommand LoadFastbootCommand { get; }

    public AsyncRelayCommand LoadAdbCommand { get; }

    public RelayCommand LoadScatterCommand { get; }

    public RelayCommand LoadRawProgramCommand { get; }

    public RelayCommand ClearCommand { get; }

    public override void OnActivated()
    {
        OnPropertyChanged(nameof(SelectedDevice));
        OnPropertyChanged(nameof(DeviceModeText));
    }

    private async Task LoadFastbootAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        if (device.Mode != DeviceMode.Fastboot)
        {
            Dialogs.Warn("Разделы", "Устройство не в режиме fastboot. Переведите его в fastboot (ADB и Fastboot → Перезагрузка в fastboot).");
            return;
        }

        IsBusy = true;
        try
        {
            var partitions = await _fastboot.GetPartitionsAsync(device.Serial).ConfigureAwait(true);
            Partitions.Clear();
            foreach (var (name, size) in partitions.OrderBy(p => p.Partition))
            {
                Partitions.Add(new PartitionRow
                {
                    Name = name,
                    Size = size is null ? "недоступно" : SizeFormatting.HumanReadable(size.Value),
                    Source = "fastboot getvar all"
                });
            }

            Status = partitions.Count == 0
                ? "fastboot не сообщил разделы: устройство может не поддерживать getvar all."
                : $"Разделов получено: {partitions.Count}.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task LoadAdbAsync()
    {
        var device = SelectedDevice;
        if (device?.Serial is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            var result = await _adb.ShellAsync(device.Serial, ["cat", "/proc/partitions"]).ConfigureAwait(true);
            Partitions.Clear();

            foreach (var line in result.StandardOutput.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            {
                var parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 4)
                {
                    continue;
                }

                if (!long.TryParse(parts[0], out var blocks))
                {
                    continue;
                }

                Partitions.Add(new PartitionRow
                {
                    Name = parts[3],
                    Size = SizeFormatting.HumanReadable(blocks * 1024),
                    Source = "/proc/partitions (ADB)"
                });
            }

            Status = Partitions.Count == 0
                ? "Раздел /proc/partitions недоступен (типично для новых Android без root-доступа)."
                : $"Разделов из /proc/partitions: {Partitions.Count}. Часть разделов может быть скрыта политикой Android.";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private void LoadScatter()
    {
        var path = Dialogs.PickFile("Scatter-файл MediaTek", "Scatter (*.txt)|*.txt|Все файлы (*.*)|*.*");
        if (path is null)
        {
            return;
        }

        try
        {
            var scatter = ScatterParser.Parse(path);
            Partitions.Clear();
            foreach (var partition in scatter.Partitions)
            {
                Partitions.Add(new PartitionRow
                {
                    Name = partition.PartitionName,
                    Size = partition.PartitionSize is null ? "недоступно" : SizeFormatting.HumanReadable(partition.PartitionSize.Value),
                    Source = "scatter",
                    Detail = partition.FileName
                });
            }

            Status = $"Scatter: платформа {scatter.Platform ?? "не указана"}, разделов {Partitions.Count}.";
        }
        catch (Exception ex) when (ex is IOException or InvalidDataException)
        {
            Handle("Чтение scatter", ex);
        }
    }

    private void LoadRawProgram()
    {
        var path = Dialogs.PickFile("rawprogram XML (Qualcomm)", "XML (*.xml)|*.xml|Все файлы (*.*)|*.*");
        if (path is null)
        {
            return;
        }

        try
        {
            var document = RawProgramParser.Parse(path);
            Partitions.Clear();
            foreach (var program in document.Programs)
            {
                Partitions.Add(new PartitionRow
                {
                    Name = program.Label,
                    Size = program.NumSectors is null ? "недоступно" : $"{program.NumSectors} секторов",
                    Source = "rawprogram XML",
                    Detail = program.FileName
                });
            }

            Status = $"rawprogram: записей {Partitions.Count}, патчей {document.Patches.Count}.";
        }
        catch (Exception ex) when (ex is IOException or System.Xml.XmlException)
        {
            Handle("Чтение rawprogram", ex);
        }
    }
}
