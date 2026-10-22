using System.Text;
using NexusFirmware.Core.Safety;
using NUnit.Framework;

namespace NexusFirmware.UnitTests;

[TestFixture]
public sealed class PathSafetyTests
{
    [TestCase("boot.img", true)]
    [TestCase("images/boot.img", true)]
    [TestCase("a/b/c/file.bin", true)]
    [TestCase("../evil.txt", false)]
    [TestCase("images/../../evil.txt", false)]
    [TestCase("/etc/passwd", false)]
    [TestCase("C:/Windows/system32/x.dll", false)]
    [TestCase("file.bin:stream", false)]
    [TestCase("CON", false)]
    [TestCase("NUL.txt", false)]
    [TestCase("dir/sub/./file.txt", true)]
    [TestCase("", false)]
    public void NormalizesArchiveEntryNames(string entry, bool expected)
    {
        var result = PathSafety.TryNormalizeArchiveEntry(entry, out var normalized, out var reason);

        Assert.That(result, Is.EqualTo(expected), reason);
        if (result)
        {
            Assert.That(normalized, Does.Not.Contain(".."));
        }
    }

    [Test]
    public void CombineInside_RejectsEscape()
    {
        using var temp = new TempDirectory();

        Assert.That(PathSafety.TryCombineInside(temp.Path, "../outside.txt", out _), Is.False);
        Assert.That(PathSafety.TryCombineInside(temp.Path, "sub/file.txt", out var full), Is.True);
        Assert.That(full, Does.StartWith(Path.GetFullPath(temp.Path)));
    }

    [Test]
    public void WorkDirectory_IsCreatedAndRemovable()
    {
        var dir = PathSafety.CreateWorkDirectory("test:name??");
        Assert.That(Directory.Exists(dir), Is.True);

        PathSafety.TryDeleteDirectory(dir);
        Assert.That(Directory.Exists(dir), Is.False);
    }
}

[TestFixture]
public sealed class HashingTests
{
    [Test]
    public async Task Sha256_MatchesKnownValue()
    {
        using var temp = new TempDirectory();
        var path = temp.File("hello.txt");
        await File.WriteAllBytesAsync(path, "hello"u8.ToArray());

        var hash = await Hashing.Sha256FileAsync(path);
        Assert.That(hash, Is.EqualTo("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"));
    }

    [Test]
    public async Task Verify_ReturnsFalseForWrongHash()
    {
        using var temp = new TempDirectory();
        var path = temp.File("a.bin");
        await File.WriteAllBytesAsync(path, [1, 2, 3]);

        Assert.That(await Hashing.VerifySha256Async(path, "deadbeef"), Is.False);
        var actual = await Hashing.Sha256FileAsync(path);
        Assert.That(await Hashing.VerifySha256Async(path, actual.ToUpperInvariant()), Is.True);
    }
}

[TestFixture]
public sealed class RedactorTests
{
    [Test]
    public void MasksShortAndLongIdentifiers()
    {
        Assert.That(Redactor.MaskIdentifier(null), Is.EqualTo("—"));
        Assert.That(Redactor.MaskIdentifier("1234"), Is.EqualTo("••••"));
        Assert.That(Redactor.MaskIdentifier("R58M12345"), Does.Contain("•"));
        Assert.That(Redactor.MaskIdentifier("R58M12345"), Does.StartWith("R58"));
        Assert.That(Redactor.MaskIdentifier("R58M12345"), Does.EndWith("345"));
    }

    [Test]
    public void MasksImeiInText()
    {
        var text = "IMEI устройства: 356938035643809 (проверено)";
        var masked = Redactor.MaskText(text);
        Assert.That(masked, Does.Not.Contain("356938035643809"));
        Assert.That(masked, Does.Contain("••••••••••"));
    }

    [Test]
    public void MasksSensitiveKeyValueLines()
    {
        var masked = Redactor.MaskKeyValueLine("[ro.serialno]: [ABC123XYZ]");
        Assert.That(masked, Does.Contain("скрыто"));
        Assert.That(masked, Does.Not.Contain("ABC123XYZ"));
    }
}

[TestFixture]
public sealed class InputValidatorTests
{
    [TestCase("R58M12345", true)]
    [TestCase("0123456789ABCDEF", true)]
    [TestCase("bad serial", false)]
    [TestCase("; rm -rf /", false)]
    [TestCase("", false)]
    public void ValidatesSerial(string serial, bool expected) =>
        Assert.That(InputValidator.IsValidSerial(serial), Is.EqualTo(expected));

    [TestCase("boot", true)]
    [TestCase("vbmeta_system", true)]
    [TestCase("boot;reboot", false)]
    [TestCase("BOOT", false)]
    public void ValidatesPartition(string name, bool expected) =>
        Assert.That(InputValidator.IsValidPartitionName(name), Is.EqualTo(expected));

    [Test]
    public void SanitizesFileName()
    {
        var name = InputValidator.SanitizeFileName("../../evil?.zip");
        Assert.That(name, Does.Not.Contain(".."));
        Assert.That(name, Does.Not.Contain("?"));
        Assert.That(name, Does.EndWith(".zip"));
    }
}
