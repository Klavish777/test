namespace NexusFirmware.App.Services;

/// <summary>Запрос навигации между разделами без циклических зависимостей ViewModel-ей.</summary>
public static class AppNavigation
{
    public static event EventHandler<string>? Requested;

    public static void Request(string sectionKey) => Requested?.Invoke(null, sectionKey);
}
