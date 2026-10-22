using System.Security.Cryptography;
using System.Text;

namespace NexusFirmware.Core.Plugins;

/// <summary>
/// Проверка отсоединённой подписи манифеста плагина (RSA-SHA256, ключ в PEM).
/// Подпись не заменяет проверку SHA-256 сборки: она подтверждает авторство манифеста,
/// а хэш — целостность самого кода.
/// </summary>
public static class PluginSignature
{
    /// <summary>Проверяет подпись строки <see cref="PluginManifest.SigningPayload"/>.</summary>
    public static bool Verify(PluginManifest manifest, string? signatureBase64, string? publicKeyPem)
    {
        if (string.IsNullOrWhiteSpace(signatureBase64) || string.IsNullOrWhiteSpace(publicKeyPem))
        {
            return false;
        }

        try
        {
            var signature = Convert.FromBase64String(signatureBase64.Trim());
            var payload = Encoding.UTF8.GetBytes(manifest.SigningPayload);

            using var rsa = RSA.Create();
            rsa.ImportFromPem(publicKeyPem);
            return rsa.VerifyData(payload, signature, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        }
        catch (Exception ex) when (ex is CryptographicException or FormatException or ArgumentException)
        {
            return false;
        }
    }

    /// <summary>Подписывает манифест закрытым ключом (используется издателем плагина и тестами).</summary>
    public static string Sign(PluginManifest manifest, RSA privateKey)
    {
        var payload = Encoding.UTF8.GetBytes(manifest.SigningPayload);
        return Convert.ToBase64String(privateKey.SignData(payload, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1));
    }
}
