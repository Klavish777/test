using System.Text.RegularExpressions;
using NUnit.Framework;

namespace NexusFirmware.UnitTests;

/// <summary>
/// Статическая проверка XAML-привязок: свойства, к которым WPF по умолчанию привязывается
/// двусторонне (TextBox.Text, CheckBox.IsChecked, ComboBox.SelectedItem, ProgressBar.Value и т.п.),
/// обязаны иметь публичный сеттер. Иначе при запуске возникает
/// «A TwoWay or OneWayToSource binding cannot work on the read-only property …»,
/// и окно показывает ошибку вместо работы.
/// </summary>
[TestFixture]
public sealed class XamlBindingTests
{
    /// <summary>Элементы и их свойства, для которых WPF использует TwoWay по умолчанию.</summary>
    private static readonly Dictionary<string, string[]> TwoWayByDefault = new(StringComparer.Ordinal)
    {
        ["TextBox"] = ["Text"],
        ["CheckBox"] = ["IsChecked"],
        ["RadioButton"] = ["IsChecked"],
        ["ToggleButton"] = ["IsChecked"],
        ["ComboBox"] = ["SelectedItem", "SelectedValue", "SelectedIndex", "Text"],
        ["ListBox"] = ["SelectedItem", "SelectedValue", "SelectedIndex"],
        ["ListView"] = ["SelectedItem"],
        ["TabControl"] = ["SelectedIndex", "SelectedItem"],
        ["Slider"] = ["Value"],
        ["ProgressBar"] = ["Value"],
        ["ScrollBar"] = ["Value"],
        ["DatePicker"] = ["SelectedDate", "Text"],
        ["Calendar"] = ["SelectedDate"],
        ["Expander"] = ["IsExpanded"],
        ["MenuItem"] = ["IsChecked"],
        ["DataGrid"] = ["SelectedItem", "SelectedIndex"]
    };

    [Test]
    public void TwoWayBindingsTargetWritableProperties()
    {
        var root = FindRepositoryRoot();
        if (root is null)
        {
            Assert.Ignore("Каталог репозитория не найден: проверка XAML выполняется только из исходников.");
            return;
        }

        var appDirectory = Path.Combine(root, "src", "NexusFirmware.App");
        var viewToViewModel = ReadViewToViewModelMap(Path.Combine(appDirectory, "App.xaml"));

        var files = new List<(string Xaml, string ViewModel)>
        {
            (Path.Combine(appDirectory, "MainWindow.xaml"), "MainViewModel")
        };

        foreach (var (view, viewModel) in viewToViewModel)
        {
            var path = Path.Combine(appDirectory, "Views", view + ".xaml");
            if (File.Exists(path))
            {
                files.Add((path, viewModel));
            }
        }

        Assert.That(files, Has.Count.GreaterThan(10), "Не удалось собрать список XAML-файлов приложения.");

        var violations = new List<string>();
        foreach (var (xaml, viewModel) in files)
        {
            var properties = ReadPropertyAccessors(Path.Combine(appDirectory, "ViewModels", viewModel + ".cs"));
            var text = File.ReadAllText(xaml);

            foreach (var binding in ReadTwoWayBindings(text))
            {
                if (!properties.TryGetValue(binding.Property, out var writable) || writable)
                {
                    continue; // свойство другого типа (элемент списка) либо доступно для записи
                }

                violations.Add(
                    $"{Path.GetFileName(xaml)}:{binding.Line}: {binding.Element}.{binding.Target} → " +
                    $"{viewModel}.{binding.Property} только для чтения (нужно Mode=OneWay)");
            }
        }

        Assert.That(violations, Is.Empty,
            "Двусторонние привязки к свойствам без сеттера вызывают ошибку при запуске:\n" +
            string.Join("\n", violations));
    }

