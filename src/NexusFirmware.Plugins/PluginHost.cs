using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Plugins;
using NexusFirmware.Plugins.BuiltIn;

namespace NexusFirmware.Plugins;

/// <summary>Реестр активных модулей: встроенные + проверенные внешние плагины.</summary>
public sealed class PluginHost
{
    private readonly PluginLoader _loader;
    private readonly ILogBus _log;
    private readonly List<LoadedPlugin> _builtIn;
    private IReadOnlyList<LoadedPlugin> _external = Array.Empty<LoadedPlugin>();

    public PluginHost(PluginLoader loader, ILogBus log)
    {
        _loader = loader;
        _log = log;
        var builtInPlugin = new GenericAndroidPlugin();
        _builtIn =
        [
            new LoadedPlugin
            {
                Manifest = builtInPlugin.Manifest,
                Instance = builtInPlugin,
                AssemblyPath = typeof(GenericAndroidPlugin).Assembly.Location,
                IsBuiltIn = true
            }
        ];
    }

    public IReadOnlyList<LoadedPlugin> All => _builtIn.Concat(_external).ToArray();

    public IReadOnlyList<PluginValidationResult> LastRejected { get; private set; } = Array.Empty<PluginValidationResult>();

    public PluginScanResult ScanAndLoad(string pluginsDirectory, IReadOnlyCollection<string> trustedPublishers, bool allowLoading)
    {
        var policy = new PluginTrustPolicy(trustedPublishers, allowLoading);
        var result = _loader.Scan(pluginsDirectory, policy);
        _external = result.Loaded;
        LastRejected = result.Rejected;
        _log.Info("Plugins", $"Активных модулей: {All.Count} (внешних: {_external.Count}).");
        return result;
    }

    public IReadOnlyList<(string Plugin, CompatibilityItem Check)> CheckDevice(DeviceInfo device)
    {
        var results = new List<(string, CompatibilityItem)>();
        foreach (var plugin in All)
        {
            try
            {
                foreach (var item in plugin.Instance.CheckCompatibility(device))
                {
                    results.Add((plugin.Manifest.Name, item));
                }
            }
            catch (Exception ex)
            {
                _log.Error("Plugins", $"Плагин {plugin.Manifest.Id} вернул ошибку: {ex.Message}");
            }
        }

        return results;
    }

    public IReadOnlyList<(string Plugin, string Operation)> DescribeOperations(DeviceInfo device)
    {
        var results = new List<(string, string)>();
        foreach (var plugin in All)
        {
            try
            {
                foreach (var operation in plugin.Instance.DescribeOperations(device))
                {
                    results.Add((plugin.Manifest.Name, operation));
                }
            }
            catch (Exception ex)
            {
                _log.Error("Plugins", $"Плагин {plugin.Manifest.Id} вернул ошибку: {ex.Message}");
            }
        }

        return results;
    }
}
