using System.IO.Compression;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.DeviceDetection;
using NexusFirmware.DeviceDetection.Services;
using NexusFirmware.DeviceDetection.Usb;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Extractor;
using NexusFirmware.Flashing;
using NexusFirmware.Infrastructure.Processes;
using NexusFirmware.UnitTests;
using NUnit.Framework;

namespace NexusFirmware.IntegrationTests;

[TestFixture]
public sealed class FlashPlannerTests
{
    private TempDirectory _temp = null!;
    private FakeProcessRunner _runner = null!;
    private AdbService _adb = null!;
    private FastbootService _fastboot = null!;
    private FirmwareExtractorService _extractor = null!;

    [SetUp]
    public void Setup()
    {
        _temp = new TempDirectory();
        _runner = new FakeProcessRunner();
        var locator = new ToolLocator(_temp.Path);
        _adb = new AdbService(_runner, locator, new FakeLogBus());
        _fastboot = new FastbootService(_runner, locator, new FakeLogBus());
        _extractor = new FirmwareExtractorService(new FakeLogBus());
    }

    [TearDown]
    public void TearDown() => _temp.Dispose();

    private FlashPlanContext CreateContext(FlashOptions options, FirmwarePackage package)
    {
        return new FlashPlanContext
        {
            Device = TestData.Device(),
            Package = package,
            Options = options,
            Adb = _adb,
            Fastboot = _fastboot,
            Extractor = _extractor,
            Analyzer = new FirmwareAnalyzer(),
            Log = new FakeLogBus()
        };
    }

    private FirmwarePackage CreateImagePackage()
    {
        var image = Path.Combine(_temp.Path, "boot.img");
        File.WriteAllBytes(image, new byte[2048]);

        return new FirmwarePackage
        {
            Id = "img",
            DisplayName = "boot.img",
            Manufacturer = "Samsung",
            Model = "G973F",
            Format = FirmwareFormat.Image,
            FilePath = image,
            SizeBytes = 2048,
            Sha256 = "a".PadRight(64, 'a'),
            Integrity = IntegrityState.Verified
        };
    }

    [Test]
    public async Task DryRunPlanDoesNotExecuteAnything()
    {
        var package = CreateImagePackage();
        var context = CreateContext(new FlashOptions { DryRun = true }, package);
        var planner = new FlashPlanner();

        var plan = await planner.BuildPlanAsync(context);

        Assert.That(plan.StrategyId, Is.EqualTo("fastboot-images"));
        Assert.That(plan.Plan.IsDryRun, Is.True);
        Assert.That(plan.Targets, Has.Count.EqualTo(1));
        Assert.That(plan.Targets[0].Partition, Is.EqualTo("boot"));
        Assert.That(plan.Plan.Steps.Any(s => s.Title.Contains("boot")), Is.True);
        Assert.That(_runner.Requests, Is.Empty, "Планирование не должно запускать процессы");
    }

    [Test]
    public async Task LivePlanRequiresPermission()
    {
        var package = CreateImagePackage();
        var options = new FlashOptions { DryRun = false, AllowDeviceModification = false };
        var planner = new FlashPlanner();

        var plan = await planner.BuildPlanAsync(CreateContext(options, package));

        Assert.That(plan.Plan.HasBlockingIssues, Is.True);
        Assert.That(plan.Plan.Checks.Any(c => c.Check == "Разрешение" && c.Severity == CompatibilitySeverity.Blocking), Is.True);
    }

    [Test]
    public async Task LivePlanWithPermissionIsConfirmable()
    {
        var package = CreateImagePackage();
        var options = new FlashOptions { DryRun = false, AllowDeviceModification = true };
        var planner = new FlashPlanner();

        var plan = await planner.BuildPlanAsync(CreateContext(options, package));

        Assert.That(plan.Plan.HasBlockingIssues, Is.False);
        Assert.That(plan.Plan.RequiresExplicitConfirmation, Is.True);
        Assert.That(plan.Plan.HighestRisk, Is.EqualTo(OperationRisk.ModifiesDevice));
    }

    [Test]
    public async Task LockedBootloaderBlocksPlan()
    {
        var package = CreateImagePackage();
        var context = CreateContext(new FlashOptions { DryRun = false, AllowDeviceModification = true }, package);
        context = new FlashPlanContext
        {
            Device = TestData.Device(unlocked: false),
            Package = package,
            Options = context.Options,
            Adb = _adb,
            Fastboot = _fastboot,
            Extractor = _extractor,
            Analyzer = new FirmwareAnalyzer(),
            Log = new FakeLogBus()
        };

        var plan = await new FlashPlanner().BuildPlanAsync(context);

        Assert.That(plan.Plan.HasBlockingIssues, Is.True);
        Assert.That(plan.Plan.Checks.Any(c => c.Check == "Загрузчик" && c.Severity == CompatibilitySeverity.Blocking), Is.True);
    }

