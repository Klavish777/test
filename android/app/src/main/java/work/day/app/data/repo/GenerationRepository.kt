package work.day.app.data.repo

import kotlinx.coroutines.flow.StateFlow
import work.day.app.core.PersistedStore
import work.day.app.data.llm.LlmClient
import work.day.app.data.llm.LlmSettings
import work.day.app.data.platform.YouTubeResearch
import work.day.app.domain.agent.ViralEditor
import work.day.app.domain.engine.ViralLab
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.GenerationPlan
import work.day.app.domain.model.GenerationState
import work.day.app.domain.model.Platform
import work.day.app.domain.model.PublishItem
import work.day.app.domain.model.PublishState
import work.day.app.domain.model.ResearchItem
import work.day.app.domain.model.TopicCandidate
import work.day.app.domain.model.VideoFormat

/**
 * Оркестратор «Генерации»: статистика YouTube → темы → скелет → правки монтажёра →
 * проверка прав → пакет + ffmpeg-рецепт. Ничего не публикует и ничего не скачивает.
 *
 * Все шаги сохраняются в один JSON, поэтому результат переживает перезапуск, а
 * «Сгенерировать» при отсутствии ключа модели и API не падает, а честно отдаёт
 * детерминированный разбор с пометкой «демо-приоры».
 */
