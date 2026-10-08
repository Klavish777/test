package work.day.app.domain.model

/**
 * Плейбук — именованный набор действий агента с ритмом применения.
 * Агент не выдумывает задачи из воздуха: он крутит плейбуки, которые включил пользователь.
 */
data class Playbook(
    val id: String,
    val agent: AgentId,
    val title: String,
    val summary: String,
    val cadence: String,
    val kinds: List<TaskKind>,
)

object Playbooks {

    val all: List<Playbook> = listOf(
        // ── Магнит ────────────────────────────────────────────────────────────
        Playbook("magnet.packaging", AgentId.MAGNET, "Упаковка для поиска",
            "Заголовки, описания, обложки — всё, что отвечает за клик.",
            "каждый новый ролик",
            listOf(TaskKind.SEO_REWRITE, TaskKind.THUMBNAIL_AB, TaskKind.KEYWORD_CLUSTER)),
        Playbook("magnet.funnel", AgentId.MAGNET, "Воронка подписки",
            "Где зритель уходит и как добрать подписчика без просьб.",
            "1 раз в неделю",
            listOf(TaskKind.FUNNEL_AUDIT, TaskKind.SERIES_PLAN)),
        Playbook("magnet.trend", AgentId.MAGNET, "Трендовое окно",
            "Ловим рост форматы, пока окно открыто 24–48 часов.",
            "каждый день, 15 минут",
            listOf(TaskKind.TREND_JACK)),

        // ── Разведчик ──────────────────────────────────────────────────────────
        Playbook("scout.recycling", AgentId.SCOUT, "Один материал — пять площадок",
            "Нарезка и адаптация существующего контента, а не новая съёмка.",
            "после каждого длинного ролика",
            listOf(TaskKind.LONG_TO_VERTICAL, TaskKind.CROSS_POST_COPY, TaskKind.LOCALIZATION)),
        Playbook("scout.alliances", AgentId.SCOUT, "Чужая аудитория",
            "Коллаборации, присутствие в комментариях, посевы.",
            "2 касания в неделю",
            listOf(TaskKind.COLLAB_PITCH, TaskKind.COMMENT_PRESENCE, TaskKind.COMMUNITY_SEED)),

        // ── Ускоритель ─────────────────────────────────────────────────────────
        Playbook("booster.experiments", AgentId.BOOSTER, "Цикл экспериментов",
            "Две гипотезы в неделю, замер, вердикт, масштабирование.",
            "понедельник",
            listOf(TaskKind.WEEKLY_EXPERIMENT, TaskKind.WINNER_PATTERN)),
        Playbook("booster.cadence", AgentId.BOOSTER, "Ритм и буфер",
            "Частота публикаций, которую можно держать месяцами.",
            "воскресенье",
            listOf(TaskKind.CADENCE_PLAN, TaskKind.RETENTION_FIX)),
        Playbook("booster.catalog", AgentId.BOOSTER, "Оживление каталога",
            "Старые ролики с хорошим удержанием получают новый клик.",
            "1 раз в 2 недели",
            listOf(TaskKind.RETRANK_OLD, TaskKind.PAID_BOOST_TEST)),

        // ── Искра ──────────────────────────────────────────────────────────────
        Playbook("spark.first_hour", AgentId.SPARK, "Первый час",
            "Ответы, CTA и опросы в первые 60 минут после публикации.",
            "в день публикации",
            listOf(TaskKind.REPLY_DRAFTS, TaskKind.CTA_SCRIPT, TaskKind.POLL_PLAN)),
        Playbook("spark.community", AgentId.SPARK, "Комьюнити-маховик",
            "UGC, эфиры и модерация, которая держит тон.",
            "1 активация в неделю",
            listOf(TaskKind.UGC_LOOP, TaskKind.LIVE_EVENT_PLAN, TaskKind.MODERATION_RULES)),
    )

    fun byId(id: String): Playbook? = all.firstOrNull { it.id == id }

    fun forAgent(agent: AgentId): List<Playbook> = all.filter { it.agent == agent }

    /** Если пользователь ничего не включал — агент работает по всем своим плейбукам. */
    fun active(agent: AgentId, enabledIds: Set<String>): List<Playbook> =
        forAgent(agent).let { if (enabledIds.isEmpty()) it else it.filter { p -> p.id in enabledIds } }

    fun kindsOf(agent: AgentId, enabledIds: Set<String>): List<TaskKind> =
        active(agent, enabledIds).flatMap { it.kinds }.distinctBy { it.id }
}
