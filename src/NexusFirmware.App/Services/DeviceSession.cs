using System.Collections.ObjectModel;
using NexusFirmware.Core.Models;
using System.Collections.Generic;
using System.Linq;

namespace NexusFirmware.App.Services;

/// <summary>Текущий список устройств и выбранное устройство, общие для всех разделов.</summary>
public sealed class DeviceSession
{
    public ObservableCollection<DeviceInfo> Devices { get; } = new();

    public DeviceInfo? SelectedDevice { get; private set; }

    public event EventHandler? SelectionChanged;

    public event EventHandler? DevicesChanged;

    public void ReplaceDevices(IEnumerable<DeviceInfo> devices)
    {
        var selectedId = SelectedDevice?.Id;

        Devices.Clear();
        foreach (var device in devices)
        {
            Devices.Add(device);
        }

        SelectedDevice = Devices.FirstOrDefault(d => d.Id == selectedId) ?? Devices.FirstOrDefault();
        DevicesChanged?.Invoke(this, EventArgs.Empty);
        SelectionChanged?.Invoke(this, EventArgs.Empty);
    }

    public void Select(DeviceInfo? device)
    {
        if (device is not null && !Devices.Contains(device))
        {
            return;
        }

        SelectedDevice = device;
        SelectionChanged?.Invoke(this, EventArgs.Empty);
    }

    public void RefreshSelection(DeviceInfo? device)
    {
        if (device is null)
        {
            SelectedDevice = null;
        }
        else
        {
            SelectedDevice = Devices.FirstOrDefault(d => d.Id == device.Id);
        }

        SelectionChanged?.Invoke(this, EventArgs.Empty);
    }
}
