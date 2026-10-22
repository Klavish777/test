using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NUnit.Framework;

namespace NexusFirmware.UnitTests;

/// <summary>Журнал в памяти для тестов.</summary>
public sealed class FakeLogBus : ILogBus
{
    private readonly List<LogEntry> _entries = new();

    public event EventHandler<LogEntry>? Appended;

    public IReadOnlyList<LogEntry> Recent
    {
        get
        {
            lock (_entries)
            {
                return _entries.ToArray();
            }
        }
    }

    public void Write(LogLevel level, string source, string message)
    {
        var entry = new LogEntry(DateTimeOffset.Now, level, source, message);
        lock (_entries)
        {
            _entries.Add(entry);
        }

        Appended?.Invoke(this, entry);
    }

    public void Clear()
    {
        lock (_entries)
        {
            _entries.Clear();
        }
    }
}

/// <summary>Временный каталог, удаляемый после теста.</summary>
public sealed class TempDirectory : IDisposable
{
    public TempDirectory()
    {
        Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "nexus_tests_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path);
    }

    public string Path { get; }

    public string File(string name) => System.IO.Path.Combine(Path, name);

    public void Dispose()
    {
        try
        {
            Directory.Delete(Path, recursive: true);
        }
        catch (IOException)
        {
        }
    }
}

/// <summary>Поддельный запуск процессов: возвращает заранее заданные ответы по имени инструмента.</summary>
public sealed class FakeProcessRunner : IProcessRunner
{
    private readonly Dictionary<string, string> _responses = new(StringComparer.OrdinalIgnoreCase);

    public List<ProcessRequest> Requests { get; } = new();

    public FakeProcessRunner With(string tool, string output)
    {
        _responses[tool] = output;
        return this;
    }

    public Task<ProcessResult> RunAsync(ProcessRequest request, CancellationToken cancellationToken = default)
    {
        Requests.Add(request);
        var key = System.IO.Path.GetFileName(request.FileName);
        var output = _responses.TryGetValue(key, out var value) ? value : string.Empty;

        return Task.FromResult(new ProcessResult
        {
            FileName = request.FileName,
            Arguments = request.Arguments,
            ExitCode = 0,
            StandardOutput = output,
            Started = true,
            Duration = TimeSpan.FromMilliseconds(5)
        });
    }

    public Task<bool> IsAvailableAsync(string fileName, CancellationToken cancellationToken = default) =>
        Task.FromResult(_responses.ContainsKey(System.IO.Path.GetFileName(fileName)));
}
