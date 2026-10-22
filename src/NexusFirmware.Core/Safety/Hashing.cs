using System.Security.Cryptography;

namespace NexusFirmware.Core.Safety;

/// <summary>Потоковое вычисление контрольных сумм с ограничением скорости чтения и отменой.</summary>
public static class Hashing
{
    public const int DefaultBufferSize = 1024 * 1024;

    public static async Task<string> Sha256FileAsync(string filePath, IProgress<double>? progress = null, CancellationToken cancellationToken = default)
    {
        await using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read, DefaultBufferSize, useAsync: true);
        return await Sha256StreamAsync(stream, stream.Length, progress, cancellationToken).ConfigureAwait(false);
    }

    public static async Task<string> Sha256StreamAsync(Stream stream, long? totalLength, IProgress<double>? progress = null, CancellationToken cancellationToken = default)
    {
        using var sha = SHA256.Create();
        var buffer = new byte[DefaultBufferSize];
        long processed = 0;
        int read;

        while ((read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken).ConfigureAwait(false)) > 0)
        {
            sha.TransformBlock(buffer, 0, read, null, 0);
            processed += read;

            if (progress is not null && totalLength is > 0)
            {
                progress.Report(Math.Clamp(processed * 100.0 / totalLength.Value, 0, 100));
            }
        }

        sha.TransformFinalBlock(buffer, 0, 0);
        progress?.Report(100);
        return Convert.ToHexString(sha.Hash!).ToLowerInvariant();
    }

    public static async Task<string> Md5FileAsync(string filePath, CancellationToken cancellationToken = default)
    {
        await using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read, DefaultBufferSize, useAsync: true);
        var hash = await MD5.HashDataAsync(stream, cancellationToken).ConfigureAwait(false);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    public static async Task<bool> VerifySha256Async(string filePath, string expectedHex, IProgress<double>? progress = null, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(expectedHex))
        {
            return false;
        }

        var actual = await Sha256FileAsync(filePath, progress, cancellationToken).ConfigureAwait(false);
        return string.Equals(actual, expectedHex.Trim(), StringComparison.OrdinalIgnoreCase);
    }

    public static string Sha256Bytes(ReadOnlySpan<byte> data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();

    public static string NormalizeHash(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var cleaned = new string(value.Trim().Where(Uri.IsHexDigit).ToArray());
        return cleaned.ToLowerInvariant();
    }
}
