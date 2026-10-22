using System.Diagnostics;
using System.Text;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Safety;

namespace NexusFirmware.Infrastructure.Processes;

/// <summary>
/// Запуск внешних инструментов с безопасной передачей аргументов (списком, без shell),
/// тайм-аутом, перехватом stdout/stderr и маскированием чувствительных данных.
/// </summary>
public sealed class ProcessRunner : IProcessRunner
{
    /// <summary>Максимальный объём перехваченного вывода, чтобы не исчерпать память.</summary>
    public int MaxCapturedChars { get; init; } = 512 * 1024;

    public async Task<ProcessResult> RunAsync(ProcessRequest request, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(request.FileName))
        {
            return ProcessResult.NotStarted(request.FileName ?? "", "Не указан исполняемый файл.");
        }

        var startedAt = DateTimeOffset.Now;
        var stdout = new StringBuilder();
        var stderr = new StringBuilder();
        var psi = new ProcessStartInfo
        {
            FileName = request.FileName,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        foreach (var argument in request.Arguments)
        {
            psi.ArgumentList.Add(argument);
        }

        if (!string.IsNullOrWhiteSpace(request.WorkingDirectory) && Directory.Exists(request.WorkingDirectory))
        {
            psi.WorkingDirectory = request.WorkingDirectory;
        }

        if (request.Environment is not null)
        {
            foreach (var pair in request.Environment)
            {
                psi.Environment[pair.Key] = pair.Value;
            }
        }

        using var process = new Process { StartInfo = psi, EnableRaisingEvents = true };

        void Append(StringBuilder target, string? line)
        {
            if (line is null)
            {
                return;
            }

            lock (target)
            {
                if (target.Length < MaxCapturedChars)
                {
                    target.AppendLine(request.RedactOutput ? Redactor.MaskText(line) : line);
                }
            }
        }

        process.OutputDataReceived += (_, e) => Append(stdout, e.Data);
        process.ErrorDataReceived += (_, e) => Append(stderr, e.Data);

        try
        {
            if (!process.Start())
            {
                return ProcessResult.NotStarted(request.FileName, "Процесс не запустился.");
            }
        }
        catch (Exception ex)
        {
            return ProcessResult.NotStarted(request.FileName, ex.Message);
        }

        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        try
        {
            // Закрываем stdin: инструменты вроде adb не должны ждать ввода.
            try
            {
                process.StandardInput.Close();
            }
            catch (IOException)
            {
            }

            using var timeoutCts = new CancellationTokenSource(request.Timeout);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(timeoutCts.Token, cancellationToken);

            try
            {
                await process.WaitForExitAsync(linked.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                var timedOut = timeoutCts.IsCancellationRequested && !cancellationToken.IsCancellationRequested;
                TryKill(process);

                lock (stdout)
                lock (stderr)
                {
                    return new ProcessResult
                    {
                        FileName = request.FileName,
                        Arguments = request.Arguments,
                        ExitCode = -1,
                        StandardOutput = stdout.ToString(),
                        StandardError = stderr.ToString(),
                        TimedOut = timedOut,
                        Cancelled = !timedOut,
                        Duration = DateTimeOffset.Now - startedAt,
                        StartedAt = startedAt
                    };
                }
            }

            // Дадим процессу дописать асинхронные потоки.
            await Task.Delay(30).ConfigureAwait(false);

            lock (stdout)
            lock (stderr)
            {
                return new ProcessResult
                {
                    FileName = request.FileName,
                    Arguments = request.Arguments,
                    ExitCode = process.ExitCode,
                    StandardOutput = stdout.ToString(),
                    StandardError = stderr.ToString(),
                    Duration = DateTimeOffset.Now - startedAt,
                    StartedAt = startedAt
                };
            }
        }
        finally
        {
            process.OutputDataReceived -= null;
            process.ErrorDataReceived -= null;
        }
    }

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (Exception)
        {
            // Процесс уже завершился или недоступен.
        }
    }

    public async Task<bool> IsAvailableAsync(string fileName, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(fileName))
        {
            return false;
        }

        if (Path.IsPathRooted(fileName))
        {
            return File.Exists(fileName);
        }

        var result = await RunAsync(new ProcessRequest
        {
            FileName = fileName,
            Arguments = ["version"],
            Timeout = TimeSpan.FromSeconds(8),
            Description = $"{fileName} version"
        }, cancellationToken).ConfigureAwait(false);

        return result.Started;
    }
}
