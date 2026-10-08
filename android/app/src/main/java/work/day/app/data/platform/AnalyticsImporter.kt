package work.day.app.data.platform

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import work.day.app.domain.model.DailyMetrics
import work.day.app.domain.model.Platform

/**
 * Импорт цифр руками пользователя: CSV из YouTube Studio / TikTok Analytics или вставленные строки.
 * Парсер терпим к разделителям «;» и «,» и к дате в трёх видах.
 *
 * Колонки: date, platform, views, subscribers, retention_pct, likes, comments, shares
 */
object AnalyticsImporter {

    class ImportError(message: String) : Exception(message)

    private val iso = DateTimeFormatter.ISO_LOCAL_DATE
    private val dmy = DateTimeFormatter.ofPattern("dd.MM.yyyy")
    private val dmySlash = DateTimeFormatter.ofPattern("dd/MM/yyyy")

    fun parse(text: String): Result<List<DailyMetrics>> = runCatching {
        val lines = text.lines().map { it.trim() }.filter { it.isNotBlank() }
        if (lines.isEmpty()) throw ImportError("Пустой ввод")
        val headerCells = splitLine(lines.first()).map { it.lowercase().trim() }
        val hasHeader = headerCells.any { it.contains("date") || it.contains("дата") }
        val rows = if (hasHeader) lines.drop(1) else lines

        fun column(names: List<String>): Int =
            headerCells.indexOfFirst { cell -> names.any { cell.contains(it) } }

        val columns = mapOf(
            "date" to column(listOf("date", "дата")),
            "platform" to column(listOf("platform", "площадка")),
            "views" to column(listOf("view", "просмотр")),
            "subs" to column(listOf("subs", "подписч")),
            "retention" to column(listOf("retention", "удержан")),
            "likes" to column(listOf("like", "лайк")),
            "comments" to column(listOf("comment", "коммент")),
            "shares" to column(listOf("share", "репост")),
        )

        rows.mapIndexed { position, line ->
            val cells = splitLine(line)
            fun cell(key: String, fallback: Int): String {
                val i = columns[key] ?: -1
                return cells.getOrNull(if (i >= 0) i else fallback)?.trim().orEmpty()
            }
            DailyMetrics(
                date = parseDate(cell("date", 0))
                    ?: throw ImportError("Строка ${position + 1}: не понял дату «${cell("date", 0)}»"),
                platform = parsePlatform(cell("platform", 1)),
                views = num(cell("views", 2)),
                subscribers = num(cell("subs", 3)),
                retentionPct = num(cell("retention", 4)).toDouble(),
                likes = num(cell("likes", 5)),
                comments = num(cell("comments", 6)),
                shares = num(cell("shares", 7)),
            )
        }.also { if (it.isEmpty()) throw ImportError("Ни одной строки не разобрал") }
    }

    private fun splitLine(line: String): List<String> =
        if (line.contains(';')) line.split(';') else line.split(',')

    private fun num(value: String): Long =
        value.filter { it.isDigit() || it == '.' || it == ',' }
            .replace(",", ".")
            .toDoubleOrNull()?.toLong() ?: 0L

    private fun parseDate(value: String): String? {
        val v = value.trim()
        runCatching { return LocalDate.parse(v, iso).format(iso) }
        runCatching { return LocalDate.parse(v, dmy).format(iso) }
        runCatching { return LocalDate.parse(v, dmySlash).format(iso) }
        return null
    }

    private fun parsePlatform(value: String): Platform = when {
        value.contains("tik", ignoreCase = true) -> Platform.TIKTOK
        else -> Platform.YOUTUBE
    }
}