    [Test]
    public async Task SamsungStrategyIsHonestAboutMissingProtocol()
    {
        var package = TestData.Package(path: Path.Combine(_temp.Path, "AP_fake.tar.md5"));
        File.WriteAllText(package.FilePath!, "x");

        var options = new FlashOptions { DryRun = true };
        var context = new FlashPlanContext
        {
            Device = TestData.Device(unlocked: true, mode: DeviceMode.Download),
            Package = package,
            Options = options,
            Adb = _adb,
            Fastboot = _fastboot,
            Extractor = _extractor,
            Analyzer = new FirmwareAnalyzer(),
            Log = new FakeLogBus()
        };

        var plan = await new FlashPlanner().BuildPlanAsync(context);

        Assert.That(plan.StrategyId, Is.EqualTo("samsung-external"));
        Assert.That(plan.Plan.HasBlockingIssues, Is.True);
        Assert.That(plan.Plan.Warnings.Any(w => w.Contains("не реализован")), Is.True);
    }

    [Test]
    public async Task ZipWithMultipleImagesProducesTargets()
    {
        var zipPath = Path.Combine(_temp.Path, "images.zip");
        using (var zip = ZipFile.Open(zipPath, ZipArchiveMode.Create))
        {
            foreach (var name in new[] { "boot.img", "vbmeta.img", "unknown-partition.img" })
            {
                using var writer = new StreamWriter(zip.CreateEntry(name).Open());
                writer.Write("data");
            }
        }

        var package = new FirmwarePackage
        {
            Id = "zip",
            DisplayName = "images.zip",
            Manufacturer = "Samsung",
            Model = "G973F",
            Format = FirmwareFormat.Zip,
            FilePath = zipPath,
            Integrity = IntegrityState.Verified
        };

        var plan = await new FlashPlanner().BuildPlanAsync(CreateContext(new FlashOptions { DryRun = true }, package));

        Assert.That(plan.Targets.Select(t => t.Partition), Is.EquivalentTo(new[] { "boot", "vbmeta" }));
        Assert.That(plan.Plan.Warnings.Any(w => w.Contains("unknown-partition.img")), Is.True);
    }
}

[TestFixture]
public sealed class ExtractionLimitTests
{
    [Test]
    public void RejectsArchiveOverConfiguredLimit()
    {
        using var temp = new TempDirectory();
        var zipPath = Path.Combine(temp.Path, "big.zip");
        using (var zip = ZipFile.Open(zipPath, ZipArchiveMode.Create))
        {
            using var writer = new StreamWriter(zip.CreateEntry("data.img").Open());
            writer.Write(new string('A', 4096));
        }

        var limits = new ExtractionLimits { MaxTotalBytes = 100 };

        Assert.ThrowsAsync<InvalidOperationException>(async () =>
            await ZipInspector.ExtractAsync(zipPath, Path.Combine(temp.Path, "out"), limits));
    }
}

internal sealed class StubDeviceProvider : IDeviceProvider
{
    public StubDeviceProvider(string id, IReadOnlyList<DeviceInfo> devices, bool available = true)
    {
        ProviderId = id;
        DisplayName = id;
        Devices = devices;
        Available = available;
    }

    public string ProviderId { get; }

    public string DisplayName { get; }

    public IReadOnlyList<DeviceInfo> Devices { get; }

    public bool Available { get; }

    public Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default) => Task.FromResult(Available);

    public Task<IReadOnlyList<DeviceInfo>> DiscoverAsync(CancellationToken cancellationToken = default) =>
        Task.FromResult(Devices);
}

[TestFixture]
public sealed class DiscoveryTests
{
    [Test]
    public async Task CollectsDevicesFromProvidersAndReportsStatuses()
    {
        var provider = new StubDeviceProvider("adb", new[] { TestData.Device(mode: DeviceMode.Adb) });
        var unavailable = new StubDeviceProvider("fastboot", Array.Empty<DeviceInfo>(), available: false);
        var usb = new WindowsUsbEnumerator(new FakeProcessRunner(), new FakeLogBus());
        var service = new DeviceDiscoveryService(
            new IDeviceProvider[] { provider, unavailable },
            usb,
            new ToolLocator(Path.GetTempPath()),
            new FakeLogBus());

        var snapshot = await service.ScanAsync();

        Assert.That(snapshot.Devices, Has.Count.EqualTo(1));
        Assert.That(snapshot.Providers.Single(p => p.ProviderId == "adb").Available, Is.True);
        Assert.That(snapshot.Providers.Single(p => p.ProviderId == "fastboot").Available, Is.False);
        Assert.That(snapshot.Providers.Any(p => p.ProviderId == "usb"), Is.True);
    }
}
