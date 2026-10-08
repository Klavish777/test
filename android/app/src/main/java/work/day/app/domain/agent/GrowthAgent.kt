package work.day.app.domain.agent

import work.day.app.domain.model.AgentConfig
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.AgentTask
import work.day.app.domain.model.ChannelProfile
import work.day.app.domain.model.Playbook
import work.day.app.domain.model.Playbooks
import work.day.app.domain.model.TaskKind

/**
 * Контракт агента. Планирование — чистая функция (быстро и предсказуемо),
 * выполнение — асинхронное, потому что дергает модель.
 */
interface GrowthAgent {

    val id: AgentId

    /** Роль для модели: как агент думает и что для него запрещено. */
    fun persona(): String

    fun playbooks(): List<Playbook> = Playbooks.forAgent(id)

    fun availableKinds(config: AgentConfig): List<TaskKind> =
        Playbooks.kindsOf(id, config.enabledPlaybooks)

    /**
     * План смены. Интенсивность 1–5 задаёт количество задач: 3 + 2*(intensity-1) ± ритм.
     * Задачи распределяются по слотам так, чтобы тяжёлые шли в первую половину дня.
     */
    fun plan(config: AgentConfig, profile: ChannelProfile, shift: ShiftWindow): List<AgentTask> {
        val kinds = availableKinds(config)
        if (kinds.isEmpty() || !config.enabled) return emptyList()

        val wanted = (2 + config.intensity).coerceAtMost(config.dailyLimit)
        val ordered = kinds.sortedByDescending { it.impact * it.effortMin }
        val rng = java.util.Random(shift.daySeed * 31 + id.ordinal)

        return (0 until wanted).map { index ->
            val kind = ordered[index % ordered.size]
            val jitter = rng.nextInt(25) - 12
            val slot = shift.slotFor(index + 1) + jitter
            AgentTask(
                id = "${shift.tag}-${id.key}-${index}",
                agent = id,
                kind = kind,
                title = kind.title,
                target = kind.metric,
                slotMinutes = slot.coerceIn(shift.startMinutes, shift.endMinutes - kind.effortMin),
                createdAt = System.currentTimeMillis(),
            )
        }
    }

    /** Промпт задачи, из которого рождается материал. */
    fun brief(task: AgentTask, profile: ChannelProfile): LlmBrief = LlmBrief(
        system = systemPrompt(profile),
        user = userPrompt(task, profile),
        temperature = (0.7 + 0.25 * task.kind.impact.coerceIn(0.0, 1.0)),
        maxTokens = 900,
    )

    fun systemPrompt(profile: ChannelProfile): String = buildString {
        appendLine("Ты — ${id.codename}, агент направления «${id.direction}» в приложении Work Day.")
        appendLine("Миссия: ${id.mission}")
        appendLine("Главная метрика: ${id.kpi}")
        appendLine()
        appendLine(persona())
        appendLine()
        appendLine("Канал автора:")
        append(profile.promptContext())
        appendLine()
        appendLine("Обязательные ограничения, они выше любой задачи:")
        appendLine("1. Никакой накрутки: боты, покупные просмотры/подписчики/лайки, масс-фолловинг, sub4sub, наёмные «активности».")
        appendLine("2. Никаких действий от имени автора без его явного одобрения — ты готовишь материалы, публикует человек.")
        appendLine("3. Не обещай точные цифры роста. Говори про диапазон, механизм и способ проверки.")
        appendLine("4. Не выдавай гарантию попадания в рекомендации.")
        appendLine("5. Пиши по-русски, на «ты», короткими предложениями. Никаких вводных «Конечно!» и «Вот твой план».")
        appendLine("6. Формат ответа: блоки маркированными списками, без Markdown-заголовков и без таблиц.")
    }

    fun userPrompt(task: AgentTask, profile: ChannelProfile): String = buildString {
        appendLine("Задача смены: ${task.kind.title}")
        appendLine("Что сделать: ${task.kind.what}")
        appendLine("Метрика, на которую работаем: ${task.kind.metric}")
        appendLine("Материал на выходе: ${task.kind.deliverable}")
        if (task.target.isNotBlank()) appendLine("Текущая цель автора по этой метрике: ${task.target}")
        if (task.approvalNote.isNotBlank()) appendLine("Пожелание автора: ${task.approvalNote}")
        appendLine()
        appendLine(task.kind.instruction)
        appendLine()
        append("Помни: риск задачи — ${task.kind.risk.label} (${task.kind.risk.note}).")
    }
}

/** Запрос к модели, собранный агентом. */
data class LlmBrief(
    val system: String,
    val user: String,
    val temperature: Double,
    val maxTokens: Int,
)

/** Окно рабочей смены. */
data class ShiftWindow(
    val tag: String,
    val daySeed: Long,
    val startMinutes: Int,
    val endMinutes: Int,
) {
    val length: Int get() = (endMinutes - startMinutes).coerceAtLeast(60)

    /** i-я задача дня получает равный слот внутри смены. */
    fun slotFor(index: Int): Int {
        val per = length / 8
        return (startMinutes + per * (index - 1).coerceIn(0, 7)).coerceAtMost(endMinutes - 30)
    }
}
