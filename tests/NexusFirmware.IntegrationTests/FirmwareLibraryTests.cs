using System.IO.Compression;
using NexusFirmware.Core.Models;
using NexusFirmware.Firmware.Library;
using NexusFirmware.Infrastructure.Data;
using NexusFirmware.UnitTests;

namespace NexusFirmware.IntegrationTests;

[TestFixture]
public sealed class FirmwareLibraryTests
{
    private TempDirectory _temp = null!;
    private FirmwareLibrary _library = null!;
    private string _zipPath = null!;

    [SetUp]
    public void Setup()
    {
        _temp = new TempDirectory();
        var database = new NexusDatabase(Path.Combine(_temp.Path, "nexus.db"));
        database.Initialize();
        _library = new FirmwareLibrary(new FirmwareRepository(database), new FakeLogBus());

        _zipPath = _temp.File("SM-G973F_firmware.zip");
        using var zip = ZipFile.Open(_zipPath, ZipArchiveMode.Create);
        foreach (var name in new[] { "boot.img", "system.img", "vbmeta.img" })
        {
            using var writer = new StreamWriter(zip.CreateEntry(name).Open());
            writer.Write("content of " + name);
        }
    }

    [TearDown]
    public void TearDown() => _temp.Dispose();

    [Test]
    public async Task ImportsPackageAndComputesHash()
    {
        var result = await _library.ImportAsync(_zipPath, new ImportOptions { ComputeHash = true });

        Assert.That(result.IsDuplicate, Is.False);
        Assert.That(result.Package.Sha256, Is.Not.Null.And.Length.EqualTo(64));
        Assert.That(result.Package.Integrity, Is.EqualTo(IntegrityState.Verified));
        Assert.That(result.Package.Format, Is.EqualTo(FirmwareFormat.Zip));
        Assert.That(_library.GetPackages(), Has.Count.EqualTo(1));
    }

    [Test]
    public async Task DetectsDuplicateByHash()
    {
        var first = await _library.ImportAsync(_zipPath);
        var second = await _library.ImportAsync(_zipPath, new ImportOptions { SkipDuplicates = true });

        Assert.That(second.IsDuplicate, Is.True);
        Assert.That(second.Package.Id, Is.EqualTo(first.Package.Id));
        Assert.That(_library.GetPackages(), Has.Count.EqualTo(1));
    }

    [Test]
    public async Task VerifyIntegrityDetectsCorruption()
    {
        var imported = await _library.ImportAsync(_zipPath);

        Assert.That(await _library.VerifyIntegrityAsync(imported.Package.Id), Is.True);

        await File.WriteAllTextAsync(_zipPath, "corrupted");
        Assert.That(await _library.VerifyIntegrityAsync(imported.Package.Id), Is.False);

        var reloaded = _library.GetPackages().Single();
        Assert.That(reloaded.Integrity, Is.EqualTo(IntegrityState.Failed));
    }

    [Test]
    public async Task NotesAreStored()
    {
        var imported = await _library.ImportAsync(_zipPath);
        _library.AddNote(imported.Package.Id, "заметка инженера");

        var notes = _library.GetNotes(imported.Package.Id);
        Assert.That(notes, Has.Count.EqualTo(1));
        Assert.That(notes[0].Text, Is.EqualTo("заметка инженера"));
    }

    [Test]
    public async Task DirectoryImportSkipsUnknownFiles()
    {
        await File.WriteAllTextAsync(_temp.File("readme.md"), "text");
        var results = await _library.ImportDirectoryAsync(_temp.Path);

        Assert.That(results, Has.Count.EqualTo(1));
        Assert.That(results[0].Package.DisplayName, Is.EqualTo("SM-G973F_firmware.zip"));
    }
}
