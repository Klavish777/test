using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Plugins;

namespace NexusFirmware.Plugins;

public sealed class LoadedPlugin
{
    public required PluginManifest Manifest { get; init; }
    public required INexusPlugin Instance { get; init; }
    public required string AssemblyPath { get; init; }
    public bool IsBuiltIn { get; init; }
}

public sealed class PluginScanResult
{
    public IReadOnlyList<LoadedPlugin> Loaded { get; init; } = Array.Empty<LoadedPlugin>();
    public IReadOnlyList<PluginValidationResult> Rejected { get; init; } = Array.Empty<PluginValidationResult>();
}

/// <summary>
/// Поиск и загрузка плагинов из каталога plugins: манифест *.plugin.json, проверка SHA-256,
/// издателя и версии. Сборки из неизвестных источников не загружаются.
/// </summary>
public sealed class PluginLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true
    };

    private readonly ILogBus _log;
    private readonly List<LoadedPlugin> _loaded = new();

    public PluginLoader(ILogBus log)
    {
        _log = log;
    }

    public IReadOnlyList<LoadedPlugin> Loaded => _loaded;

    public PluginScanResult Scan(string pluginsDirectory, PluginTrustPolicy policy)
    {
        var loaded = new List<LoadedPlugin>(_loaded);
        var rejected = new List<PluginValidationResult>();

        if (!Directory.Exists(pluginsDirectory))
        {
            return new PluginScanResult { Loaded = loaded, Rejected = rejected };
        }

        foreach (var manifestPath in Directory.EnumerateFiles(pluginsDirectory, "*.plugin.json", SearchOption.TopDirectoryOnly))
        {
            PluginManifest? manifest;
            try
            {
                manifest = JsonSerializer.Deserialize<PluginManifest>(File.ReadAllText(manifestPath), JsonOptions);
            }
            catch (Exception ex) when (ex is JsonException or IOException)
            {
                rejected.Add(new PluginValidationResult(PluginTrustDecision.InvalidManifest,
                    $"Манифест {Path.GetFileName(manifestPath)} не прочитан: {ex.Message}"));
                continue;
            }

            if (manifest is null)
            {
                rejected.Add(new PluginValidationResult(PluginTrustDecision.InvalidManifest,
                    $"Манифест {Path.GetFileName(manifestPath)} пуст."));
                continue;
            }

            var assemblyPath = Path.Combine(pluginsDirectory, Path.GetFileName(manifest.AssemblyFile));
            var signature = ReadSignature(assemblyPath);
            var validation = policy.Validate(manifest, assemblyPath, signature);
            if (!validation.IsTrusted)
            {
                rejected.Add(validation);
                _log.Warn("Plugins", $"Плагин {manifest.Id} отклонён: {validation.Message}");
                continue;
            }

            try
            {
                var instance = LoadInstance(assemblyPath, manifest.EntryType);
                loaded.Add(new LoadedPlugin
                {
                    Manifest = manifest,
                    Instance = instance,
                    AssemblyPath = assemblyPath
                });
                _log.Info("Plugins", $"Плагин загружен: {manifest.Name} {manifest.Version} ({manifest.Publisher}).");
            }
            catch (Exception ex)
            {
                rejected.Add(new PluginValidationResult(PluginTrustDecision.InvalidManifest,
                    $"Сборка {Path.GetFileName(assemblyPath)} не загружена: {ex.Message}"));
            }
        }

        _loaded.Clear();
        _loaded.AddRange(loaded);
        return new PluginScanResult { Loaded = loaded, Rejected = rejected };
    }

    private static INexusPlugin LoadInstance(string assemblyPath, string entryType)
    {
        var context = new PluginLoadContext(assemblyPath);
        var assembly = context.LoadFromAssemblyPath(Path.GetFullPath(assemblyPath));
        var type = assembly.GetType(entryType, throwOnError: false)
                   ?? throw new InvalidOperationException($"Тип {entryType} не найден в сборке.");

        if (!typeof(INexusPlugin).IsAssignableFrom(type))
        {
            throw new InvalidOperationException($"Тип {entryType} не реализует INexusPlugin.");
        }

        return Activator.CreateInstance(type) as INexusPlugin
            ?? throw new InvalidOperationException($"Не удалось создать экземпляр {entryType}.");
    }

    /// <summary>Отсоединённая подпись манифеста: файл {сборка}.sig рядом со сборкой.</summary>
    private static string? ReadSignature(string assemblyPath)
    {
        var signaturePath = assemblyPath + ".sig";
        return File.Exists(signaturePath) ? File.ReadAllText(signaturePath).Trim() : null;
    }

    private sealed class PluginLoadContext : AssemblyLoadContext
    {
        private readonly AssemblyDependencyResolver _resolver;

        public PluginLoadContext(string pluginPath)
            : base(isCollectible: false)
        {
            _resolver = new AssemblyDependencyResolver(pluginPath);
        }

        protected override Assembly? Load(AssemblyName assemblyName)
        {
            var path = _resolver.ResolveAssemblyToPath(assemblyName);
            return path is null ? null : LoadFromAssemblyPath(path);
        }
    }
}
