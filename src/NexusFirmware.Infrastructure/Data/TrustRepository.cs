using System.Globalization;

namespace NexusFirmware.Infrastructure.Data;

/// <summary>Список доверенных издателей плагинов, подтверждённых пользователем вручную.</summary>
public sealed class TrustRepository
{
    private readonly NexusDatabase _database;

    public TrustRepository(NexusDatabase database)
    {
        _database = database;
    }

    public IReadOnlyList<string> GetTrustedPublishers()
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT publisher FROM trusted_publisher ORDER BY publisher;";
        using var reader = command.ExecuteReader();
        var list = new List<string>();
        while (reader.Read())
        {
            list.Add(reader.GetString(0));
        }

        return list;
    }

    public void Trust(string publisher, string? note = null)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO trusted_publisher (publisher, added_at, note) VALUES ($publisher, $at, $note)
            ON CONFLICT(publisher) DO NOTHING;
            """;
        command.Parameters.AddWithValue("$publisher", publisher);
        command.Parameters.AddWithValue("$at", DateTimeOffset.Now.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$note", (object?)note ?? DBNull.Value);
        command.ExecuteNonQuery();
    }

    public void Revoke(string publisher)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "DELETE FROM trusted_publisher WHERE publisher = $publisher;";
        command.Parameters.AddWithValue("$publisher", publisher);
        command.ExecuteNonQuery();
    }
}
