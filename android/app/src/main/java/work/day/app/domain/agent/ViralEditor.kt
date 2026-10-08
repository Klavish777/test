package work.day.app.domain.agent

import work.day.app.data.llm.LlmClient
import work.day.app.data.llm.LlmSettings
import work.day.app.domain.engine.ViralLab
import work.day.app.domain.model.Beat
import work.day.app.domain.model.BeatRole
import work.day.app.domain.model.TopicCandidate
import work.day.app.domain.model.VideoFormat

/**
 * Агент-монтажёр «Ножницы». Не пятый агент смены — он работает только в «Генерации»,
 * потому что у него один заказчик: конкретный ролик, который нужно собрать и не угробить
 * о правах/монетизации.
 *
 * Две функции:
 * 1) предложить формулировки (темы, хук, озвучку) — тут говорит модель;
 * 2) внести правки в скелет, чтобы вырос балл удержания — тут говорит статистика,
 *    и каждую правку можно проверить: [ViralLab.editPass] меняет ровно те входные
 *    данные, из которых считается оценка.
 */
object ViralEditor {

    const val NAME = "Ножницы"
    const val ROLE = "агент-монтажёр: режет, пока не начнёт держаться"

    /** Что агент не сделает никогда — показывается в UI рядом с результатом. */
    val RULES: List<String> = listOf(
        "не берёт чужие ролики и треки: собирает из твоих материалов и лицензионной музыки",
        "не обещает в заголовке того, чего нет в битах",
        "не вставляет накрутки, покупки просмотров и «взаимные подписки»",
        "не публикует сам: отдаёт пакет и ffmpeg-скрипт, выкладываешь ты",
        "не выдумывает цифры: если статистики YouTube нет, говорит «демо-приоры»",
    )

    private const val OFFLINE_MARK = "ВИДЕОГЕНЕРАЦИЯ"

    /** Формулировки тем от модели. Без ключа возвращает пусто — движок возьмёт свои шаблоны. */
    suspend fun topics(
        settings: LlmSettings,
        llm: LlmClient,
        niche: ViralLab.Niche,
        format: VideoFormat,
        durationSec: Int,
        stats: ViralLab.NicheStats,
        audience: String,
    ): List<String> {
        if (!settings.isUsable) return emptyList()
        val brief = LlmBrief(
            system = SYSTEM,
            user = buildString {
                appendLine("$OFFLINE_MARK · подбор тем")
                appendLine("Ниша: ${niche.name}")
                appendLine("Интент зрителя: ${niche.intent}")
                appendLine("Формат: ${format.label}, ${durationSec} секунд")
                appendLine(
                    "Статистика нишы по YouTube: медиана ${stats.medianDurationSec}с, " +
                        "медиана просмотров ${stats.medianViews}, просм/час ${stats.medianVelocity}, " +
                        "доля лайков ${(stats.medianLikeRatio * 1000).toInt() / 10.0}%, " +
                        "выборка ${stats.sample}" + if (stats.fromDemo) " (демо-приоры, живой статистики нет)" else "",
                )
                appendLine("Работает в заголовках этой нишы: ${stats.bestTitlePatterns.joinToString("; ")}")
                if (audience.isNotBlank()) appendLine("Аудитория канала: $audience")
                appendLine()
                appendLine("Дай 6 вариантов в формате: Заголовок | Хук первых 3 секунд | Почему залетит")
                appendLine("Заголовок до 90 символов, без кликбейта, который ролик не выполнит. Без нумерации и без markdown.")
            },
            temperature = 0.85,
            maxTokens = 700,
        )
        val text = runCatching { llm.complete(brief).text }.getOrNull().orEmpty()
        return text.lines()
            .map { it.trim() }
            .filter { it.contains('|') || it.length > 12 }
            .filterNot { it.startsWith("$OFFLINE_MARK") || it.startsWith("Ниша:") || it.startsWith("Статистика") }
            .take(8)
    }

    /** Озвучка по битам: ровно по строке на бит, лишнее отсекается, недостающее берётся из шаблона. */
    suspend fun voice(
        settings: LlmSettings,
        llm: LlmClient,
        topic: TopicCandidate,
        beats: List<Beat>,
    ): List<Beat> {
        if (!settings.isUsable || beats.isEmpty()) return beats
        val brief = LlmBrief(
            system = SYSTEM,
            user = buildString {
                appendLine("$OFFLINE_MARK · озвучка по битам")
                appendLine("Тема: ${topic.title}")
                appendLine("Обещание в хуке: ${topic.hook}")
                appendLine("Формат: ${topic.format.label}, всего ${topic.durationSec}с")
                appendLine("Прочитать вслух нужно ровно столько, сколько длится бит. Ни одного «привет, ребята».")
                appendLine()
                appendLine("Верни ${beats.size} строк — по одной на бит, без нумерации:")
                beats.forEach { beat ->
                    appendLine(
                        "${beat.startSec}-${beat.endSec}с · ${beat.role.label} · ${beat.screen.take(70)}",
                    )
                }
            },
            temperature = 0.75,
            maxTokens = (beats.size * 42).coerceIn(240, 1400),
        )
        val lines = runCatching { llm.complete(brief).text }
            .getOrNull().orEmpty()
            .lines()
            .map { it.trim().trimStart('-', '*', '•').replace(Regex("^\\d+\\s*[.)]\\s*"), "") }
            .filter { it.isNotBlank() }
        if (lines.size < beats.size) return beats
        return beats.mapIndexed { index, beat ->
            val line = lines[index].take(if (topic.format == VideoFormat.SHORTS) 150 else 260)
            beat.copy(voice = line.ifBlank { beat.voice })
        }
    }

    private val SYSTEM = """
Ты — редактор вертикальных и горизонтальных роликов для YouTube. Ты отвечаешь за то, чтобы
зрителя не выключили, а ролик можно было монетизировать без страйков.

Правила, которые ты не нарушаешь:
- говоришь на русском, на «ты», без канцелярита и без восклицательного крика;
- не обещаешь того, чего нет в структуре ролика;
- не предлагаешь брать чужие видео, чужую музыку, чужие нарезки и репосты;
- не предлагаешь накрутки, покупки просмотров, подписки за подписку, массовые жалобы;
- не пишешь «подпишись и поставь лайк» — только конкретную причину вернуться;
- фраза должна произноситься за то время, которое отведено на бит;
- markdown и таблицы не используешь, только строки текста.
""".trimIndent()
}
