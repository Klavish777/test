using System.Collections.Concurrent;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Core.Jobs;

public sealed class JobStepDefinition
{
    public required OperationStep Info { get; init; }

    /// <summary>Можно ли безопасно прервать операцию на этом шаге (например, между файлами, но не во время записи раздела).</summary>
    public bool IsCancellable { get; init; } = true;

    public required Func<JobContext, CancellationToken, Task> Execute { get; init; }
}

public sealed class JobRequest
{
    public string Title { get; init; } = "Операция";
    public string DeviceSummary { get; init; } = "";
    public string FirmwareSummary { get; init; } = "";
    public bool IsDryRun { get; init; }
    public bool AllowCancellation { get; init; } = true;
    public IReadOnlyList<JobStepDefinition> Steps { get; init; } = Array.Empty<JobStepDefinition>();
}

/// <summary>Контекст выполнения задания: журнал, прогресс и токен отмены.</summary>
public sealed class JobContext
{
    private readonly Action<LogLevel, string> _log;
    private readonly Action<OperationProgress> _progress;

    internal JobContext(Guid jobId, Action<LogLevel, string> log, Action<OperationProgress> progress)
    {
        JobId = jobId;
        _log = log;
        _progress = progress;
    }

    public Guid JobId { get; }

    public void Log(string message, LogLevel level = LogLevel.Information) => _log(level, message);

    public void Report(double percent, string message, string? step = null) =>
        _progress(OperationProgress.Create(percent, message, step));
}

public sealed class JobRun
{
    private readonly List<ReportEntry> _entries = new();
    private readonly CancellationTokenSource _cts = new();

    public JobRun(JobRequest request)
    {
        Request = request;
        Id = Guid.NewGuid();
        StartedAt = DateTimeOffset.Now;
        Entries = _entries.AsReadOnly();
    }

    public Guid Id { get; }
    public JobRequest Request { get; }
    public OperationState State { get; internal set; } = OperationState.Queued;
    public DateTimeOffset StartedAt { get; }
    public DateTimeOffset? FinishedAt { get; internal set; }
    public double Percent { get; internal set; }
    public string StatusMessage { get; internal set; } = "В очереди";
    public string? CurrentStep { get; internal set; }
    public string? FailedReason { get; internal set; }
    public IReadOnlyList<ReportEntry> Entries { get; }
    public CancellationToken Token => _cts.Token;
    public bool IsTerminal => State is OperationState.Succeeded or OperationState.Failed or OperationState.Cancelled or OperationState.Blocked;

    internal bool CancellationRequested { get; private set; }

    internal void AddEntry(LogLevel level, string message)
    {
        lock (_entries)
        {
            _entries.Add(new ReportEntry(DateTimeOffset.Now, level.ToString(), Safety.Redactor.MaskText(message)));
        }
    }

    internal bool TryCancel()
    {
        if (IsTerminal || CancellationRequested || !Request.AllowCancellation)
        {
            return false;
        }

        CancellationRequested = true;
        _cts.Cancel();
        return true;
    }
}

public sealed class JobStateChangedEventArgs(JobRun job) : EventArgs
{
    public JobRun Job { get; } = job;
}

/// <summary>Последовательная очередь заданий. Параллельная запись на устройства не допускается.</summary>
public sealed class JobQueue : IAsyncDisposable
{
    private readonly ConcurrentQueue<JobRequest> _pending = new();
    private readonly ILogBus _logBus;
    private readonly SemaphoreSlim _signal = new(0);
    private readonly CancellationTokenSource _shutdown = new();
    private readonly List<JobRun> _history = new();
    private Task? _worker;

    public JobQueue(ILogBus logBus)
    {
        _logBus = logBus;
    }

    public event EventHandler<JobStateChangedEventArgs>? JobChanged;

    public JobRun? Current { get; private set; }

    public IReadOnlyList<JobRun> History
    {
        get
        {
            lock (_history)
            {
                return _history.ToArray();
            }
        }
    }

    public int PendingCount => _pending.Count;

    public JobRun Enqueue(JobRequest request)
    {
        var run = new JobRun(request);
        lock (_history)
        {
            _history.Add(run);
        }

        _pending.Enqueue(request);
        _pendingRuns.Enqueue(run);
        Raise(run);
        _logBus.Info("JobQueue", $"Задание добавлено в очередь: {request.Title}");
        _signal.Release();
        _worker ??= Task.Run(ProcessLoopAsync);
        return run;
    }

