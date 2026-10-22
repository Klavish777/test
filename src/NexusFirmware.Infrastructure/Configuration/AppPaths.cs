namespace NexusFirmware.Infrastructure.Configuration;

/// <summary>Каталоги приложения. Все данные по умолчанию хранятся локально.</summary>
public sealed class AppPaths
{
    public AppPaths(string? rootOverride = null)
    {
        Root = rootOverride ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "NexusFirmwareStudio");

        Database = Path.Combine(Root, "nexus.db");
        Logs = Path.Combine(Root, "logs");
        Reports = Path.Combine(Root, "reports");
        Cache = Path.Combine(Root, "cache");
        Tools = Path.Combine(Root, "tools");
        SettingsFile = Path.Combine(Root, "settings.json");
        Plugins = Path.Combine(Root, "plugins");

        EnsureCreated();
    }

    public string Root { get; }
    public string Database { get; }
    public string Logs { get; }
    public string Reports { get; }
    public string Cache { get; }
    public string Tools { get; }
    public string SettingsFile { get; }
    public string Plugins { get; }

    public void EnsureCreated()
    {
        foreach (var directory in new[] { Root, Logs, Reports, Cache, Tools, Plugins })
        {
            Directory.CreateDirectory(directory);
        }
    }
}