class GenerationRepository(
    private val store: PersistedStore<GenerationState>,
    private val settings: SettingsRepository,
    private val workspace: WorkspaceRepository,
    private val llm: () -> LlmClient,
    private val research: YouTubeResearch,
) {

    val state: StateFlow<GenerationState> = store.state

    val niches: List<String> get() = ViralLab.NICHES.map { it.name }

    fun setNiche(name: String) = store.update { it.copy(niche = name) }

    fun setFormat(format: VideoFormat) = store.update { it.copy(format = format.name, durationSec = 0) }

    fun setDuration(seconds: Int) = store.update { it.copy(durationSec = seconds) }

    fun format(): VideoFormat = VideoFormat.of(store.value.format)

    /** Ниша: явный выбор человека, иначе — ниша из профиля канала, иначе первая из списка. */
    fun activeNiche(): String =
        store.value.niche.ifBlank { workspace.profile.niche }.ifBlank { ViralLab.NICHES.first().name }

    fun suggestedDuration(): Int {
        val st = store.value
        return ViralLab.pickDuration(VideoFormat.of(st.format), ViralLab.statsOf(st.research))
    }

    /** Живая статистика нишы, если есть ключ API; иначе пустой список — и движок сам всё подпишет. */
    suspend fun refreshResearch(): Result<Int> = runCatching {
        val niche = ViralLab.nicheByName(activeNiche())
        val key = settings.youtubeApiKey().trim()
        if (key.isBlank()) {
            store.update { it.copy(niche = niche.name, research = emptyList(), researchAt = 0L) }
            return@runCatching 0
        }
        val items = research.fetch(key, niche.query).getOrElse { error ->
            store.update {
                it.copy(history = (listOf("research: ${error.message?.take(120)}") + it.history).take(30))
            }
            throw error
        }
        store.update {
            it.copy(
                niche = niche.name,
                research = items,
                researchAt = System.currentTimeMillis(),
                history = (listOf("исследовано ${items.size} роликов · ${niche.name}") + it.history).take(30),
            )
        }
        items.size
    }

    /** Шаг 1: темы + длительность. Именно это показывает кнопка «Сгенерировать». */
    suspend fun generate(): Result<List<TopicCandidate>> = runCatching {
        val niche = ViralLab.nicheByName(activeNiche())
        ensureResearch(niche)
        val st = store.value
        val format = VideoFormat.of(st.format)
        val stats = ViralLab.statsOf(st.research)
        val duration = if (st.durationSec > 0) st.durationSec.coerceIn(format.minSec, format.maxSec)
        else ViralLab.pickDuration(format, stats)
        val llmSettings = settings.llmNow()
        val titles = if (llmSettings.isUsable) {
            ViralEditor.topics(
                settings = llmSettings,
                llm = llm(),
                niche = niche,
                format = format,
                durationSec = duration,
                stats = stats,
                audience = workspace.profile.audience.ifBlank { workspace.profile.youtubeTitle },
            )
        } else {
            emptyList()
        }
        val topics = ViralLab.proposeTopics(
            niche = niche,
            research = st.research,
            format = format,
            requestedDuration = duration,
            llmTitles = titles,
            channelTitle = workspace.profile.youtubeTitle,
        )
        store.update {
            it.copy(
                topics = topics,
                durationSec = duration,
                history = (listOf("тем: ${topics.size} · ${if (stats.fromDemo) "демо-приоры" else "${stats.sample} роликов YouTube"}") + it.history).take(30),
            )
        }
        topics
    }

    private suspend fun ensureResearch(niche: ViralLab.Niche) {
        val st = store.value
        if (st.niche == niche.name && st.researchFresh) return
        runCatching { refreshResearch() }
    }

    /** Шаг 2: собираем план по выбранной теме (скелет → озвучка модели → правки → права → рецепт). */
    suspend fun build(topic: TopicCandidate, rewriteVoice: Boolean = true): Result<GenerationPlan> = runCatching {
        val skeleton = ViralLab.buildBeats(topic, store.value.research)
        val llmSettings = settings.llmNow()
        val spoken = if (rewriteVoice && llmSettings.isUsable) {
            ViralEditor.voice(llmSettings, llm(), topic, skeleton)
        } else {
            skeleton
        }
        val assetsRaw = ViralLab.assetsFor(topic, spoken)
        val scoreBefore = ViralLab.critique(spoken, topic, assetsRaw)
        val ((beats, assets), edits) = ViralLab.editPass(spoken, topic, assetsRaw)
        val scoreAfter = ViralLab.critique(beats, topic, assets)
        val packaging = ViralLab.packaging(topic, beats)
        val compliance = ViralLab.compliance(topic, beats, assets, packaging.title, packaging.description)
        val recipe = ViralLab.recipe(topic, beats, assets)
        val plan = GenerationPlan(
            id = "gen-${System.currentTimeMillis()}",
            createdAt = System.currentTimeMillis(),
            topic = topic.copy(score = scoreAfter),
            beats = beats,
            edits = edits,
            assets = assets,
            scoreBefore = scoreBefore,
            scoreAfter = scoreAfter,
            compliance = compliance,
            recipe = recipe,
            title = packaging.title,
            description = packaging.description,
            tags = packaging.tags,
            pinnedComment = packaging.pinnedComment,
            thumbnailBrief = packaging.thumbnailBrief,
            modelSource = if (llmSettings.isUsable) "модель ${llmSettings.model}" else "офлайн-движок",
        )
        store.update {
            it.copy(
                plan = plan,
                history = (listOf("собран «${plan.title.take(40)}» · балл ${scoreBefore.total}→${scoreAfter.total}") + it.history).take(30),
            )
        }
        plan
    }

    /** Повторить правки ещё раз: монтажёр не против пройтись по тому же плану. */
    suspend fun reEdit(): Result<GenerationPlan> = runCatching {
        val plan = store.value.plan ?: error("плана ещё нет")
        val (pair, edits) = ViralLab.editPass(plan.beats, plan.topic, plan.assets)
        val (beats, assets) = pair
        val score = ViralLab.critique(beats, plan.topic, assets)
        val compliance = ViralLab.compliance(plan.topic, beats, assets, plan.title, plan.description)
        val updated = plan.copy(
            beats = beats,
            assets = assets,
            edits = plan.edits + edits,
            scoreAfter = score,
            compliance = compliance,
            recipe = ViralLab.recipe(plan.topic, beats, assets),
        )
        store.update { it.copy(plan = updated) }
        updated
    }

    /**
     * Только в очередь на публикацию. Отправлять в канал само приложение не может и не будет:
     * права на запись мы не запрашиваем — публикацию подтверждает человек.
     */
    fun enqueueToChannel(plan: GenerationPlan, platform: Platform = Platform.YOUTUBE): PublishItem {
        val item = PublishItem(
            id = plan.id,
            taskId = plan.id,
            agent = AgentId.MAGNET,
            platform = platform,
            title = plan.title,
            body = buildString {
                appendLine(plan.description)
                appendLine()
                appendLine("Теги: ${plan.tags.joinToString(", ")}")
                appendLine("Длительность: ${plan.totalSec}с · формат ${plan.topic.format.label}")
                appendLine("Балл вирусности: ${plan.scoreAfter.total} (было ${plan.scoreBefore.total})")
                appendLine("Готов к публикации: ${if (plan.compliance.allowedToPublish) "да" else "нет — закрой blockers"}")
                appendLine("Сборка: ./render.sh из рецепта (ffmpeg), материалы — свои.")
                appendLine("Подготовил: ${ViralEditor.NAME} (${plan.modelSource})")
            },
            slotMinutes = BEST_SHORT_SLOT,
            state = PublishState.READY,
        )
        workspace.enqueue(item)
        store.update { st -> st.copy(history = (listOf("в очередь: ${plan.title.take(40)}") + st.history).take(30)) }
        return item
    }

    fun exportRecipe(plan: GenerationPlan): String = buildString {
        appendLine("=== manifest.json ===")
        appendLine(plan.recipe.manifest)
        appendLine("=== render.sh ===")
        appendLine(plan.recipe.script)
        appendLine("=== captions.srt ===")
        appendLine(plan.recipe.srt)
    }

    fun wipe() = store.replace(GenerationState())

    companion object {
        /** 18:30 — слот, который в большинстве ниш даёт вечерний пик; правится в очереди. */
        const val BEST_SHORT_SLOT = 18 * 60 + 30
    }
}