    private readonly ConcurrentQueue<JobRun> _pendingRuns = new();

    public bool Cancel(Guid jobId)
    {
        var run = History.FirstOrDefault(r => r.Id == jobId);
        if (run is null)
        {
            return false;
        }

        var cancelled = run.TryCancel();
        if (cancelled)
        {
            _logBus.Warn("JobQueue", $"Запрошена отмена задания: {run.Request.Title}");
            Raise(run);
        }

        return cancelled;
    }

    private async Task ProcessLoopAsync()
    {
        while (!_shutdown.IsCancellationRequested)
        {
            try
            {
                await _signal.WaitAsync(_shutdown.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }

            if (!_pendingRuns.TryDequeue(out var run))
            {
                continue;
            }

            _pending.TryDequeue(out _);
            Current = run;
            await ExecuteAsync(run).ConfigureAwait(false);
            Current = null;
        }
    }

    private async Task ExecuteAsync(JobRun run)
    {
        run.State = OperationState.Running;
        run.StatusMessage = "Выполняется";
        Raise(run);

        var context = new JobContext(run.Id,
            (level, message) =>
            {
                run.AddEntry(level, message);
                Raise(run);
            },
            progress =>
            {
                run.Percent = progress.Percent;
                run.StatusMessage = progress.Message;
                run.CurrentStep = progress.CurrentStep;
                Raise(run);
            });

        try
        {
            var total = Math.Max(run.Request.Steps.Count, 1);
            var index = 0;

            foreach (var step in run.Request.Steps)
            {
                if (run.Token.IsCancellationRequested)
                {
                    break;
                }

                index++;
                run.CurrentStep = step.Info.Title;
                context.Report((index - 1) * 100.0 / total, step.Info.Title, step.Info.Title);
                context.Log($"Шаг {index}/{total}: {step.Info.Title}", LogLevel.Information);

                await step.Execute(context, run.Token).ConfigureAwait(false);
                context.Report(index * 100.0 / total, $"Завершено: {step.Info.Title}", step.Info.Title);
            }

            if (run.Token.IsCancellationRequested)
            {
                run.State = OperationState.Cancelled;
                run.StatusMessage = "Отменено пользователем";
                context.Log("Операция отменена пользователем.", LogLevel.Warning);
            }
            else
            {
                run.State = OperationState.Succeeded;
                run.Percent = 100;
                run.StatusMessage = run.Request.IsDryRun ? "Проверка завершена (Dry Run)" : "Завершено успешно";
                context.Log("Операция завершена успешно.", LogLevel.Information);
            }
        }
        catch (OperationCanceledException)
        {
            run.State = OperationState.Cancelled;
            run.StatusMessage = "Отменено пользователем";
        }
        catch (Exception ex)
        {
            run.State = OperationState.Failed;
            run.FailedReason = ex.Message;
            run.StatusMessage = "Ошибка: " + ex.Message;
            run.AddEntry(LogLevel.Error, ex.ToString());
            _logBus.Error("JobQueue", $"Задание «{run.Request.Title}» завершилось ошибкой: {ex.Message}");
        }
        finally
        {
            run.FinishedAt = DateTimeOffset.Now;
            Raise(run);
        }
    }

    private void Raise(JobRun run)
    {
        try
        {
            JobChanged?.Invoke(this, new JobStateChangedEventArgs(run));
        }
        catch (Exception ex)
        {
            _logBus.Error("JobQueue", "Ошибка обработчика изменения задания: " + ex.Message);
        }
    }

    public OperationReport BuildReport(JobRun run, IEnumerable<string>? artifacts = null) => new()
    {
        Title = run.Request.Title,
        DeviceSummary = run.Request.DeviceSummary,
        FirmwareSummary = run.Request.FirmwareSummary,
        State = run.State,
        StartedAt = run.StartedAt,
        FinishedAt = run.FinishedAt ?? DateTimeOffset.Now,
        Entries = run.Entries,
        FailedReason = run.FailedReason,
        IsDryRun = run.Request.IsDryRun,
        Artifacts = artifacts?.ToArray() ?? Array.Empty<string>()
    };

    public async ValueTask DisposeAsync()
    {
        _shutdown.Cancel();
        if (_worker is not null)
        {
            try
            {
                await _worker.ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
            }
        }

        _signal.Dispose();
        _shutdown.Dispose();
    }
}
