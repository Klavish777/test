using System.Windows;
using System.Windows.Threading;
using Microsoft.Extensions.DependencyInjection;
using NexusFirmware.App.Services;
using NexusFirmware.App.ViewModels;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Infrastructure.Configuration;
using NexusFirmware.Infrastructure.Logging;
using NexusFirmware.Plugins;
using Serilog;

namespace NexusFirmware.App;

public partial class App : Application
{
    private ServiceProvider? _services;
    private Mutex? _singleInstanceMutex;
    private ILogger? _logger;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _singleInstanceMutex = new Mutex(initiallyOwned: true, "NexusFirmwareStudio.SingleInstance", out var isFirst);
        if (!isFirst)
        {
            MessageBox.Show("NEXUS Firmware Studio уже запущен.", "Приложение уже открыто", MessageBoxButton.OK, MessageBoxImage.Information);
            Shutdown();
            return;
        }

        var paths = new AppPaths();
        var settingsStore = new SettingsStore(paths);
        var settings = settingsStore.Load();

        _logger = new LoggerConfiguration()
            .MinimumLevel.Information()
            .WriteTo.File(
                Path.Combine(paths.Logs, "nexus-.log"),
                rollingInterval: RollingInterval.Day,
                retainedFileCountLimit: Math.Max(3, settings.LogRetentionDays),
                outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss.fff} [{Level:u3}] {Message:lj}{NewLine}{Exception}")
            .CreateLogger();

        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnDomainUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;

        _services = AppHost.Build(paths, settingsStore, _logger);
        var log = _services.GetRequiredService<ILogBus>();
        log.Info("App", $"Запуск NEXUS Firmware Studio {typeof(App).Assembly.GetName().Version}. Каталог данных: {paths.Root}");
        log.Info("App", $"Режим только чтения: {(settings.ReadOnlyMode ? "включён" : "выключен")}.");

        try
        {
            var plugins = _services.GetRequiredService<PluginHost>();
            var result = plugins.ScanAndLoad(paths.Plugins, settings.TrustedPluginPublishers, settings.AllowPluginLoading);
            if (result.Rejected.Count > 0)
            {
                log.Warn("Plugins", $"Отклонено плагинов: {result.Rejected.Count}.");
            }
        }
        catch (Exception ex)
        {
            log.Error("Plugins", "Ошибка загрузки плагинов: " + ex.Message);
        }

        var mainViewModel = _services.GetRequiredService<MainViewModel>();
        var window = new MainWindow { DataContext = mainViewModel };
        MainWindow = window;
        window.Show();

        _ = mainViewModel.InitializeAsync();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        try
        {
            if (_services is not null)
            {
                _services.GetRequiredService<JobQueue>().DisposeAsync().AsTask().Wait(TimeSpan.FromSeconds(5));
            }
        }
        catch (Exception)
        {
            // Завершение не должно блокироваться.
        }

        Log.CloseAndFlush();
        _singleInstanceMutex?.Dispose();
        base.OnExit(e);
    }

    private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        _logger?.Error(e.Exception, "Необработанная ошибка интерфейса");
        MessageBox.Show(
            "Произошла ошибка. Подробности записаны в журнал.\n\n" + e.Exception.Message,
            "Ошибка NEXUS Firmware Studio",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        e.Handled = true;
    }

    private void OnDomainUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception exception)
        {
            _logger?.Error(exception, "Необработанная ошибка домена");
        }
    }

    private void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        _logger?.Error(e.Exception, "Необработанная ошибка задачи");
        e.SetObserved();
    }
}
