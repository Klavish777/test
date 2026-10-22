using NexusFirmware.Core.Jobs;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Plugins;
using NexusFirmware.Core.Reporting;
using NexusFirmware.Core.Safety;
using NexusFirmware.Plugins;
using NexusFirmware.Plugins.BuiltIn;

namespace NexusFirmware.UnitTests;

[TestFixture]
public sealed class PluginTrustTests
{
    [Test]
    public void AcceptsTrustedPluginWithMatchingHash()
    {
        using var temp = new TempDirectory();
        var assembly = Path.Combine(temp.Path, "plugin.dll");
        File.WriteAllText(assembly, "fake assembly bytes");
        var hash = Hashing.Sha256FileAsync(assembly).GetAwaiter().GetResult();

        var manifest = new PluginManifest
        {
            Id = "test.plugin",
            Name = "Test",
            Version = "1.0.0",
            Publisher = "Acme",
            AssemblyFile = "plugin.dll",
            EntryType = "Test.Plugin",
            Sha256 = hash
        };

        var policy = new PluginTrustPolicy(new[] { "Acme" }, allowLoading: true);
        var result = policy.Validate(manifest, assembly);

        Assert.That(result.Decision, Is.EqualTo(PluginTrustDecision.Trusted));
        Assert.That(result.IsTrusted, Is.True);
    }

    [Test]
    public void RejectsHashMismatch()
    {
        using var temp = new TempDirectory();
        var assembly = Path.Combine(temp.Path, "plugin.dll");
        File.WriteAllText(assembly, "bytes");

        var manifest = new PluginManifest
        {
            Id = "test.plugin",
            Name = "Test",
            Version = "1.0.0",
            Publisher = "Acme",
            Sha256 = new string('0', 64)
        };

        var result = new PluginTrustPolicy(new[] { "Acme" }, true).Validate(manifest, assembly);
        Assert.That(result.Decision, Is.EqualTo(PluginTrustDecision.HashMismatch));
    }

    [Test]
    public void RejectsUnsignePublisherAndDisabledLoading()
    {
        using var temp = new TempDirectory();
        var assembly = Path.Combine(temp.Path, "plugin.dll");
        File.WriteAllText(assembly, "bytes");
        var hash = Hashing.Sha256FileAsync(assembly).GetAwaiter().GetResult();

        var unsigned = new PluginManifest { Id = "a", Name = "a", Version = "1.0", Sha256 = hash };
        Assert.That(new PluginTrustPolicy(Array.Empty<string>(), true).Validate(unsigned, assembly).Decision,
            Is.EqualTo(PluginTrustDecision.Unsigned));

        var trusted = new PluginManifest { Id = "b", Name = "b", Version = "1.0", Publisher = "Acme", Sha256 = hash };
        Assert.That(new PluginTrustPolicy(new[] { "Acme" }, false).Validate(trusted, assembly).Decision,
            Is.EqualTo(PluginTrustDecision.NotAllowedByPolicy));
    }

    [Test]
    public void RejectsInvalidManifest()
    {
        using var temp = new TempDirectory();
        var assembly = Path.Combine(temp.Path, "plugin.dll");
        File.WriteAllText(assembly, "bytes");

        var manifest = new PluginManifest { Id = "", Name = "", Version = "x" };
        var result = new PluginTrustPolicy(Array.Empty<string>(), true).Validate(manifest, assembly);
        Assert.That(result.Decision, Is.EqualTo(PluginTrustDecision.InvalidManifest));
    }

    [Test]
    public void BuiltInPluginDescribesOperations()
    {
        var plugin = new GenericAndroidPlugin();
        var device = TestData.Device();

        var checks = plugin.CheckCompatibility(device);
        var operations = plugin.DescribeOperations(device);

        Assert.That(checks, Is.Not.Empty);
        Assert.That(operations, Does.Contain("Список разделов"));
        Assert.That(plugin.Manifest.Id, Is.EqualTo("nexus.builtin.generic-android"));
    }
}

[TestFixture]
public sealed class JobQueueTests
{
    [Test]
    public async Task RunsStepsSequentiallyAndBuildsReport()
    {
        var log = new FakeLogBus();
        await using var queue = new JobQueue(log);
        var executed = new List<string>();

        var request = new JobRequest
        {
            Title = "Тестовое задание",
            DeviceSummary = "test",
            FirmwareSummary = "test",
            Steps = new[]
            {
                new JobStepDefinition
                {
                    Info = new OperationStep { Title = "Шаг 1" },
                    Execute = (ctx, _) => { executed.Add("1"); ctx.Log("шаг 1"); return Task.CompletedTask; }
                },
                new JobStepDefinition
                {
                    Info = new OperationStep { Title = "Шаг 2" },
                    Execute = (ctx, _) => { executed.Add("2"); ctx.Report(50, "половина"); return Task.CompletedTask; }
                }
            }
        };

        var run = queue.Enqueue(request);
        var deadline = DateTimeOffset.UtcNow.AddSeconds(10);
        while (!run.IsTerminal && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(20);
        }

        Assert.That(run.State, Is.EqualTo(OperationState.Succeeded));
        Assert.That(executed, Is.EqualTo(new[] { "1", "2" }));
        Assert.That(run.Percent, Is.EqualTo(100));

        var report = queue.BuildReport(run);
        Assert.That(report.Entries, Is.Not.Empty);
        Assert.That(ReportWriter.ToMarkdown(report), Does.Contain("Тестовое задание"));
    }

    [Test]
    public async Task MarksFailedJob()
    {
        var log = new FakeLogBus();
        await using var queue = new JobQueue(log);

        var run = queue.Enqueue(new JobRequest
        {
            Title = "Ошибка",
            Steps = new[]
            {
                new JobStepDefinition
                {
                    Info = new OperationStep { Title = "Падение" },
                    Execute = (_, _) => throw new InvalidOperationException("сбой устройства")
                }
            }
        });

        var deadline = DateTimeOffset.UtcNow.AddSeconds(10);
        while (!run.IsTerminal && DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(20);
        }

        Assert.That(run.State, Is.EqualTo(OperationState.Failed));
        Assert.That(run.FailedReason, Does.Contain("сбой"));
    }
}

[TestFixture]
public sealed class ReportingTests
{
    [Test]
    public void MarkdownContainsKeySections()
    {
        var report = new OperationReport
        {
            Title = "Прошивка",
            DeviceSummary = "Samsung SM-G973F",
            FirmwareSummary = "AP_test",
            State = OperationState.Succeeded,
            StartedAt = DateTimeOffset.Now.AddMinutes(-2),
            FinishedAt = DateTimeOffset.Now,
            IsDryRun = true,
            Entries = new[] { new ReportEntry(DateTimeOffset.Now, "Information", "строка журнала") },
            Artifacts = new[] { "C:\\reports\\a.md" }
        };

        var markdown = ReportWriter.ToMarkdown(report);
        Assert.That(markdown, Does.Contain("# Прошивка"));
        Assert.That(markdown, Does.Contain("Dry Run"));
        Assert.That(markdown, Does.Contain("строка журнала"));
        Assert.That(markdown, Does.Contain("Успешно"));

        var json = ReportWriter.ToJson(report);
        Assert.That(json, Does.Contain("\"Title\": \"Прошивка\""));
    }
}
