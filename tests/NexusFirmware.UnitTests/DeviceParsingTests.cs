using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection.Adb;
using NexusFirmware.DeviceDetection.Fastboot;
using NexusFirmware.DeviceDetection.Usb;

namespace NexusFirmware.UnitTests;

[TestFixture]
public sealed class AdbParsingTests
{
    [Test]
    public void ParsesDeviceList()
    {
        const string output = """
            List of devices attached
            R58M12345              device product:beyond1lte model:SM_G973F device:beyond1 transport_id:1
            ABCDEF0123             unauthorized usb:1-1 transport_id:2
            987654                 offline transport_id:3
            """;

        var devices = AdbProvider.ParseDeviceList(output);

        Assert.That(devices, Has.Count.EqualTo(3));
        Assert.That(devices[0].Mode, Is.EqualTo(DeviceMode.Adb));
        Assert.That(devices[0].Connection, Is.EqualTo(ConnectionState.Connected));
        Assert.That(devices[0].Model, Is.EqualTo("SM G973F"));
        Assert.That(devices[0].Codename, Is.EqualTo("beyond1"));
        Assert.That(devices[1].Connection, Is.EqualTo(ConnectionState.Unauthorized));
        Assert.That(devices[1].Warnings, Is.Not.Empty);
        Assert.That(devices[2].Connection, Is.EqualTo(ConnectionState.Offline));
    }

    [Test]
    public void IgnoresHeaderAndEmptyOutput()
    {
        Assert.That(AdbProvider.ParseDeviceList("List of devices attached\n\n"), Is.Empty);
        Assert.That(AdbProvider.ParseDeviceList(""), Is.Empty);
    }

    [Test]
    public void ParsesProps()
    {
        const string output = """
            [ro.product.model]: [SM-G973F]
            [ro.product.device]: [beyond1]
            [ro.build.version.release]: [12]
            [ro.boot.flash.locked]: [1]
            """;

        var props = AdbProvider.ParseProps(output);

        Assert.That(props["ro.product.model"], Is.EqualTo("SM-G973F"));
        Assert.That(props["ro.product.device"], Is.EqualTo("beyond1"));
        Assert.That(props.Count, Is.EqualTo(4));
    }
}

[TestFixture]
public sealed class FastbootParsingTests
{
    [Test]
    public void ParsesDevices()
    {
        var devices = FastbootProvider.ParseDeviceList("FA79X1A00001\tfastboot\n12ab34cd\tfastboot\n");
        Assert.That(devices, Has.Count.EqualTo(2));
        Assert.That(devices[0].Transport, Is.EqualTo(DeviceTransport.Fastboot));
        Assert.That(devices[0].Connection, Is.EqualTo(ConnectionState.Connected));
    }

    [Test]
    public void ParsesGetVarOutput()
    {
        const string output = """
            (bootloader) product: raven
            (bootloader) unlocked: no
            (bootloader) current-slot: a
            (bootloader) partition-size:boot:0x2000000
            (bootloader) partition-size:vendor:0x40000000
            finished. total time: 0.123s
            """;

        var vars = FastbootProvider.ParseGetVarOutput(output);

        Assert.That(vars["product"], Is.EqualTo("raven"));
        Assert.That(vars["unlocked"], Is.EqualTo("no"));
        Assert.That(vars.ContainsKey("finished"), Is.False);
    }

    [Test]
    public void ParsesPartitions()
    {
        const string output = """
            (bootloader) partition-size:boot:0x2000000
            (bootloader) partition-size:vendor:0x40000000
            """;

        var partitions = NexusFirmware.DeviceDetection.Services.FastbootService.ParsePartitions(output);

        Assert.That(partitions, Has.Count.EqualTo(2));
        Assert.That(partitions[0].Partition, Is.EqualTo("boot"));
        Assert.That(partitions[0].SizeBytes, Is.EqualTo(0x2000000));
    }
}

[TestFixture]
public sealed class UsbParsingTests
{
    [Test]
    public void ParsesCimJsonArray()
    {
        const string json = """
            [
              {"DeviceID":"USB\\VID_05C6&PID_9008\\7&1A2B3C4D&0&1","Name":"Qualcomm HS-USB QDLoader 9008","Manufacturer":"Qualcomm","Service":"QDUSBADB","Status":"OK","ConfigManagerErrorCode":0},
              {"DeviceID":"USB\\VID_04E8&PID_685D\\5&2A3B4C5D&0&2","Name":"SAMSUNG Mobile USB Modem","Manufacturer":"Samsung","Service":"MODEM","Status":"Error","ConfigManagerErrorCode":28}
            ]
            """;

        var devices = WindowsUsbEnumerator.ParseJson(json);

        Assert.That(devices, Has.Count.EqualTo(2));
        Assert.That(devices[0].VendorId, Is.EqualTo(0x05C6));
        Assert.That(devices[0].ProductId, Is.EqualTo(0x9008));
        Assert.That(devices[0].Driver, Is.EqualTo(DriverStatus.Ok));
        Assert.That(devices[1].Driver, Is.EqualTo(DriverStatus.Problem));
        Assert.That(devices[1].ProblemCode, Is.EqualTo(28));

        var info = WindowsUsbEnumerator.ToDeviceInfo(devices[0]);
        Assert.That(info.Mode, Is.EqualTo(DeviceMode.QualcommEdl));
        Assert.That(info.VendorId, Is.EqualTo("05C6"));
        Assert.That(info.Warnings, Is.Not.Empty);
    }

    [Test]
    public void HandlesInvalidJson()
    {
        Assert.That(WindowsUsbEnumerator.ParseJson("not json"), Is.Empty);
        Assert.That(WindowsUsbEnumerator.ParseJson(""), Is.Empty);
    }
}
