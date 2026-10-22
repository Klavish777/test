namespace NexusFirmware.Core.Abstractions;

/// <summary>Поиск внешних исполняемых инструментов (adb, fastboot, heimdall и т.п.).</summary>
public interface IToolLocator
{
    string? Find(string toolName);

    Task<bool> ExistsAsync(string toolName, CancellationToken cancellationToken = default);

    IReadOnlyList<string> SearchPaths { get; }
}
