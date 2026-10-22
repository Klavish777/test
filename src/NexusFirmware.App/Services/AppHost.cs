using Microsoft.Extensions.DependencyInjection;
using NexusFirmware.App.ViewModels;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Jobs;
using NexusFirmware.DeviceDetection;
using NexusFirmware.DeviceDetection.Adb;
using NexusFirmware.DeviceDetection.Fastboot;
using NexusFirmware.DeviceDetection.Services;
using NexusFirmware.DeviceDetection.Usb;
using NexusFirmware.Drivers;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Extractor;
using NexusFirmware.Firmware.Library;
using NexusFirmware.Flashing;
using NexusFirmware.Infrastructure.Configuration;
using NexusFirmware.Infrastructure.Data;
using NexusFirmware.Infrastructure.Logging;
using NexusFirmware.Infrastructure.Processes;
using NexusFirmware.MediaTek;
using NexusFirmware.Plugins;
using NexusFirmware.Qualcomm;
using NexusFirmware.Samsung;
using Serilog;

namespace NexusFirmware.App.Services;

/// <summary>Сборка контейнера зависимостей приложения.</summary>
public static class AppHost
{
    public static ServiceProvider Build(AppPaths paths, SettingsStore settingsStore, ILogger logger)
    {
        var services = new ServiceCollection();

        services.AddSingleton(paths);
        services.AddSingleton(settingsStore);
        services.AddSingleton<SettingsService>();
        services.AddSingleton(logger);
        services.AddSingleton<ILogBus>(_ => new LogBus(logger));
        services.AddSingleton<DialogService>();
        services.AddSingleton<DeviceSession>();
        services.AddSingleton<ReportService>();

        services.AddSingleton(_ =>
        {
            var database = new NexusDatabase(paths.Database);
            database.Initialize();
            return database;
        });
        services.AddSingleton<FirmwareRepository>();
        services.AddSingleton<DiagnosticsRepository>();
        services.AddSingleton<TrustRepository>();

        services.AddSingleton<IProcessRunner, ProcessRunner>();
        services.AddSingleton<IToolLocator>(_ => new ToolLocator(paths.Tools));
        services.AddSingleton<ExternalToolAdapter>();
        services.AddSingleton<WindowsUsbEnumerator>();
        services.AddSingleton<IDeviceProvider, AdbProvider>();
        services.AddSingleton<IDeviceProvider, FastbootProvider>();
        services.AddSingleton<DeviceDiscoveryService>();
        services.AddSingleton<AdbService>();
        services.AddSingleton<FastbootService>();

        services.AddSingleton<FirmwareLibrary>();
        services.AddSingleton<FirmwareAnalyzer>();
        services.AddSingleton(_ => new FirmwareExtractorService(_.GetRequiredService<ILogBus>(), ExtractionLimits.Default));
        services.AddSingleton<JobQueue>();
        services.AddSingleton<FlashPlanner>();

        services.AddSingleton<QualcommService>();
        services.AddSingleton<MediaTekService>();
        services.AddSingleton<SamsungService>();
        services.AddSingleton<DriverCenterService>();
        services.AddSingleton<PluginLoader>();
        services.AddSingleton<PluginHost>();

        // ViewModels — синглтоны: состояние разделов сохраняется при навигации.
        services.AddSingleton<DashboardViewModel>();
        services.AddSingleton<DevicesViewModel>();
        services.AddSingleton<FirmwareViewModel>();
        services.AddSingleton<FlashingViewModel>();
        services.AddSingleton<AdbViewModel>();
        services.AddSingleton<QualcommViewModel>();
        services.AddSingleton<MediaTekViewModel>();
        services.AddSingleton<SamsungViewModel>();
        services.AddSingleton<ExtractorViewModel>();
        services.AddSingleton<PartitionsViewModel>();
        services.AddSingleton<LogsViewModel>();
        services.AddSingleton<DriversViewModel>();
        services.AddSingleton<PluginsViewModel>();
        services.AddSingleton<SettingsViewModel>();
        services.AddSingleton<MainViewModel>();

        return services.BuildServiceProvider(new ServiceProviderOptions
        {
            ValidateOnBuild = false,
            ValidateScopes = false
        });
    }
}
