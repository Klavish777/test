using System.Diagnostics;
using System.Text.Json;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Reporting;
using NexusFirmware.Infrastructure.Configuration;
using NexusFirmware.Infrastructure.Data;
using System.IO;
using System.Collections.Generic;
using System.Linq;

namespace NexusFirmware.App.Services;

public sealed record SavedReport(string MarkdownPath, string JsonPath);

/// <summary>Сохранение отчётов в локальный каталог и регистрация в базе.</summary>
public sealed class ReportService
{
    private readonly AppPaths _paths;
    private readonly DiagnosticsRepository _repository;
    private readonly ILogBus _log;

    public ReportService(AppPaths paths, DiagnosticsRepository repository, ILogBus log)
    {
        _paths = paths;
        _repository = repository;
        _log = log;
    }

    public string ReportsDirectory => _paths.Reports;

    public IReadOnlyList<ReportSummary> GetRecentReports() => _repository.GetReports();

    public SavedReport Save(OperationReport report, string? customDirectory = null)
    {
        var directory = customDirectory ?? _paths.Reports;
        Directory.CreateDirectory(directory);

        var safeName = new string(report.Title.Select(c => Path.GetInvalidFileNameChars().Contains(c) ? '_' : c).ToArray());
        var stamp = DateTimeOffset.Now.ToString("yyyyMMdd_HHmmss");
        var basePath = Path.Combine(directory, $"{stamp}_{safeName}");

        var markdownPath = basePath + ".md";
        var jsonPath = basePath + ".json";

        File.WriteAllText(markdownPath, ReportWriter.ToMarkdown(report));
        File.WriteAllText(jsonPath, ReportWriter.ToJson(report));

        _repository.SaveReport(report, markdownPath);
        _log.Info("Reports", $"Отчёт сохранён: {Path.GetFileName(markdownPath)}");

        return new SavedReport(markdownPath, jsonPath);
    }

    public string SaveText(string title, string content, string extension = ".md")
    {
        Directory.CreateDirectory(_paths.Reports);
        var safeName = new string(title.Select(c => Path.GetInvalidFileNameChars().Contains(c) ? '_' : c).ToArray());
        var path = Path.Combine(_paths.Reports, $"{DateTimeOffset.Now:yyyyMMdd_HHmmss}_{safeName}{extension}");
        File.WriteAllText(path, content);
        _log.Info("Reports", $"Документ сохранён: {Path.GetFileName(path)}");
        return path;
    }

    public static void OpenInExplorer(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Process.Start(new ProcessStartInfo { FileName = path, UseShellExecute = true });
            }
            else if (File.Exists(path))
            {
                Process.Start(new ProcessStartInfo { FileName = "explorer.exe", Arguments = $"/select,\"{path}\"", UseShellExecute = true });
            }
        }
        catch (Exception)
        {
            // Открытие проводника не критично.
        }
    }
}
