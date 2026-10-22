using NexusFirmware.Core.Models;
using NexusFirmware.Infrastructure.Data;
using NexusFirmware.UnitTests;
using NUnit.Framework;

namespace NexusFirmware.IntegrationTests;

[TestFixture]
public sealed class DatabaseTests
{
    private TempDirectory _temp = null!;
    private NexusDatabase _database = null!;
    private FirmwareRepository _firmware = null!;
    private DiagnosticsRepository _diagnostics = null!;
    private TrustRepository _trust = null!;

    [SetUp]
    public void Setup()
    {
        _temp = new TempDirectory();
        _database = new NexusDatabase(Path.Combine(_temp.Path, "nexus.db"));
        _database.Initialize();
        _firmware = new FirmwareRepository(_database);
        _diagnostics = new DiagnosticsRepository(_database);
        _trust = new TrustRepository(_database);
    }

    [TearDown]
    public void TearDown() => _temp.Dispose();

    [Test]
    public void FirmwareRoundtripAndNotes()
    {
        var package = TestData.Package(path: _temp.File("fw.zip"));
        _firmware.Upsert(package);

        var loaded = _firmware.GetById(package.Id);
        Assert.That(loaded, Is.Not.Null);
        Assert.That(loaded!.DisplayName, Is.EqualTo(package.DisplayName));
        Assert.That(loaded.Sha256, Is.EqualTo(package.Sha256));
        Assert.That(loaded.Integrity, Is.EqualTo(IntegrityState.Verified));

        _firmware.AddNote(package.Id, "проверено на стенде");
        var notes = _firmware.GetNotes(package.Id);
        Assert.That(notes, Has.Count.EqualTo(1));
        Assert.That(notes[0].Text, Is.EqualTo("проверено на стенде"));

        _firmware.AddImportHistory(package.Id, package.FilePath!, package.Sha256, "import");
        Assert.That(_firmware.GetImportHistory(package.Id), Has.Count.EqualTo(1));

        Assert.That(_firmware.FindBySha256(package.Sha256!), Has.Count.EqualTo(1));

        _firmware.Delete(package.Id);
        Assert.That(_firmware.GetById(package.Id), Is.Null);
    }

    [Test]
    public void ReportsAndJournalArePersisted()
    {
        var report = new OperationReport
        {
            Title = "Dry Run",
            DeviceSummary = "dev",
            FirmwareSummary = "fw",
            State = OperationState.Succeeded,
            StartedAt = DateTimeOffset.Now,
            FinishedAt = DateTimeOffset.Now,
            IsDryRun = true
        };

        _diagnostics.SaveReport(report, _temp.File("report.md"));
        var reports = _diagnostics.GetReports();
        Assert.That(reports, Has.Count.EqualTo(1));
        Assert.That(reports[0].IsDryRun, Is.True);
        Assert.That(reports[0].ModeText, Is.EqualTo("Dry Run"));

        _diagnostics.SaveDeviceSnapshot(TestData.Device());
        _diagnostics.WriteJournal(new LogEntry(DateTimeOffset.Now, LogLevel.Information, "test", "message"));
        _diagnostics.ClearJournal();
    }

    [Test]
    public void TrustedPublishersRoundtrip()
    {
        Assert.That(_trust.GetTrustedPublishers(), Is.Empty);
        _trust.Trust("Acme");
        Assert.That(_trust.GetTrustedPublishers(), Does.Contain("Acme"));
        _trust.Revoke("Acme");
        Assert.That(_trust.GetTrustedPublishers(), Is.Empty);
    }
}