    private static string? FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        for (var depth = 0; depth < 12 && directory is not null; depth++)
        {
            if (File.Exists(Path.Combine(directory.FullName, "NexusFirmware.sln")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        return null;
    }

    private static Dictionary<string, string> ReadViewToViewModelMap(string appXamlPath)
    {
        var map = new Dictionary<string, string>(StringComparer.Ordinal);
        if (!File.Exists(appXamlPath))
        {
            return map;
        }

        var text = File.ReadAllText(appXamlPath);
        foreach (Match match in Regex.Matches(text, @"DataType=""\{x:Type\s+vm:(\w+)\}"">\s*<views:(\w+)", RegexOptions.Singleline))
        {
            map[match.Groups[2].Value] = match.Groups[1].Value;
        }

        return map;
    }

    /// <summary>Имя свойства → доступно ли оно для записи снаружи (публичный set).</summary>
    private static Dictionary<string, bool> ReadPropertyAccessors(string viewModelPath)
    {
        var result = new Dictionary<string, bool>(StringComparer.Ordinal);
        if (!File.Exists(viewModelPath))
        {
            return result;
        }

        var source = File.ReadAllText(viewModelPath);
        foreach (Match match in Regex.Matches(source, @"public\s+[\w<>\[\],\.\?\s]+?\s+(\w+)\s*(\{|=>)"))
        {
            var name = match.Groups[1].Value;
            var start = match.Index + match.Length;
            var length = Math.Min(420, source.Length - start);
            var block = source.Substring(start, length).Split("\n\n")[0];
            var writable = Regex.IsMatch(block, @"(?<!private\s)(?<!protected\s)(?<!internal\s)\bset\b");
            result[name] = result.TryGetValue(name, out var existing) ? existing || writable : writable;
        }

        return result;
    }

    private static IEnumerable<(int Line, string Element, string Target, string Property)> ReadTwoWayBindings(string xaml)
    {
        foreach (Match element in Regex.Matches(xaml, @"<([A-Za-z][\w\.]*)\b([^>]*?)/?>", RegexOptions.Singleline))
        {
            var tag = element.Groups[1].Value;
            var shortTag = tag.Contains('.') ? tag[(tag.LastIndexOf('.') + 1)..] : tag;
            if (!TwoWayByDefault.TryGetValue(shortTag, out var targets))
            {
                continue;
            }

            foreach (Match attribute in Regex.Matches(element.Groups[2].Value, @"([\w\.]+)=""([^""]*)"""))
            {
                var name = attribute.Groups[1].Value;
                var propertyName = name.Contains('.') ? name[(name.LastIndexOf('.') + 1)..] : name;
                if (!targets.Contains(propertyName, StringComparer.Ordinal))
                {
                    continue;
                }

                var binding = Regex.Match(attribute.Groups[2].Value, @"\{Binding\s+([^}]*)\}");
                if (!binding.Success)
                {
                    continue;
                }

                var body = binding.Groups[1].Value;
                if (body.Contains("Source=", StringComparison.OrdinalIgnoreCase) ||
                    body.Contains("ElementName=", StringComparison.OrdinalIgnoreCase) ||
                    body.Contains("RelativeSource=", StringComparison.OrdinalIgnoreCase))
                {
                    continue; // привязка к другому элементу, а не к ViewModel
                }

                var mode = Regex.Match(body, @"Mode=(\w+)");
                if (mode.Success &&
                    (mode.Groups[1].Value.Equals("OneWay", StringComparison.OrdinalIgnoreCase) ||
                     mode.Groups[1].Value.Equals("OneTime", StringComparison.OrdinalIgnoreCase)))
                {
                    continue;
                }

                var path = body.Replace("Path=", string.Empty, StringComparison.Ordinal).Split(',')[0].Trim();
                var property = path.Split('.')[0];
                if (property.Length == 0)
                {
                    continue;
                }

                var line = xaml.Take(element.Index).Count(c => c == '\n') + 1;
                yield return (line, shortTag, propertyName, property);
            }
        }
    }
}
