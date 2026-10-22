using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Detection;
using NexusFirmware.Firmware.Images;

namespace NexusFirmware.Firmware.Extractor;

/// <summary>
/// Извлечение содержимого прошивок во временный каталог с защитой от path traversal и zip-бомб.
/// Оригинальные файлы всегда открываются только на чтение.
/// </summary>
public sealed class FirmwareExtractorService
{
    private readonly ILogBus _log;
    private readonly ExtractionLimits _limits;

    public FirmwareExtractorService(ILogBus log, ExtractionLimits? limits = null)
    {
        _log = log;
        _limits = limits ?? ExtractionLimits.Default;
    }

    public string CreateWorkDirectory(string hint) => PathSafety.CreateWorkDirectory(hint);

    public ExtractionLimits Limits => _limits;

    public async Task<IReadOnlyList<string>> ExtractAsync(
        string sourceFile,
        string destinationDirectory,
        IProgress<(double Percent, string Message)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (!InputValidator.IsReadableFile(sourceFile))
        {
            throw new FileNotFoundException("Файл не найден или пуст.", sourceFile);
        }

        var format = FormatDetector.Detect(sourceFile);
        _log.Info("Extractor", $"Извлечение {Path.GetFileName(sourceFile)} ({format}) → {destinationDirectory}");

        switch (format)
        {
            case FirmwareFormat.Zip:
            {
                var zipProgress = new Progress<double>(p => progress?.Report((p, $"Распаковка ZIP: {p:0}%")));
                return await ZipInspector.ExtractAsync(sourceFile, destinationDirectory, _limits, true, zipProgress, cancellationToken).ConfigureAwait(false);
            }

            case FirmwareFormat.Tar:
            case FirmwareFormat.TarMd5:
            {
                var tarProgress = new Progress<double>(p => progress?.Report((p, $"Распаковка TAR: {p:0}%")));
                return await TarInspector.ExtractFileAsync(sourceFile, destinationDirectory, _limits, tarProgress, cancellationToken).ConfigureAwait(false);
            }

            case FirmwareFormat.Gzip:
            {
                var target = Path.Combine(destinationDirectory, StripCompressionSuffix(Path.GetFileName(sourceFile), ".gz"));
                Directory.CreateDirectory(destinationDirectory);
                await using var input = File.OpenRead(sourceFile);
                await using var gzip = new System.IO.Compression.GZipStream(input, System.IO.Compression.CompressionMode.Decompress);
                await using var output = File.Create(target);
                await gzip.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
                progress?.Report((100, "GZip распакован"));
                return new[] { target };
            }

            case FirmwareFormat.Lz4:
            {
                var target = Path.Combine(destinationDirectory, StripCompressionSuffix(Path.GetFileName(sourceFile), ".lz4"));
                Directory.CreateDirectory(destinationDirectory);
                await using var input = File.OpenRead(sourceFile);
                await using var output = File.Create(target);
                var info = await Lz4FrameDecoder.DecompressAsync(input, output, cancellationToken).ConfigureAwait(false);
                progress?.Report((100, $"LZ4 распакован ({SizeFormatting.HumanReadable(info.UncompressedBytes)})"));
                return new[] { target };
            }

            case FirmwareFormat.SparseImage:
            {
                var target = Path.Combine(destinationDirectory, StripCompressionSuffix(Path.GetFileName(sourceFile), ".img") + ".raw.img");
                Directory.CreateDirectory(destinationDirectory);
                var sparseProgress = new Progress<double>(p => progress?.Report((p, $"Разворачивание sparse: {p:0}%")));
                await SparseImageParser.UnsparseAsync(sourceFile, target, sparseProgress, cancellationToken).ConfigureAwait(false);
                return new[] { target };
            }

            default:
                throw new NotSupportedException($"Для формата {format} автоматическое извлечение не реализовано. Используйте анализ.");
        }
    }

    private static string StripCompressionSuffix(string name, string suffix) =>
        name.EndsWith(suffix, StringComparison.OrdinalIgnoreCase) ? name[..^suffix.Length] : name + ".out";
}
