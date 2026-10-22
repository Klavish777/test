using NexusFirmware.App.Mvvm;
using NexusFirmware.App.Services;
using NexusFirmware.Core.Abstractions;

namespace NexusFirmware.App.ViewModels;

/// <summary>База для разделов: единая обработка ошибок и уведомление в журнал.</summary>
public abstract class PageViewModelBase : ObservableObject, IPageViewModel
{
    protected PageViewModelBase(ILogBus log, DialogService dialogs)
    {
        Log = log;
        Dialogs = dialogs;
    }

    protected ILogBus Log { get; }

    protected DialogService Dialogs { get; }

    public abstract string Title { get; }

    public virtual void OnActivated()
    {
    }

    protected void Handle(string operation, Exception ex)
    {
        Log.Error(Title, $"{operation}: {ex.Message}");
        Dialogs.Error(operation, ex.Message);
    }

    protected void Notify(string message)
    {
        Log.Info(Title, message);
    }
}
