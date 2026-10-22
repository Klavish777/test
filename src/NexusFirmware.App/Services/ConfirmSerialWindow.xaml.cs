using System.Windows;

namespace NexusFirmware.App.Services;

public partial class ConfirmSerialWindow : Window
{
    private readonly string _expected;

    public ConfirmSerialWindow(string title, string message, string expectedSerial)
    {
        InitializeComponent();
        _expected = expectedSerial;
        TitleText.Text = title;
        MessageText.Text = message;
        SerialRun.Text = expectedSerial;
        Loaded += (_, _) => SerialBox.Focus();
    }

    private void OnConfirm(object sender, RoutedEventArgs e)
    {
        var entered = SerialBox.Text.Trim();
        if (!string.Equals(entered, _expected, StringComparison.OrdinalIgnoreCase))
        {
            ErrorText.Visibility = Visibility.Visible;
            return;
        }

        DialogResult = true;
        Close();
    }

    private void OnCancel(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
        Close();
    }
}
