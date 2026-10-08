package work.day.app.data.repo

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.max
import kotlin.math.sin
import work.day.app.domain.model.DailyMetrics
import work.day.app.domain.model.Platform

/**
 * Демо-данные для графика и отчётов, пока канал не подключён.
 * Детерминированы по дате: при перезапуске картина та же, ничего не «прыгает».
 */
object SampleMetrics {

    private val fmt = DateTimeFormatter.ISO_LOCAL_DATE

    fun series(days: Int, today: LocalDate = LocalDate.now()): List<DailyMetrics> =
        (0 until days).flatMap { i ->
            val date = today.minusDays((days - i).toLong())
            listOf(row(date, i, Platform.YOUTUBE), row(date, i, Platform.TIKTOK))
        }

    private fun row(date: LocalDate, index: Int, platform: Platform): DailyMetrics {
        val seed = (date.toEpochDay() * 2654435761u).toInt()
        val weekend = if (date.dayOfWeek.value >= 6) 1.18 else 1.0
        val wave = 1.0 + 0.14 * sin(index / 3.1)
        val ramp = 1.0 + index / 55.0
        val baseViews = if (platform == Platform.YOUTUBE) 5200 else 13400
        val subs = if (platform == Platform.YOUTUBE) 18_420L else 27_150L

        val views = (baseViews * wave * weekend * ramp).toLong()
        val gained = max(3L, (views / if (platform == Platform.YOUTUBE) 210 else 340) + (seed % 7))

        return DailyMetrics(
            date = date.format(fmt),
            platform = platform,
            subscribers = subs + index * gained,
            views = views,
            retentionPct = round(if (platform == Platform.YOUTUBE) 41.0 + (seed % 9) / 2.0 else 58.0 + (seed % 11) / 2.0),
            likes = views / 34,
            comments = views / 300,
            shares = views / 720,
            newAudiencePct = round(if (platform == Platform.TIKTOK) 71.0 + (seed % 17) / 3.0 else 38.0 + (seed % 13) / 3.0),
            impressions = views * if (platform == Platform.YOUTUBE) 6 else 3,
            ctrPct = round(if (platform == Platform.YOUTUBE) 4.2 + (seed % 21) / 10.0 else 8.5 + (seed % 31) / 10.0),
        )
    }

    private fun round(v: Double): Double = Math.round(v * 10) / 10.0
}
