package work.day.app.domain.model

import kotlinx.serialization.Serializable

/**
 * Модель «Генерации»: ролик собирается не «из воздуха», а из того, что уже работает
 * в нише по статистике YouTube. Порядок строго конвейерный:
 *
 *   тема + длительность → скелет по битам → правки агента-монтажёра → проверка
 *   на политику/авторские права → пакет к публикации + ffmpeg-скрипт.
 *
 * Важно: приложение **не** выкладывает само и не скачивает чужие ролики. Оно считает
 * структуру, тексты, тайминги и даёт готовый рецепт сборки, который прогоняется у тебя
 * на компьютере (ffmpeg), а публикация остаётся ручным шагом — права на запись в канал
 * приложение не запрашивает никогда.
 */

/** Формат ролика. Границы — из самого YouTube: Shorts — не длиннее 60 секунд. */
@Serializable
enum class VideoFormat(
    val label: String,
    val minSec: Int,
    val maxSec: Int,
    val vertical: Boolean,
    val note: String,
) {
    SHORTS("Shorts", 20, 58, true, "до 60 секунд, вертикаль 9:16; удержание решает всё"),
    FEED("В лентах", 61, 180, false, "1–3 минуты: нормальный ритм, но без клипового монтажа"),
    MID("Середина", 181, 480, false, "3–8 минут: главы, доказательная часть, средний CPM выше"),
    LONG("Длинное", 481, 900, false, "8–15 минут: удержание по главам, больше подборок в описание"),
    ;

    companion object {
        fun of(name: String): VideoFormat = entries.firstOrNull { it.name == name } ?: SHORTS
    }
}

/** Роль бита в ролике. Бит = минимальная единица монтажа: один кусок времени, один смысл. */
@Serializable
enum class BeatRole(val label: String, val screenHint: String) {
    HOOK("хук", "кадр с самым сильным движением в первые полсекунды"),
    SETUP("разогрев", "обещание + ставка: что человек получит к концу"),
    PAYLOAD("мясо", "смена плана каждые 2–3 секунды, текст поверх"),
    PROOF("доказательство", "цифра, скрин, замер — кадр, который нельзя оспорить"),
    TWIST("поворот", "то, что ломает ожидание из начала"),
    CTA("призыв", "одна конкретная причина вернуться, без «подпишись»"),
    LOOP("петля", "последний кадр цепляет первый: пересматриваемость"),
    ;
}

/** Тип материала, из которого собирается ролик. */
@Serializable
enum class AssetKind(val label: String) {
    OWN_CLIP("свои съёмки"),
    OWN_BROLL("свои перебивки"),
    GENERATED_VIDEO("сгенерированное видео"),
    GENERATED_TTS("синтезированный голос"),
    GENERATED_IMAGE("сгенерированная картинка"),
    TEXT_OVERLAY("текст поверх"),
    MUSIC("музыка"),
    SFX("звуковой эффект"),
    CAPTIONS("субтитры"),
    ;
}

/**
 * Лицензия материала. Именно здесь решается, монетизируется ролик или прилетает
 * страйк: чужой трек и чужие клипы — самая частая причина обнуления.
 */
@Serializable
enum class AssetLicense(val label: String, val monetizable: Boolean, val blocking: Boolean) {
    OWN("твоё", true, false),
    CC0("CC0 / public domain", true, false),
    YT_AUDIO_LIBRARY("YouTube Audio Library", true, false),
    GENERATED("сгенерировано тобой", true, false),
    /** Требует разрешения правообладателя. Пока разрешения нет — блокирует публикацию. */
    NEEDS_PERMISSION("нужно разрешение", false, true),
    /** Чужое видео целиком: переиспользованный контент, монетизации не будет. */
    REPOSTED("чужой репост", false, true),
    ;
}

/** Одна оценка по конкретной оси. Все оси — 0..100, чтобы складываться в средний балл. */
@Serializable
data class ViralScore(
    val hook: Int = 0,
    val pacing: Int = 0,
    val payoff: Int = 0,
    val retention: Int = 0,
    val monetization: Int = 0,
) {
    val total: Int get() = (hook + pacing + payoff + retention + monetization) / 5

    fun weakest(): Pair<String, Int> {
        val axes = listOf(
            "хук" to hook, "ритм" to pacing, "раскрытие" to payoff,
            "удержание" to retention, "монетизация" to monetization,
        )
        return axes.minByOrNull { it.second } ?: ("хук" to 0)
    }

    companion object {
        fun of(hook: Int, pacing: Int, payoff: Int, retention: Int, monetization: Int): ViralScore =
            ViralScore(clamp(hook), clamp(pacing), clamp(payoff), clamp(retention), clamp(monetization))

        private fun clamp(v: Int): Int = v.coerceIn(0, 100)
    }
}

