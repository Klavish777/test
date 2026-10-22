using System.Diagnostics;
using NexusFirmware.Core.Abstractions;

namespace NexusFirmware.App.Services;

/// <summary>
/// Публикует ошибки привязок WPF (PresentationTraceSources) в общий журнал.
/// В обычной сборке WPF пишет их только в отладочный вывод, поэтому без этого
/// слушателя причину «пустого» интерфейса невозможно найти по журналу.
/// </summary>
public static class BindingDiagnostics
{
    private static LogBusTraceListener? _listener;

    /// <summary>Подключает слушателя один раз за процесс. Повторные вызовы безопасны.</summary>
    public static void Attach(ILogBus log)
    {
        if (_listener is not null)
        {
            return;
        }

        try
        {
            PresentationTraceSources.Refresh();
            var source = PresentationTraceSources.DataBindingSource;
            _listener = new LogBusTraceListener(log);
            source.Listeners.Add(_listener);
            source.Switch.Level = SourceLevels.Error;
        }
        catch (Exception ex)
        {
            // Диагностика привязок не должна мешать запуску приложения.
            log.Warn("UI", "Не удалось включить журналирование ошибок привязок: " + ex.Message);
        }
    }

    private sealed class LogBusTraceListener : TraceListener
    {
        private readonly ILogBus _log;

        public LogBusTraceListener(ILogBus log)
        {
            _log = log;
        }

        public override void Write(string? message)
        {
            // WPF вызывает Write для фрагментов; строка приходит в WriteLine.
        }

        public override void WriteLine(string? message)
        {
            if (string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            _log.Warn("Binding", message.Trim());
        }
    }
}
