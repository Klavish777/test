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

    /// <summary>Сохраняет открытый ключ издателя (PEM) для проверки подписи манифестов.</summary>
    public void SetPublisherKey(string publisher, string publicKeyPem)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO publisher_key (publisher, public_key_pem, added_at) VALUES ($publisher, $key, $at)
            ON CONFLICT(publisher) DO UPDATE SET public_key_pem = excluded.public_key_pem;
            """;
        command.Parameters.AddWithValue("$publisher", publisher);
        command.Parameters.AddWithValue("$key", publicKeyPem);
        command.Parameters.AddWithValue("$at", DateTimeOffset.Now.ToString("O", CultureInfo.InvariantCulture));
        command.ExecuteNonQuery();
    }

    /// <summary>Открытый ключ издателя или null, если он не задан.</summary>
    public string? GetPublisherKey(string publisher)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT public_key_pem FROM publisher_key WHERE publisher = $publisher LIMIT 1;";
        command.Parameters.AddWithValue("$publisher", publisher);
        return command.ExecuteScalar() as string;
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
