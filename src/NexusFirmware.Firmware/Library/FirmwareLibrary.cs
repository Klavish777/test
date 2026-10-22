using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using NexusFirmware.Firmware.Detection;
using NexusFirmware.Firmware.Samsung;
using NexusFirmware.Firmware.Ota;
using NexusFirmware.Firmware.Scatter;
using NexusFirmware.Infrastructure.Data;

namespace NexusFirmware.Firmware.Library;

public sealed class ImportOptions
{
    public bool ComputeHash { get; init; } = true;
    public bool SkipDuplicates { get; init; } = true;
    public string? Manufacturer { get; init; }
    public string? Model { get; init; }
    public string? Version { get; init; }
    public string? Region { get; init; }
    public string? Notes { get; init; }
}

public sealed record ImportResult(FirmwarePackage Package, bool IsDuplicate, IReadOnlyList<string> Messages);

/// <summary>
/// Каталог прошивок: импорт файлов и каталогов, метаданные, SHA-256, проверка целостности.
/// Оригинальные файлы не изменяются; копирование в библиотеку — только по явному запросу.
/// </summary>
public sealed class FirmwareLibrary
{
    private static readonly HashSet<string> RecognizedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".zip", ".tar", ".md5", ".tar.md5", ".tgz", ".gz", ".lz4", ".img", ".bin", ".xml", ".txt", ".ap", ".bl", ".cp", ".csc"
    };

    private readonly FirmwareRepository _repository;
    private readonly ILogBus _log;

    public FirmwareLibrary(FirmwareRepository repository, ILogBus log)
    {
        _repository = repository;
        _log = log;
    }

    public IReadOnlyList<FirmwarePackage> GetPackages() => _repository.GetAll();

    public async Task<ImportResult> ImportAsync(
        string filePath,
        ImportOptions? options = null,
        IProgress<(double Percent, string Message)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        options ??= new ImportOptions();

        if (!InputValidator.IsReadableFile(filePath))
        {
            throw new FileNotFoundException("Файл прошивки не найден или пуст.", filePath);
        }

        var info = new FileInfo(filePath);
        var format = FormatDetector.Detect(filePath);
        progress?.Report((5, "Формат определён: " + format));

        var messages = new List<string>();
        var metadata = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        string? sha256 = null;
        if (options.ComputeHash)
        {
            progress?.Report((15, "Вычисление SHA-256…"));
            var hashProgress = new Progress<double>(p => progress?.Report((15 + p * 0.6, $"SHA-256: {p:0}%")));
            sha256 = await Hashing.Sha256FileAsync(filePath, hashProgress, cancellationToken).ConfigureAwait(false);

            if (options.SkipDuplicates)
            {
                var duplicates = _repository.FindBySha256(sha256);
                if (duplicates.Count > 0)
                {
                    messages.Add($"Файл с таким SHA-256 уже есть в каталоге: {duplicates[0].DisplayName}.");
                    progress?.Report((100, "Дубликат найден"));
                    return new ImportResult(duplicates[0], true, messages);
                }
            }
        }

        progress?.Report((80, "Чтение метаданных…"));

        string? manufacturer = options.Manufacturer;
        string? model = options.Model;
        string? version = options.Version;
        string? region = options.Region;
        string? codename = null;
        string? buildNumber = null;
        string? androidVersion = null;
        var components = new List<FirmwareComponent>();

        switch (format)
        {
            case FirmwareFormat.SamsungAp:
            case FirmwareFormat.SamsungBl:
            case FirmwareFormat.SamsungCp:
            case FirmwareFormat.SamsungCsc:
            case FirmwareFormat.SamsungHomeCsc:
            case FirmwareFormat.TarMd5:
            case FirmwareFormat.Tar:
            case FirmwareFormat.Zip:
            {
                if (FileIsSamsungComponent(info.Name) || format is FirmwareFormat.TarMd5)
                {
                    var samsung = SamsungPackageAnalyzer.AnalyzeFile(filePath);
                    metadata["samsung.component"] = samsung.Component ?? "не распознан";
                    if (samsung.ModelCode is not null)
                    {
                        metadata["samsung.model"] = samsung.ModelCode;
                        model ??= samsung.ModelCode;
                    }

                    if (samsung.PdaVersion is not null)
                    {
                        metadata["samsung.pda"] = samsung.PdaVersion;
                        version ??= samsung.PdaVersion;
                    }

                    if (samsung.CscVersion is not null)
                    {
                        metadata["samsung.csc"] = samsung.CscVersion;
                    }

                    if (samsung.BootloaderBinary is not null)
                    {
                        metadata["samsung.binary"] = samsung.BootloaderBinary;
                    }

                    buildNumber ??= samsung.BuildNumber;
                    manufacturer ??= "Samsung";

                    foreach (var entry in samsung.Entries.Take(200))
                    {
                        components.Add(new FirmwareComponent
                        {
                            Name = Path.GetFileName(entry),
                            FileName = entry,
                            Format = FirmwareFormat.Image
                        });
                    }

                    messages.AddRange(samsung.Warnings);
                }
                break;
            }

            case FirmwareFormat.Scatter:
            {
                var scatter = ScatterParser.Parse(filePath);
                metadata["mtk.platform"] = scatter.Platform ?? "не указана";
                manufacturer ??= "MediaTek (OEM)";
                foreach (var partition in scatter.Partitions.Take(200))
                {
                    components.Add(new FirmwareComponent
                    {
                        Name = partition.PartitionName,
                        FileName = partition.FileName ?? "",
                        SizeBytes = partition.PartitionSize,
                        Format = FirmwareFormat.Image,
                        Partition = partition.PartitionName
                    });
                }

                messages.AddRange(scatter.Warnings);
                break;
            }

            case FirmwareFormat.PayloadBin:
            {
                var payload = PayloadParserSafe(filePath, messages);
                if (payload is not null)
                {
                    metadata["ota.version"] = payload.Version.ToString();
                    metadata["ota.partitions"] = payload.Partitions.Count.ToString();
                    foreach (var partition in payload.Partitions.Take(200))
                    {
                        components.Add(new FirmwareComponent
                        {
                            Name = partition.Name,
                            FileName = $"payload.bin:{partition.Name}",
                            SizeBytes = partition.SizeBytes,
                            Format = FirmwareFormat.Image,
                            Partition = partition.Name
                        });
                    }
                }

                break;
            }

            case FirmwareFormat.SparseImage:
            {
                try
                {
                    var sparse = Images.SparseImageParser.Read(filePath);
                    metadata["sparse.blocks"] = sparse.TotalBlocks.ToString();
                    metadata["sparse.block_size"] = sparse.BlockSize.ToString();
                }
                catch (InvalidDataException ex)
                {
                    messages.Add("Sparse-заголовок не прочитан: " + ex.Message);
                }

                break;
            }

            case FirmwareFormat.RawProgramXml:
            {
                try
                {
                    var document = Qualcomm.RawProgramParser.Parse(filePath);
                    metadata["qualcomm.programs"] = document.Programs.Count.ToString();
                    if (document.ProductName is not null)
                    {
                        metadata["qualcomm.product"] = document.ProductName;
                    }

                    messages.AddRange(document.Warnings);
                }
                catch (Exception ex) when (ex is InvalidOperationException or System.Xml.XmlException)
                {
                    messages.Add("XML не прочитан: " + ex.Message);
                }

                break;
            }
        }

        if (string.IsNullOrWhiteSpace(manufacturer))
        {
            manufacturer = GuessManufacturer(info.Name);
        }

        metadata["detected.format"] = format.ToString();

        var package = new FirmwarePackage
        {
            Id = sha256 is not null ? sha256[..Math.Min(32, sha256.Length)] : Guid.NewGuid().ToString("N"),
            DisplayName = info.Name,
            Manufacturer = manufacturer,
            Model = model,
            Region = region,
            Version = version,
            BuildNumber = buildNumber,
            Codename = codename,
            AndroidVersion = androidVersion,
            Format = format,
            FilePath = filePath,
            SizeBytes = info.Length,
            Sha256 = sha256,
            Integrity = sha256 is null ? IntegrityState.NotVerified : IntegrityState.Verified,
            Notes = options.Notes,
            Source = "Локальный файл",
            IsUserProvided = true,
            ImportedAt = DateTimeOffset.Now,
            LastCheckedAt = DateTimeOffset.Now,
            Components = components,
            Metadata = metadata
        };

        _repository.Upsert(package);
        _repository.AddImportHistory(package.Id, filePath, sha256, "import");
        _log.Info("Firmware", $"Импортирована прошивка: {info.Name} ({format}), SHA-256: {sha256?[..12] ?? "не вычислен"}…");
        progress?.Report((100, "Импорт завершён"));

        return new ImportResult(package, false, messages);
    }

    public async Task<IReadOnlyList<ImportResult>> ImportDirectoryAsync(
        string directory,
        bool recursive = false,
        ImportOptions? options = null,
        IProgress<(double Percent, string Message)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (!PathSafety.IsExistingDirectory(directory))
        {
            throw new DirectoryNotFoundException(directory);
        }

        var searchOption = recursive ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
        var files = Directory.EnumerateFiles(directory, "*", searchOption)
            .Where(f => RecognizedExtensions.Contains(Path.GetExtension(f)))
            .OrderBy(f => f, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var results = new List<ImportResult>();
        for (var i = 0; i < files.Length; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var index = i;
            var fileProgress = new Progress<(double Percent, string Message)>(p =>
                progress?.Report(((index * 100.0 / files.Length) + p.Percent / files.Length, $"{Path.GetFileName(files[index])}: {p.Message}")));

            try
            {
                results.Add(await ImportAsync(files[index], options, fileProgress, cancellationToken).ConfigureAwait(false));
            }
            catch (Exception ex) when (ex is IOException or InvalidDataException or UnauthorizedAccessException)
            {
                _log.Warn("Firmware", $"Пропущен файл {Path.GetFileName(files[i])}: {ex.Message}");
            }
        }

        progress?.Report((100, $"Обработано файлов: {results.Count} из {files.Length}"));
        return results;
    }

    public async Task<bool> VerifyIntegrityAsync(string firmwareId, CancellationToken cancellationToken = default)
    {
        var package = _repository.GetById(firmwareId) ?? throw new InvalidOperationException("Прошивка не найдена в каталоге.");
        if (string.IsNullOrWhiteSpace(package.FilePath) || !File.Exists(package.FilePath))
        {
            _log.Warn("Firmware", "Файл прошивки недоступен для проверки целостности.");
            return false;
        }

        var actual = await Hashing.Sha256FileAsync(package.FilePath, null, cancellationToken).ConfigureAwait(false);
        var match = string.Equals(actual, package.Sha256, StringComparison.OrdinalIgnoreCase);

        var updated = new FirmwarePackage
        {
            Id = package.Id,
            DisplayName = package.DisplayName,
            Manufacturer = package.Manufacturer,
            Model = package.Model,
            Region = package.Region,
            Version = package.Version,
            BuildNumber = package.BuildNumber,
            Codename = package.Codename,
            AndroidVersion = package.AndroidVersion,
            Format = package.Format,
            FilePath = package.FilePath,
            SizeBytes = package.SizeBytes,
            Sha256 = package.Sha256 ?? actual,
            Integrity = match ? IntegrityState.Verified : IntegrityState.Failed,
            Notes = package.Notes,
            Source = package.Source,
            IsUserProvided = package.IsUserProvided,
            ImportedAt = package.ImportedAt,
            LastCheckedAt = DateTimeOffset.Now,
            Components = package.Components,
            Metadata = package.Metadata
        };

        _repository.Upsert(updated);
        _log.Write(match ? LogLevel.Information : LogLevel.Warning, "Firmware",
            match
                ? $"SHA-256 подтверждён: {package.DisplayName}"
                : $"SHA-256 НЕ совпадает: {package.DisplayName}");
        return match;
    }

    public void AddNote(string firmwareId, string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        _repository.AddNote(firmwareId, text.Trim());
    }

    public IReadOnlyList<FirmwareNote> GetNotes(string firmwareId) => _repository.GetNotes(firmwareId);

    public void Remove(string firmwareId)
    {
        _repository.Delete(firmwareId);
        _log.Info("Firmware", "Запись удалена из каталога (файл на диске не изменялся).");
    }

    public static (long FreeBytes, string Root) GetFreeSpace(string path)
    {
        try
        {
            var full = Path.GetFullPath(path);
            var root = Path.GetPathRoot(full) ?? full;
            var drive = new DriveInfo(root);
            return (drive.AvailableFreeSpace, root);
        }
        catch (Exception)
        {
            return (0, path);
        }
    }

    private static PayloadInfo? PayloadParserSafe(string filePath, List<string> messages)
    {
        try
        {
            return Ota.PayloadParser.Read(filePath);
        }
        catch (Exception ex) when (ex is InvalidDataException or IOException)
        {
            messages.Add("Манифест payload.bin не прочитан: " + ex.Message);
            return null;
        }
    }

    private static bool FileIsSamsungComponent(string fileName)
    {
        var upper = fileName.ToUpperInvariant();
        return upper.StartsWith("AP_", StringComparison.Ordinal) || upper.StartsWith("BL_", StringComparison.Ordinal) ||
               upper.StartsWith("CP_", StringComparison.Ordinal) || upper.StartsWith("CSC_", StringComparison.Ordinal) ||
               upper.StartsWith("HOME_CSC_", StringComparison.Ordinal);
    }

    private static string? GuessManufacturer(string fileName)
    {
        var upper = fileName.ToUpperInvariant();
        var map = new (string Token, string Manufacturer)[]
        {
            ("SAMSUNG", "Samsung"), ("SM-", "Samsung"),
            ("XIAOMI", "Xiaomi"), ("REDMI", "Xiaomi"), ("POCO", "Xiaomi"), ("MIUI", "Xiaomi"),
            ("MOTOROLA", "Motorola"), ("ONEPLUS", "OnePlus"), ("PIXEL", "Google"),
            ("HUAWEI", "Huawei"), ("HONOR", "Honor"), ("OPPO", "OPPO"), ("REALME", "Realme"),
            ("VIVO", "Vivo"), ("INFINIX", "Infinix"), ("TECNO", "Tecno"), ("ZTE", "ZTE"), ("NUBIA", "Nubia")
        };

        foreach (var (token, manufacturer) in map)
        {
            if (upper.Contains(token, StringComparison.Ordinal))
            {
                return manufacturer;
            }
        }

        return null;
    }
}
