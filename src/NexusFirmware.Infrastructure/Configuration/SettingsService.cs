namespace NexusFirmware.Infrastructure.Configuration;

/// <summary>Текущие настройки приложения с сохранением в файл и уведомлением подписчиков.</summary>
public sealed class SettingsService
{
    private readonly SettingsStore _store;

    public SettingsService(SettingsStore store)
    {
        _store = store;
        Current = store.Load();
    }

    public AppSettings Current { get; private set; }

    public event EventHandler? Changed;

    public void Save(AppSettings settings)
    {
        _store.Save(settings);
        Current = settings;
        Changed?.Invoke(this, EventArgs.Empty);
    }

    public void SaveCurrent() => Save(Current);

    public void Update(Action<AppSettings> change)
    {
        change(Current);
        _store.Save(Current);
        Changed?.Invoke(this, EventArgs.Empty);
    }
}
