using System.Windows;
using Microsoft.Win32;

namespace NexusFirmware.App.Services;

/// <summary>Диалоги подтверждения и выбора файлов. Опасные операции требуют явного согласия.</summary>
public sealed class DialogService
{
    public bool Confirm(string title, string message, bool danger = false)
    {
        var result = MessageBox.Show(
            message,
            title,
            MessageBoxButton.YesNo,
            danger ? MessageBoxImage.Warning : MessageBoxImage.Question,
            MessageBoxResult.No);

        return result == MessageBoxResult.Yes;
    }

    /// <summary>Подтверждение вводом серийного номера: защита от случайной прошивки не того устройства.</summary>
    public bool ConfirmWithSerial(string title, string message, string expectedSerial, Window? owner = null)
    {
        var dialog = new ConfirmSerialWindow(title, message, expectedSerial)
        {
            Owner = owner ?? Application.Current?.MainWindow
        };

        return dialog.ShowDialog() == true;
    }

    public void Info(string title, string message) =>
        MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Information);

    public void Warn(string title, string message) =>
        MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Warning);

    public void Error(string title, string message) =>
        MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Error);

    public string? PickFile(string title, string filter = "Все файлы (*.*)|*.*")
    {
        var dialog = new OpenFileDialog
        {
            Title = title,
            Filter = filter,
            CheckFileExists = true,
            Multiselect = false
        };

        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    public IReadOnlyList<string> PickFiles(string title, string filter = "Все файлы (*.*)|*.*")
    {
        var dialog = new OpenFileDialog
        {
            Title = title,
            Filter = filter,
            CheckFileExists = true,
            Multiselect = true
        };

        return dialog.ShowDialog() == true ? dialog.FileNames : Array.Empty<string>();
    }

    public string? PickFolder(string title)
    {
        var dialog = new OpenFolderDialog
        {
            Title = title,
            Multiselect = false
        };

        return dialog.ShowDialog() == true ? dialog.FolderName : null;
    }

    public string? SaveFile(string title, string defaultFileName, string filter)
    {
        var dialog = new SaveFileDialog
        {
            Title = title,
            FileName = defaultFileName,
            Filter = filter,
            OverwritePrompt = true
        };

        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }
}
