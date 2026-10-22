using System.Text.Json;
using System.Text.Json.Serialization;

namespace NexusFirmware.Infrastructure.Configuration;

public sealed class AppSettings
{
    public string Language { get; set; } = "ru";

    public string Theme { get; set; } = "DarkBlue";

    /// <summary>Период автообновления списка устройств, секунды. 0 — выключено.</summary>
    public int DeviceRefreshSeconds { get; set; } = 5;

    /// <summary>Запрет любых реальных операций записи. Включён по умолчанию.</summary>
    public bool ReadOnlyMode { get; set; } = true;

    /// <summary>Требовать ввода серийного номера для подтверждения опасных операций.</summary>
    public bool RequireSerialConfirmation { get; set; } = true;

    public bool AllowPluginLoading { get; set; }

    public List<string> TrustedPluginPublishers { get; set; } = new();

    public string? AdbPath { get; set; }

    public string? FastbootPath { get; set; }

    public string? FirmwareLibraryRoot { get; set; }

    public string? ExtractorOutputDirectory { get; set; }

    public bool MaskSerialsInLogs { get; set; } = true;

    public int LogRetentionDays { get; set; } = 14;

    public string LicenseKey { get; set; } = "";

    public string UpdateChannel { get; set; } = "stable";

    [JsonIgnore]
    public bool IsRussian => !string.Equals(Language, "en", StringComparison.OrdinalIgnoreCase);
}

public sealed class SettingsStore
{
    private static readonly JsonSerializerOptions Options = new() { WriteIndented = true };

    public SettingsStore(AppPaths paths)
    {
        Paths = paths;
    }

    public AppPaths Paths { get; }

    public AppSettings Load()
    {
        try
        {
            if (File.Exists(Paths.SettingsFile))
            {
                var json = File.ReadAllText(Paths.SettingsFile);
                return JsonSerializer.Deserialize<AppSettings>(json, Options) ?? new AppSettings();
            }
        }
        catch (Exception)
        {
            // Повреждённый файл настроек — используем значения по умолчанию.
        }

        return new AppSettings();
    }

    public void Save(AppSettings settings)
    {
        Paths.EnsureCreated();
        var json = JsonSerializer.Serialize(settings, Options);
        var temp = Paths.SettingsFile + ".tmp";
        File.WriteAllText(temp, json);
        File.Move(temp, Paths.SettingsFile, overwrite: true);
    }
}
