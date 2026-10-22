using System.Text;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Firmware.Detection;

/// <summary>
/// Определение формата файла по сигнатуре и расширению. Формат определяется по фактическому
/// содержимому, расширение используется только как дополнительный признак.
/// </summary>
public static class FormatDetector
{
    private static readonly byte[] ZipSignature = [0x50, 0x4B, 0x03, 0x04];
    private static readonly byte[] ZipEmptySignature = [0x50, 0x4B, 0x05, 0x06];
    private static readonly byte[] GzipSignature = [0x1F, 0x8B];
    private static readonly byte[] Lz4Signature = [0x04, 0x22, 0x4D, 0x18];
    private static readonly byte[] SparseSignature = [0x3A, 0xFF, 0x26, 0xED];
    private static readonly byte[] ElfSignature = [0x7F, 0x45, 0x4C, 0x46];
    private static readonly byte[] PayloadMagic = "CrAU"u8.ToArray();
    private static readonly byte[] AndroidBootMagic = "ANDROID!"u8.ToArray();

    public static FirmwareFormat Detect(string filePath)
    {
        if (!File.Exists(filePath))
        {
            return FirmwareFormat.Unknown;
        }

        var name = Path.GetFileName(filePath);
        var extension = Path.GetExtension(name).ToLowerInvariant();

        Span<byte> header = stackalloc byte[512];
        int read;
        using (var stream = File.OpenRead(filePath))
        {
            read = stream.Read(header);
        }

        header = header[..read];

        if (StartsWith(header, SparseSignature))
        {
            return FirmwareFormat.SparseImage;
        }

        if (StartsWith(header, ZipSignature) || StartsWith(header, ZipEmptySignature))
        {
            return FirmwareFormat.Zip;
        }

        if (StartsWith(header, GzipSignature))
        {
            return FirmwareFormat.Gzip;
        }

        if (StartsWith(header, Lz4Signature))
        {
            return FirmwareFormat.Lz4;
        }

        if (StartsWith(header, PayloadMagic))
        {
            return FirmwareFormat.PayloadBin;
        }

        if (StartsWith(header, ElfSignature))
        {
            return FirmwareFormat.Elf;
        }

        if (extension is ".tar" or ".md5" or ".tar.md5" && IsTar(header))
        {
            return extension == ".md5" || name.EndsWith(".tar.md5", StringComparison.OrdinalIgnoreCase)
                ? FirmwareFormat.TarMd5
                : FirmwareFormat.Tar;
        }

        if (IsTar(header))
        {
            return FirmwareFormat.Tar;
        }

        if (extension == ".img" || StartsWith(header, AndroidBootMagic))
        {
            return FirmwareFormat.Image;
        }

        if (extension is ".xml")
        {
            return LooksLikeRawProgramXml(filePath) ? FirmwareFormat.RawProgramXml : FirmwareFormat.Text;
        }

        if (extension is ".txt" && name.Contains("scatter", StringComparison.OrdinalIgnoreCase))
        {
            return FirmwareFormat.Scatter;
        }

        if (extension is ".exe" or ".dll")
        {
            return FirmwareFormat.Executable;
        }

        if (extension is ".ap" or ".bl" or ".cp" or ".csc")
        {
            return SamsungFormatFromName(name);
        }

        if (LooksLikeScatter(filePath))
        {
            return FirmwareFormat.Scatter;
        }

        return IsMostlyText(header) ? FirmwareFormat.Text : FirmwareFormat.Unknown;
    }

    public static FirmwareFormat SamsungFormatFromName(string fileName)
    {
        var name = Path.GetFileName(fileName).ToUpperInvariant();
        if (name.StartsWith("HOME_CSC", StringComparison.Ordinal))
        {
            return FirmwareFormat.SamsungHomeCsc;
        }

        if (name.Contains("_CSC", StringComparison.Ordinal) || name.Contains("CSC_", StringComparison.Ordinal) || name.StartsWith("CSC", StringComparison.Ordinal))
        {
            return FirmwareFormat.SamsungCsc;
        }

        if (name.StartsWith("AP", StringComparison.Ordinal) || name.Contains("_AP_", StringComparison.Ordinal))
        {
            return FirmwareFormat.SamsungAp;
        }

        if (name.StartsWith("BL", StringComparison.Ordinal) || name.Contains("_BL_", StringComparison.Ordinal))
        {
            return FirmwareFormat.SamsungBl;
        }

        if (name.StartsWith("CP", StringComparison.Ordinal) || name.Contains("_CP_", StringComparison.Ordinal))
        {
            return FirmwareFormat.SamsungCp;
        }

        return FirmwareFormat.Unknown;
    }

    private static bool StartsWith(ReadOnlySpan<byte> data, ReadOnlySpan<byte> signature) =>
        data.Length >= signature.Length && data[..signature.Length].SequenceEqual(signature);

    private static bool IsTar(ReadOnlySpan<byte> header)
    {
        // Поле «ustar» в TAR-заголовке на смещении 257.
        if (header.Length < 265)
        {
            return false;
        }

        var magic = Encoding.ASCII.GetString(header.Slice(257, 5));
        return magic.StartsWith("ustar", StringComparison.Ordinal);
    }

    private static bool IsMostlyText(ReadOnlySpan<byte> data)
    {
        if (data.Length == 0)
        {
            return false;
        }

        var nonPrintable = 0;
        foreach (var b in data)
        {
            if (b == 0)
            {
                return false;
            }

            if (b < 9 || (b > 13 && b < 32))
            {
                nonPrintable++;
            }
        }

        return nonPrintable < data.Length / 20;
    }

    private static bool LooksLikeScatter(string filePath)
    {
        try
        {
            using var stream = File.OpenRead(filePath);
            using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
            for (var i = 0; i < 10; i++)
            {
                var line = reader.ReadLine();
                if (line is null)
                {
                    break;
                }

                if (line.Contains("MTK_PLATFORM", StringComparison.OrdinalIgnoreCase) ||
                    line.Contains("- partition_index:", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
        }
        catch (IOException)
        {
        }

        return false;
    }

    private static bool LooksLikeRawProgramXml(string filePath)
    {
        try
        {
            var text = File.ReadAllText(filePath, Encoding.UTF8);
            return text.Contains("<program", StringComparison.OrdinalIgnoreCase) ||
                   text.Contains("rawprogram", StringComparison.OrdinalIgnoreCase) ||
                   text.Contains("patch", StringComparison.OrdinalIgnoreCase) && text.Contains("filename", StringComparison.OrdinalIgnoreCase);
        }
        catch (IOException)
        {
            return false;
        }
    }
}
