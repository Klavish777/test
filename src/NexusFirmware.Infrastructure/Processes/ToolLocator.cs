using NexusFirmware.Core.Abstractions;

namespace NexusFirmware.Infrastructure.Processes;

/// <summary>
/// Поиск внешних инструментов: переменные окружения NEXUS_PLATFORM_TOOLS / ANDROID_HOME,
/// каталог tools приложения, PATH и стандартные расположения Android SDK.
/// </summary>
public sealed class ToolLocator : IToolLocator
{
    private readonly List<string> _searchPaths = new();
    private readonly Dictionary<string, string?> _cache = new(StringComparer.OrdinalIgnoreCase);

    public ToolLocator(string? appToolsDirectory = null)
    {
        if (!string.IsNullOrWhiteSpace(appToolsDirectory))
        {
            _searchPaths.Add(appToolsDirectory);
        }

        foreach (var variable in new[] { "NEXUS_PLATFORM_TOOLS", "ANDROID_PLATFORM_TOOLS", "ANDROID_HOME", "ANDROID_SDK_ROOT" })
        {
            var value = Environment.GetEnvironmentVariable(variable);
            if (!string.IsNullOrWhiteSpace(value))
            {
                _searchPaths.Add(value);
                _searchPaths.Add(Path.Combine(value, "platform-tools"));
            }
        }

        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrWhiteSpace(localAppData))
        {
            _searchPaths.Add(Path.Combine(localAppData, "Android", "Sdk", "platform-tools"));
        }

        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        if (!string.IsNullOrWhiteSpace(programFiles))
        {
            _searchPaths.Add(Path.Combine(programFiles, "Nexus Firmware Studio", "tools"));
            _searchPaths.Add(Path.Combine(programFiles, "Android", "platform-tools"));
        }

        foreach (var pathEntry in (Environment.GetEnvironmentVariable("PATH") ?? string.Empty)
                     .Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            _searchPaths.Add(pathEntry);
        }
    }

    public IReadOnlyList<string> SearchPaths => _searchPaths;

    public string? Find(string toolName)
    {
        if (string.IsNullOrWhiteSpace(toolName))
        {
            return null;
        }

        lock (_cache)
        {
            if (_cache.TryGetValue(toolName, out var cached))
            {
                return cached;
            }

            var candidates = OperatingSystem.IsWindows()
                ? new[] { toolName, toolName + ".exe", toolName + ".bat" }
                : new[] { toolName };

            foreach (var directory in _searchPaths)
            {
                foreach (var candidate in candidates)
                {
                    try
                    {
                        var full = Path.Combine(directory, candidate);
                        if (File.Exists(full))
                        {
                            _cache[toolName] = full;
                            return full;
                        }
                    }
                    catch (ArgumentException)
                    {
                        // Некорректная запись в PATH — пропускаем.
                    }
                }
            }

            _cache[toolName] = null;
            return null;
        }
    }

    public async Task<bool> ExistsAsync(string toolName, CancellationToken cancellationToken = default)
    {
        if (Find(toolName) is not null)
        {
            return true;
        }

        await Task.Yield();
        return false;
    }

    public void Invalidate() => _cache.Clear();
}
