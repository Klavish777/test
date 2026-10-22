using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;
using NexusFirmware.Core.Models;

namespace NexusFirmware.App.Converters;

public sealed class BoolToVisibilityConverter : IValueConverter
{
    public bool Invert { get; set; }

    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var flag = value is bool b && b;
        if (Invert)
        {
            flag = !flag;
        }

        return flag ? Visibility.Visible : Visibility.Collapsed;
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        value is Visibility visibility && visibility == Visibility.Visible;
}

public sealed class NullToVisibilityConverter : IValueConverter
{
    public bool Invert { get; set; }

    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var hasValue = value is not null && (value is not string s || !string.IsNullOrWhiteSpace(s));
        if (Invert)
        {
            hasValue = !hasValue;
        }

        return hasValue ? Visibility.Visible : Visibility.Collapsed;
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Binding.DoNothing;
}

public sealed class SeverityToBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) => value switch
    {
        CompatibilitySeverity.Blocking => (Brush)Application.Current.Resources["DangerBrush"],
        CompatibilitySeverity.Warning => (Brush)Application.Current.Resources["WarningBrush"],
        _ => (Brush)Application.Current.Resources["AccentBrush"]
    };

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) => Binding.DoNothing;
}

public sealed class LogLevelToBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) => value switch
    {
        LogLevel.Error or LogLevel.Critical => (Brush)Application.Current.Resources["DangerBrush"],
        LogLevel.Warning => (Brush)Application.Current.Resources["WarningBrush"],
        LogLevel.Debug or LogLevel.Trace => (Brush)Application.Current.Resources["MutedBrush"],
        _ => (Brush)Application.Current.Resources["SuccessBrush"]
    };

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) => Binding.DoNothing;
}

public sealed class StateToBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var text = value?.ToString() ?? string.Empty;
        if (text.Contains("Ошибка", StringComparison.OrdinalIgnoreCase) || text.Contains("заблок", StringComparison.OrdinalIgnoreCase) ||
            text.Contains("не найден", StringComparison.OrdinalIgnoreCase))
        {
            return (Brush)Application.Current.Resources["DangerBrush"];
        }

        if (text.Contains("Отмен", StringComparison.OrdinalIgnoreCase) || text.Contains("Ожида", StringComparison.OrdinalIgnoreCase) ||
            text.Contains("очеред", StringComparison.OrdinalIgnoreCase))
        {
            return (Brush)Application.Current.Resources["WarningBrush"];
        }

        if (text.Contains("Подключено", StringComparison.OrdinalIgnoreCase) || text.Contains("успеш", StringComparison.OrdinalIgnoreCase) ||
            text.Contains("в порядке", StringComparison.OrdinalIgnoreCase))
        {
            return (Brush)Application.Current.Resources["SuccessBrush"];
        }

        return (Brush)Application.Current.Resources["MutedBrush"];
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) => Binding.DoNothing;
}

public sealed class InverseBoolConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) => value is bool b && !b;

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) => value is bool b && !b;
}
