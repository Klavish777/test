using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Archives;
using NexusFirmware.Firmware.Detection;

namespace NexusFirmware.Firmware.Comparison;

public sealed class VersionComparison
{
    public required FirmwarePackage Left { get; init; }
    public required FirmwarePackage Right { get; init; }
    public required IReadOnlyList<ComparisonRow> Rows { get; init; }
    public required IReadOnlyList<string> OnlyInLeft { get; init; }
    public required IReadOnlyList<string> OnlyInRight { get; init; }
    public required IReadOnlyList<string> SizeDifferences { get; init; }
    public required IReadOnlyList<string> Notes { get; init; }

    public bool AreIdenticalByHash =>
        !string.IsNullOrWhiteSpace(Left.Sha256) &&
        string.Equals(Left.Sha256, Right.Sha256, StringComparison.OrdinalIgnoreCase);
}

public sealed record ComparisonRow(string Property, string Left, string Right, bool Differs);

/// <summary>Сравнение двух сборок прошивки: метаданные, хеши, содержимое архивов и размеры.</summary>
public static class FirmwareComparer
{
    public static VersionComparison Compare(FirmwarePackage left, FirmwarePackage right, bool compareArchiveContents = true)
    {
        var rows = new List<ComparisonRow>
        {
            Row("Название", left.DisplayName, right.DisplayName),
            Row("Производитель", left.Manufacturer, right.Manufacturer),
            Row("Модель", left.Model, right.Model),
            Row("Кодовое имя", left.Codename, right.Codename),
            Row("Версия", left.Version, right.Version),
            Row("Сборка", left.BuildNumber, right.BuildNumber),
            Row("Регион", left.Region, right.Region),
            Row("Android", left.AndroidVersion, right.AndroidVersion),
            Row("Формат", left.FormatText, right.FormatText),
            Row("Размер", left.SizeText, right.SizeText),
            Row("SHA-256", Short(left.Sha256), Short(right.Sha256)),
            Row("Целостность", left.IntegrityText, right.IntegrityText),
            Row("Дата импорта", left.ImportedAt.ToString("yyyy-MM-dd HH:mm"), right.ImportedAt.ToString("yyyy-MM-dd HH:mm")),
            Row("Файл", left.FilePath, right.FilePath)
        };

        var onlyLeft = new List<string>();
        var onlyRight = new List<string>();
        var differences = new List<string>();
        var notes = new List<string>();

        if (compareArchiveContents)
        {
            var leftEntries = TryReadEntries(left);
            var rightEntries = TryReadEntries(right);

            if (leftEntries is not null && rightEntries is not null)
            {
                var leftMap = leftEntries.ToDictionary(e => e.Name, e => e.Size, StringComparer.OrdinalIgnoreCase);
                var rightMap = rightEntries.ToDictionary(e => e.Name, e => e.Size, StringComparer.OrdinalIgnoreCase);

                onlyLeft.AddRange(leftMap.Keys.Where(k => !rightMap.ContainsKey(k)));
                onlyRight.AddRange(rightMap.Keys.Where(k => !leftMap.ContainsKey(k)));

                foreach (var pair in leftMap.Where(p => rightMap.ContainsKey(p.Key)))
                {
                    var rightSize = rightMap[pair.Key];
                    if (pair.Value != rightSize)
                    {
                        differences.Add($"{pair.Key}: {SizeFormatting.HumanReadable(pair.Value)} → {SizeFormatting.HumanReadable(rightSize)}");
                    }
                }
            }
            else
            {
                notes.Add("Содержимое архивов не сравнивалось: один из файлов недоступен или не является архивом.");
            }
        }

        if (!string.IsNullOrWhiteSpace(left.Sha256) && left.Sha256 == right.Sha256)
        {
            notes.Add("SHA-256 сборок совпадает: это один и тот же файл.");
        }

        if (!string.IsNullOrWhiteSpace(left.Version) && !string.IsNullOrWhiteSpace(right.Version) &&
            !string.Equals(left.Version, right.Version, StringComparison.OrdinalIgnoreCase))
        {
            notes.Add($"Версии различаются: «{left.Version}» и «{right.Version}». Направление обновления определяется вручную: строки версий не всегда сравнимы лексикографически.");
        }

        return new VersionComparison
        {
            Left = left,
            Right = right,
            Rows = rows,
            OnlyInLeft = onlyLeft.OrderBy(s => s, StringComparer.OrdinalIgnoreCase).ToArray(),
            OnlyInRight = onlyRight.OrderBy(s => s, StringComparer.OrdinalIgnoreCase).ToArray(),
            SizeDifferences = differences,
            Notes = notes
        };
    }

    private static IReadOnlyList<(string Name, long Size)>? TryReadEntries(FirmwarePackage package)
    {
        if (string.IsNullOrWhiteSpace(package.FilePath) || !File.Exists(package.FilePath))
        {
            return null;
        }

        try
        {
            var format = FormatDetector.Detect(package.FilePath);
            return format switch
            {
                FirmwareFormat.Zip => ZipInspector.Inspect(package.FilePath).Entries
                    .Where(e => !e.IsDirectory).Select(e => (e.FullName, e.Length)).ToArray(),
                FirmwareFormat.Tar or FirmwareFormat.TarMd5 => TarInspector.InspectFile(package.FilePath).Entries
                    .Where(e => !e.IsDirectory).Select(e => (e.FullName, e.Length)).ToArray(),
                _ => null
            };
        }
        catch (Exception ex) when (ex is IOException or InvalidDataException)
        {
            return null;
        }
    }

    private static ComparisonRow Row(string property, string? left, string? right)
    {
        var l = left ?? "—";
        var r = right ?? "—";
        return new ComparisonRow(property, l, r, !string.Equals(l, r, StringComparison.Ordinal));
    }

    private static string Short(string? hash) =>
        string.IsNullOrWhiteSpace(hash) ? "—" : hash.Length > 16 ? hash[..16] + "…" : hash;
}