/** Тема-кандидат: то, что приложение подсовывает нажатием «Сгенерировать». */
@Serializable
data class TopicCandidate(
    val title: String,
    val niche: String,
    val hook: String,
    val why: String,
    val format: VideoFormat = VideoFormat.SHORTS,
    val durationSec: Int = 34,
    /** Просмотры на час с момента публикации у победителей нишы — главный сигнал. */
    val velocityPerHour: Double = 0.0,
    /** Насколько тема затёрта: чем больше, тем выше планка по подаче. */
    val competition: Int = 0,
    val demand: Int = 0,
    val score: ViralScore = ViralScore(),
    /** Что именно в статистике YouTube заставило так решить (заголовки + цифры). */
    val evidence: List<String> = emptyList(),
    /** Демо-приор вместо живой статистики — чтобы не выдавать выдуманное за факт. */
    val fromDemo: Boolean = true,
) {
    val durationLabel: String get() = "%d:%02d".format(durationSec / 60, durationSec % 60)
}

/** Бит будущего ролика. Тайминги в секундах, целые: их потом читает ffmpeg. */
@Serializable
data class Beat(
    val index: Int = 0,
    val startSec: Int = 0,
    val endSec: Int = 0,
    val role: BeatRole = BeatRole.PAYLOAD,
    val screen: String = "",
    val voice: String = "",
    val shot: String = "",
    val overlay: String = "",
    val sourceHint: String = "",
) {
    val lengthSec: Int get() = (endSec - startSec).coerceAtLeast(0)
}

/** Правка агента-монтажёра: что изменено, зачем и на сколько баллов это поднимает. */
@Serializable
data class Edit(
    val beatIndex: Int = -1,
    val action: String = "",
    val before: String = "",
    val after: String = "",
    val reason: String = "",
    val delta: Int = 0,
)

/** Материал, который нужно подложить под бит. */
@Serializable
data class AssetSpec(
    val id: String = "",
    val kind: AssetKind = AssetKind.OWN_BROLL,
    val license: AssetLicense = AssetLicense.OWN,
    /** Что искать/генерировать: конкретный запрос, а не «красивая картинка». */
    val query: String = "",
    val note: String = "",
)

@Serializable
data class ComplianceCheck(
    val rule: String = "",
    val ok: Boolean = true,
    val blocking: Boolean = true,
    /** Что сделать, если не ок. Обязательно конкретно. */
    val fix: String = "",
)

@Serializable
data class ComplianceReport(val checks: List<ComplianceCheck> = emptyList()) {
    val allowedToPublish: Boolean get() = checks.none { it.blocking && !it.ok }
    val blockers: List<ComplianceCheck> get() = checks.filter { it.blocking && !it.ok }
    val warnings: List<ComplianceCheck> get() = checks.filter { !it.blocking && !it.ok }
}

/** Рецепт сборки: то, что реально превращает биты в файл. */
@Serializable
data class RenderRecipe(
    val manifest: String = "",
    val script: String = "",
    val srt: String = "",
    val notes: String = "",
)

/** Готовый пакет: ролик + упаковка. Публикация — руками человека. */
@Serializable
data class GenerationPlan(
    val id: String = "",
    val createdAt: Long = 0L,
    val topic: TopicCandidate = TopicCandidate(title = "", niche = "", hook = "", why = ""),
    val beats: List<Beat> = emptyList(),
    val edits: List<Edit> = emptyList(),
    val assets: List<AssetSpec> = emptyList(),
    val scoreBefore: ViralScore = ViralScore(),
    val scoreAfter: ViralScore = ViralScore(),
    val compliance: ComplianceReport = ComplianceReport(),
    val recipe: RenderRecipe = RenderRecipe(),
    val title: String = "",
    val description: String = "",
    val tags: List<String> = emptyList(),
    val pinnedComment: String = "",
    val thumbnailBrief: String = "",
    val modelSource: String = "офлайн-движок",
) {
    val totalSec: Int get() = beats.sumOf { it.lengthSec }
    val isReady: Boolean get() = beats.isNotEmpty() && compliance.allowedToPublish
}

