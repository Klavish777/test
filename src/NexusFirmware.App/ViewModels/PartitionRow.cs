namespace NexusFirmware.App.ViewModels;

public sealed class PartitionRow
{
    public required string Name { get; init; }
    public string Size { get; init; } = "недоступно";
    public string Source { get; init; } = "";
    public string? Detail { get; init; }
}
