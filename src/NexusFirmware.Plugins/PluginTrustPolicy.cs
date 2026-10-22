using NexusFirmware.Core.Plugins;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.Plugins;

/// <summary>
/// Политика доверия плагинам: проверка манифеста, SHA-256 сборки, издателя из списка доверенных.
/// Непроверенные сборки не загружаются в процесс приложения.
/// </summary>
public sealed class PluginTrustPolicy
{
    public PluginTrustPolicy(IReadOnlyCollection<string> trustedPublishers, bool allowLoading, string hostVersion = "1.0.0")
    {
        TrustedPublishers = trustedPublishers;
        AllowLoading = allowLoading;
        HostVersion = hostVersion;
    }

    public IReadOnlyCollection<string> TrustedPublishers { get; }

    public bool AllowLoading { get; }

    public string HostVersion { get; }

    public PluginValidationResult Validate(PluginManifest manifest, string assemblyPath)
    {
        if (string.IsNullOrWhiteSpace(manifest.Id) || string.IsNullOrWhiteSpace(manifest.Name) || string.IsNullOrWhiteSpace(manifest.Version))
        {
            return new PluginValidationResult(PluginTrustDecision.InvalidManifest,
                "Манифест не содержит обязательных полей id/name/version.");
        }

        if (!System.Version.TryParse(NormalizeVersion(manifest.Version), out var pluginVersion))
        {
            return new PluginValidationResult(PluginTrustDecision.InvalidManifest,
                $"Версия плагина «{manifest.Version}» не является корректной версией.");
        }

        if (System.Version.TryParse(NormalizeVersion(manifest.MinimumHostVersion), out var minimumHost) &&
            System.Version.TryParse(NormalizeVersion(HostVersion), out var host) &&
            host < minimumHost)
        {
            return new PluginValidationResult(PluginTrustDecision.NotAllowedByPolicy,
                $"Плагин требует версию хоста {manifest.MinimumHostVersion}, текущая {HostVersion}.");
        }

        if (!File.Exists(assemblyPath))
        {
            return new PluginValidationResult(PluginTrustDecision.InvalidManifest,
                "Файл сборки плагина не найден: " + assemblyPath);
        }

        if (string.IsNullOrWhiteSpace(manifest.Sha256))
        {
            return new PluginValidationResult(PluginTrustDecision.HashMismatch,
                "В манифесте отсутствует SHA-256 сборки — загрузка запрещена.");
        }

        var actual = Hashing.Sha256FileAsync(assemblyPath).GetAwaiter().GetResult();
        if (!string.Equals(actual, Hashing.NormalizeHash(manifest.Sha256), StringComparison.OrdinalIgnoreCase))
        {
            return new PluginValidationResult(PluginTrustDecision.HashMismatch,
                $"SHA-256 сборки не совпадает с манифестом (ожидался {manifest.Sha256[..Math.Min(16, manifest.Sha256.Length)]}…).");
        }

        if (string.IsNullOrWhiteSpace(manifest.Publisher))
        {
            return new PluginValidationResult(PluginTrustDecision.Unsigned,
                "Издатель плагина не указан — плагин считается неподписанным.");
        }

        var trusted = TrustedPublishers.Any(p => string.Equals(p, manifest.Publisher, StringComparison.OrdinalIgnoreCase));
        if (!trusted)
        {
            return new PluginValidationResult(PluginTrustDecision.UntrustedPublisher,
                $"Издатель «{manifest.Publisher}» отсутствует в списке доверенных.");
        }

        if (!AllowLoading)
        {
            return new PluginValidationResult(PluginTrustDecision.NotAllowedByPolicy,
                "Загрузка плагинов отключена в настройках.");
        }

        return new PluginValidationResult(PluginTrustDecision.Trusted,
            "Плагин проверен: SHA-256 совпадает, издатель доверенный.", manifest, assemblyPath);
    }

    private static string NormalizeVersion(string version)
    {
        var cleaned = version.Split('-', '+')[0];
        var parts = cleaned.Split('.');
        return parts.Length switch
        {
            1 => cleaned + ".0.0",
            2 => cleaned + ".0",
            _ => cleaned
        };
    }
}