/** Состояние мастерской — одна запись на диске, переживает перезапуск. */
@Serializable
data class GenerationState(
    val topics: List<TopicCandidate> = emptyList(),
    val plan: GenerationPlan? = null,
    val niche: String = "",
    val format: String = "SHORTS",
    val durationSec: Int = 0,
    /** Кэш живой статистики: search.list стоит 100 единиц квоты, жечь её на каждый тап нельзя. */
    val research: List<ResearchItem> = emptyList(),
    val researchAt: Long = 0L,
    val history: List<String> = emptyList(),
) {
    companion object {
        const val RESEARCH_TTL_MS = 6 * 60 * 60 * 1000L
    }

    val researchFresh: Boolean
        get() = research.isNotEmpty() && System.currentTimeMillis() - researchAt < RESEARCH_TTL_MS
}

/** Один ролик из выдачи YouTube — то, на чём считается «что залетает». */
@Serializable
data class ResearchItem(
    val videoId: String = "",
    val title: String = "",
    val channelTitle: String = "",
    val publishedAt: String = "",
    val views: Long = 0L,
    val likes: Long = 0L,
    val comments: Long = 0L,
    val durationSec: Int = 0,
    /** contentDetails.licensedContent: у чужого лицензионного контента страйк почти гарантирован. */
    val licensed: Boolean = false,
) {
    /** Просмотры в час с момента публикации — честнее абсолютных просмотров: они накапаны за год. */
    val velocityPerHour: Double
        get() {
            val hours = hoursSincePublish
            return if (hours > 0) views / hours else views.toDouble() / (24 * 30)
        }

    private val hoursSincePublish: Double
        get() {
            val epoch = parseIsoEpoch(publishedAt) ?: return 24.0 * 30
            return ((System.currentTimeMillis() - epoch) / 3_600_000.0).coerceAtLeast(1.0)
        }

    val likeRatio: Double get() = if (views > 0) likes.toDouble() / views else 0.0

    companion object {
        /** ISO-8601 от YouTube («2026-10-01T08:00:00Z») в миллисекунды; без java.time на minSdk 26. */
        fun parseIsoEpoch(raw: String): Long? {
            if (raw.length < 19) return null
            // «2026-10-01T08:00:00Z»: дату и время берём по позициям — между ними
            // обязательный «T», а суффикс зоны («Z»/«+03:00») нам не нужен: смещение
            // YouTube отдаёт уже учтённым в самих часах.
            val date = raw.substring(0, 10).filter { it.isDigit() }
            val time = raw.substring(11, 19).filter { it.isDigit() }
            if (date.length != 8 || time.length != 6) return null
            val y = date.substring(0, 4).toInt()
            val mo = date.substring(4, 6).toInt()
            val d = date.substring(6, 8).toInt()
            if (mo !in 1..12 || d !in 1..31) return null
            val h = time.substring(0, 2).toInt()
            val mi = time.substring(2, 4).toInt()
            val sec = time.substring(4, 6).toInt()
            return epochDays(y, mo, d) * 86_400_000L + h * 3_600_000L + mi * 60_000L + sec * 1_000L
        }

        /** Дней от 1970-01-01 по григорианскому календарю (алгоритм Howard Hinnant). */
        fun epochDays(year: Int, month: Int, day: Int): Long {
            val y = if (month <= 2) year - 1 else year
            val era = (if (y >= 0) y else y - 399) / 400
            val yoe = y - era * 400
            val doy = (153 * (month + if (month > 2) -3 else 9) + 2) / 5 + day - 1
            val doe = yoe * 365 + yoe / 4 - yoe / 100 + doy
            return era.toLong() * 146_097 + doe - 719_468
        }

        /** «PT4M12S» / «PT37S» / «PT1H2M3S» в секунды. */
        fun parseDuration(text: String): Int {
            if (!text.startsWith("PT")) return 0
            val body = text.drop(2).replace(",", ".")
            var total = 0
            val number = StringBuilder()
            for (c in body) {
                if (c.isDigit()) {
                    number.append(c)
                    continue
                }
                val value = number.toString().toIntOrNull() ?: 0
                number.setLength(0)
                total += when (c) {
                    'H' -> value * 3600
                    'M' -> value * 60
                    'S' -> value
                    else -> 0
                }
            }
            return total
        }
    }
}
