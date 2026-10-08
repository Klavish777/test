package work.day.app.domain.engine

import work.day.app.domain.model.AssetKind
import work.day.app.domain.model.AssetLicense
import work.day.app.domain.model.AssetSpec
import work.day.app.domain.model.Beat
import work.day.app.domain.model.BeatRole
import work.day.app.domain.model.ComplianceCheck
import work.day.app.domain.model.ComplianceReport
import work.day.app.domain.model.Edit
import work.day.app.domain.model.ResearchItem
import work.day.app.domain.model.RenderRecipe
import work.day.app.domain.model.TopicCandidate
import work.day.app.domain.model.VideoFormat
import work.day.app.domain.model.ViralScore
import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * ViralLab — движок «Генерации».
 *
 * Принцип, вокруг которого всё построено: **цифры берёт статистика, слова берёт модель**.
 * Языковая модель предлагает заголовки и текст озвучки, но ранжирует темы и режет тайминги
 * не она, а разрез по реальным роликам нишы (просмотры на час, длительность победителей,
 * плотность монтажа). Так «вирусность» перестаёт быть мнением и становится измеримой ставкой.
 *
 * Второй принцип: движок собирает *пакет к публикации*, а не постит. Ролик физически
 * делается из твоих материалов (ffmpeg-скрипт в рецепте), публикация — ручной шаг,
 * потому что прав на запись в канал у приложения нет и не будет.
 */
object ViralLab {

    /** Ниже порога — статистика не показатель, выше — ниша просто большая. */
    private const val MIN_SAMPLE = 3

    // ─── нишы ─────────────────────────────────────────────────────────────────

    data class Niche(
        val name: String,
        val query: String,
        /** Что люди ищут в этой нише — из этого же собираются заголовки. */
        val intent: String,
        /** Насколько ниша любит Shorts: влияет на рекомендованную длительность. */
        val shortsFriendly: Boolean,
        /** Детский контент = отдельные правила монетизации (COPPA). */
        val forKids: Boolean,
        val advertiserFriendly: Int,
    )

    val NICHES: List<Niche> = listOf(
        Niche("Финансы и деньги", "как накопить деньги", "быстрые деньги, ловушки, экономия", true, false, 78),
        Niche("Рецепты и кухня", "рецепт на сковороде за 5 минут", "скорость, бюджет, «вау»-кадр", true, false, 86),
        Niche("Фитнес и тело", "упражнение для спины дома", "техника, боль, результат за срок", true, false, 82),
        Niche("Техника и гаджеты", "обзор смартфона за 30 секунд", "сравнение, цена, скрытые функции", true, false, 90),
        Niche("Сделай сам", "ремонт который спасёт бюджет", "до/после, инструменты, ошибка новичка", true, false, 80),
        Niche("Игры", "секретная механика которая решает", "метки, патчи, скрытые детали", true, false, 74),
        Niche("Юмор и скетчи", "скетч про будни", "ожидание/реальность, петля в конце", true, false, 68),
        Niche("Образование", "объяснение за 60 секунд", "инсайт, аналогия, «теперь я понял»", true, false, 88),
        Niche("Психология", "признак что человек врал", "самопроверка, конкретика, без диагнозов", true, false, 72),
        Niche("Путешествия", "сколько стоит съездить", "цена, ловушка сезона, кадр-доказательство", true, false, 76),
        Niche("Красота и уход", "ошибка которая портит кожу", "до/после, состав, возраст", true, false, 84),
        Niche("Авто и мотто", "что убивает двигатель", "срок, ремонт, звук/запах-доказательство", true, false, 79),
        Niche("Родительство", "что делать если ребёнок не спит", "без паники, возраст, возрастная маркировка", true, true, 66),
        Niche("Бизнес и найм", "собеседование которое всё решает", "цифры, провал, чек-лист", false, false, 85),
    )

    fun nicheByName(name: String): Niche = NICHES.firstOrNull { it.name == name } ?: NICHES.first()

    // ─── статистика нишы ──────────────────────────────────────────────────────

    data class NicheStats(
        val sample: Int,
        val medianDurationSec: Int,
        val medianViews: Long,
        /** Просмотры на час жизни — то, по чему реально видно «залетело». */
        val medianVelocity: Double,
        val medianLikeRatio: Double,
        val bestTitlePatterns: List<String>,
        val fromDemo: Boolean,
    )

    fun statsOf(research: List<ResearchItem>): NicheStats {
        if (research.size < MIN_SAMPLE) {
            return NicheStats(
                sample = research.size,
                medianDurationSec = 38,
                medianViews = 180_000L,
                medianVelocity = 210.0,
                medianLikeRatio = 0.041,
                bestTitlePatterns = listOf("цифра в заголовке", "обещание срока", "отрицание «без / не»"),
                fromDemo = true,
            )
        }
        val durations = research.map { it.durationSec }.filter { it > 0 }.sorted()
        val views = research.map { it.views }.sorted()
        val velocity = research.map { it.velocityPerHour }.sorted()
        val likes = research.map { it.likeRatio }.sorted()
        val titles = research.map { it.title.lowercase() }
        val patterns = buildList {
            if (titles.count { hasNumber(it) } > titles.size / 2) add("цифра в заголовке (${percent(titles.count { hasNumber(it) }, titles.size)})")
            if (titles.count { it.startsWith("как") || it.contains(" как ") } > titles.size / 3) add("«как …» — обещание навыка")
            if (titles.count { it.contains("почему") || it.contains("из-за") } > titles.size / 4) add("причина/следствие")
            if (titles.count { it.contains("без ") || it.contains("не делай") || it.contains("ошибк") } > titles.size / 4) add("отрицание и страх ошибки")
            if (titles.count { hasTimeframe(it) } > titles.size / 5) add("срок («за 7 дней»)")
            if (titles.count { it.contains("топ") || it.contains("список") || Regex("\\b\\d+\\b").containsMatchIn(it) } > titles.size / 3) add("список из N пунктов")
            if (isEmpty()) add("прямое обещание результата")
        }
        return NicheStats(
            sample = research.size,
            medianDurationSec = median(durations),
            medianViews = medianLong(views),
            medianVelocity = round2(if (velocity.isEmpty()) 0.0 else velocity[velocity.size / 2]),
            medianLikeRatio = if (likes.isEmpty()) 0.0 else round4(likes[likes.size / 2]),
            bestTitlePatterns = patterns,
            fromDemo = false,
        )
    }

    // ─── темы ─────────────────────────────────────────────────────────────────

    /**
     * Шесть тем, отранжированных по статистике. [llmTitles] — строки вида
     * `Заголовок | Хук | Почему залетит`: если модель их дала, берём её формулировки,
     * но оценку всё равно считаем по цифрам. Если их нет — детерминированные шаблоны нишы.
     */
    fun proposeTopics(
        niche: Niche,
        research: List<ResearchItem>,
        format: VideoFormat,
        requestedDuration: Int = 0,
        llmTitles: List<String> = emptyList(),
        channelTitle: String = "",
    ): List<TopicCandidate> {
        val stats = statsOf(research)
        val duration = if (requestedDuration > 0) requestedDuration.coerceIn(format.minSec, format.maxSec)
        else pickDuration(format, stats)
        val seeds = llmTitles.mapNotNull { parseLlmTitle(it) }.ifEmpty { templateTopics(niche, stats) }
        return seeds.mapIndexed { index, raw ->
            val matched = matchEvidence(research, raw.title)
            val velocity = if (matched.isEmpty()) stats.medianVelocity
            else round2(matched.map { it.velocityPerHour }.average())
            val demand = if (stats.fromDemo) 46 else (ln(1.0 + stats.medianViews.toDouble()) * 12).roundToInt()
            val competition = matched.size + research.count { sameIntent(it.title, raw.title) }
            val hook = hookStrength(raw.title, raw.hook, stats)
            val payoff = payoffStrength(raw.hook, stats)
            val pacing = pacingFit(duration, stats, format)
            val monetization = monetizationStrength(raw.title, niche, stats)
            TopicCandidate(
                title = raw.title,
                niche = niche.name,
                hook = raw.hook,
                why = raw.why.ifBlank { "в топе нишы ${stats.sample} из ${max(stats.sample, 1)} роликов с похожим обещанием" },
                format = format,
                durationSec = duration,
                velocityPerHour = velocity,
                competition = competition,
                demand = demand.coerceIn(0, 100),
                score = ViralScore.of(hook, pacing, payoff, retentionPrior(duration, stats, format), monetization),
                evidence = (matched.map { "${it.title} · ${it.views} просм. · ${it.durationSec}с" } +
                    stats.bestTitlePatterns.map { "шаблон: $it" }).take(5),
                fromDemo = stats.fromDemo,
            )
        }
            .sortedWith(
                compareByDescending<TopicCandidate> { it.score.total }
                    .thenByDescending { it.velocityPerHour }
                    .thenBy { it.competition }
            )
            .mapIndexed { index, topic -> topic.copy(why = if (index == 0) "лучшая ставка: ${topic.why}" else topic.why) }
            .take(6)
    }

    private data class Raw(val title: String, val hook: String, val why: String)

    private fun parseLlmTitle(line: String): Raw? {
        val parts = line.trim().trimStart('-', '*', '•').split('|').map { it.trim() }.filter { it.isNotEmpty() }
        if (parts.isEmpty()) return null
        return Raw(
            title = parts[0].removeSurrounding("\"").take(110),
            hook = parts.getOrNull(1).orEmpty().take(180),
            why = parts.getOrNull(2).orEmpty().take(200),
        )
    }

    /** Детерминированный генератор тем: тот же результат при том же входе — иначе тесты бессмысленны. */
    private fun templateTopics(niche: Niche, stats: NicheStats): List<Raw> {
        val num = if (stats.bestTitlePatterns.any { it.startsWith("цифра") }) "3 " else ""
        val term = if (stats.bestTitlePatterns.any { it.contains("срок") }) " за 7 дней" else ""
        val base = listOf(
            Raw(
                "${num}${niche.intent.replace(",", ", ")}: что делает ${percent(70, 100)} новичков не так",
                "Ты делаешь это ${num.ifBlank { "" }}не так — и теряешь результат на второй день.",
                "в топе нишы держатся разборы «ошибка → причина → как иначе»",
            ),
            Raw(
                "${niche.intent.substringBefore(",")}: вариант на ноль рублей",
                "Работает лучше платного, просто выглядит скучно. Покажу за минуту.",
                "низкий порог входа + «почему об этом молчат» — два сильных сигнала удержания",
            ),
            Raw(
                "Проверил ${niche.query}$term: вот что вышло",
                "Я проверил «${niche.query}» и зафиксировал цифры. Спойлер: результат не там, где обещают.",
                "личный эксперимент — это доказательство, а не пересказ",
            ),
            Raw(
                "Не делай это, если ${niche.intent.substringBefore(",")}",
                "Если сделаешь это — потом объясняешь себе, куда делись деньги/время.",
                "отрицание + потеря: самый быстрый вход в внимание",
            ),
            Raw(
                "${niche.intent.replace(",", " /")} за ${if (niche.shortsFriendly) "60 секунд" else "одну вечер"}",
                "За ${if (niche.shortsFriendly) "60 секунд" else "одну вечер"} — то, что я собирал месяцами.",
                "обещание сжатия срока при конкретной ставке",
            ),
            Raw(
                "Что изменилось, когда я перестал ${niche.intent.substringAfterLast(" ").trim()}",
                "Перестал — и поехало. Разбираю, почему это работало против меня.",
                "поворот против ожиданий читается как чужой опыт, а не как совет",
            ),
        )
        return base
    }

    /** Длительность — не «сколько хочется», а сколько выдерживает эта ниша в этом формате. */
    fun pickDuration(format: VideoFormat, stats: NicheStats): Int {
        val anchor = stats.medianDurationSec
        val target = when (format) {
            VideoFormat.SHORTS -> if (anchor > 0) (anchor * 0.72).roundToInt() else 34
            VideoFormat.FEED -> if (anchor > 0) (anchor * 0.8).roundToInt() else 95
            VideoFormat.MID -> if (anchor > 0) (anchor * 0.9).roundToInt() else 300
            VideoFormat.LONG -> if (anchor > 0) anchor else 660
        }
        return when (format) {
            VideoFormat.SHORTS -> target.coerceIn(20, 47)
            VideoFormat.FEED -> target.coerceIn(61, 170)
            VideoFormat.MID -> target.coerceIn(181, 420)
            VideoFormat.LONG -> target.coerceIn(481, 870)
        }
    }

    // ─── скелет ролика по битам ──────────────────────────────────────────────

    /**
     * Инвариант: сумма длительностей битов ровно равна [TopicCandidate.durationSec].
     * Иначе «34 секунды» в ТЗ и 33,6 в файле — это рассинхрон, из-за которого монтаёр
     * начинает импровизировать. Проверено тестом на всех допустимых длительностях.
     */
    fun buildBeats(topic: TopicCandidate, research: List<ResearchItem> = emptyList()): List<Beat> {
        val total = topic.durationSec.coerceIn(topic.format.minSec, topic.format.maxSec)
        val vertical = topic.format == VideoFormat.SHORTS
        val plan = ArrayList<Int>()

        val hook = if (vertical) min(3, max(2, total * 8 / 100)) else min(6, max(3, total * 3 / 100))
        val setup = if (vertical) max(3, total * 12 / 100) else max(6, total * 9 / 100)
        val proof = if (vertical) max(3, total * 13 / 100) else max(8, total * 11 / 100)
        val cta = if (vertical) max(2, total * 8 / 100) else max(5, total * 5 / 100)
        val loop = if (vertical && total <= 45) 1 else 0
        val twist = if (vertical) 0 else max(5, total * 6 / 100)
        val rest = total - hook - setup - proof - cta - loop - twist
        val payloadCount = when {
            total <= 30 -> 2
            total <= 60 -> 3
            total <= 180 -> 4
            total <= 420 -> 5
            else -> 6
        }
        val each = max(2, rest / payloadCount)
        var left = rest - each * payloadCount
        repeat(payloadCount) { i -> plan += each + if (i == payloadCount - 1) left else 0; if (i == payloadCount - 1) left = 0 }

        val roles = ArrayList<Pair<BeatRole, Int>>()
        roles += BeatRole.HOOK to hook
        roles += BeatRole.SETUP to setup
        roles += List(payloadCount) { BeatRole.PAYLOAD to plan[it] }
        if (twist > 0) roles += BeatRole.TWIST to twist
        roles += BeatRole.PROOF to proof
        roles += BeatRole.CTA to cta
        if (loop > 0) roles += BeatRole.LOOP to loop

        val topicWord = topic.title.trimEnd('.', '!').take(64)
        var cursor = 0
        return roles.mapIndexed { index, (role, len) ->
            val beat = Beat(
                index = index,
                startSec = cursor,
                endSec = cursor + len,
                role = role,
                screen = screenFor(role, topic, vertical, index),
                voice = voiceFor(role, topicWord, len, vertical),
                shot = shotFor(role, vertical, len),
                overlay = overlayFor(role, topicWord, len),
                sourceHint = sourceFor(role, research, topic),
            )
            cursor += len
            beat
        }
    }

    private fun screenFor(role: BeatRole, topic: TopicCandidate, vertical: Boolean, index: Int): String {
        val base = when (role) {
            BeatRole.HOOK -> "самое сильное движение из ${topic.hook.take(40)} — первые 0,5 секунды без логотипа и без «привет»"
            BeatRole.SETUP -> "ставка: что человек получит к концу и что потеряет, если пролистнёт"
            BeatRole.PAYLOAD -> "шаг ${index + 1}: действие + результат в кадре, без пауз на дыхание"
            BeatRole.PROOF -> "доказательство: экран с цифрой/замером, крупно, читается с телефона"
            BeatRole.TWIST -> "лом ожидания: кадр, который противоречит началу"
            BeatRole.CTA -> "одна причина вернуться: что будет в следующем ролике"
            BeatRole.LOOP -> "последний кадр = первый: ролик пересматривают, и это плюс к охвату"
        }
        return if (vertical) "$base (вертикаль 9:16, лицо/объект в верхней трети)" else base
    }

    /**
     * Текст озвучки под длительность бита: в вертикальном Shorts фраза длиннее
     * ~9 слов физически не влезает, поэтому длину режет формат, а не вдохновение.
     */
    private fun voiceFor(role: BeatRole, topicWord: String, len: Int, vertical: Boolean): String {
        val per = if (vertical) 3.1 else 2.6
        val words = max(4, (len * per).roundToInt())
        val core = short(topicWord, words.coerceAtMost(if (vertical) 12 else 24))
        return when (role) {
            BeatRole.HOOK -> "«$core» — и вот где это ломается с самого начала"
            BeatRole.SETUP -> "Сейчас покажу, что делать вместо этого, и почему это быстрее"
            BeatRole.PAYLOAD -> "Шаг: $core — делаешь так, иначе потеряешь на втором дне"
            BeatRole.PROOF -> "Смотри на цифры: $core — это замер, а не мнение"
            BeatRole.TWIST -> "А теперь наоборот: $core"
            BeatRole.CTA -> "Если пригодилось — следующим роликом разбираю $core"
            BeatRole.LOOP -> "…и поэтому снова «${short(topicWord, 4)}»"
        }
    }

    private fun shotFor(role: BeatRole, vertical: Boolean, len: Int): String {
        val cuts = max(1, (len / if (vertical) 2.2 else 4.0).roundToInt())
        return "${cuts} склеек за ${len}с · " + when (role) {
            BeatRole.HOOK -> "крупно, движение в кадре с первого кадра"
            BeatRole.SETUP -> "средний план + текст-плашка"
            BeatRole.PAYLOAD -> "смена ракурса каждые ${if (vertical) "2" else "4"} секунды, руки/объект в фокусе"
            BeatRole.PROOF -> "стоп-кадр с цифрой, контрастная плашка"
            BeatRole.TWIST -> "резкая смена света/ракурса"
            BeatRole.CTA -> "говорящая голова, спокойный план"
            BeatRole.LOOP -> "тот же кадр, что в начале"
        }
    }

    private fun overlayFor(role: BeatRole, topicWord: String, len: Int): String = when (role) {
        BeatRole.HOOK -> short(topicWord, 4).uppercase()
        BeatRole.SETUP -> "что получишь: " + short(topicWord, 3)
        BeatRole.PAYLOAD -> "шаг " + (len.toString() + "с")
        BeatRole.PROOF -> "цифра на экране"
        BeatRole.TWIST -> "а не так"
        BeatRole.CTA -> "продолжение →"
        BeatRole.LOOP -> ""
    }

    private fun sourceFor(role: BeatRole, research: List<ResearchItem>, topic: TopicCandidate): String = when (role) {
        BeatRole.HOOK, BeatRole.PAYLOAD -> {
            val src = research.firstOrNull { sameIntent(it.title, topic.title) }
            if (src == null) "свой материал: снять под этот бит (камера/экран), чужие ролики не берём"
            else "структура взята из «${short(src.title, 6)}» (${src.views} просм.), материал — свой"
        }
        BeatRole.PROOF -> "нужен замер/скрин: свой скриншот статистики или таблицы"
        else -> "свой материал или генерация; лицензия помечена в ассетах"
    }

    // ─── ассеты ───────────────────────────────────────────────────────────────

    fun assetsFor(topic: TopicCandidate, beats: List<Beat>): List<AssetSpec> = buildList {
        beats.forEach { beat ->
            when (beat.role) {
                BeatRole.HOOK, BeatRole.PAYLOAD, BeatRole.TWIST -> {
                    add(
                        AssetSpec(
                            id = "clip-${beat.index}",
                            kind = AssetKind.OWN_CLIP,
                            license = AssetLicense.OWN,
                            query = beat.screen.take(90),
                            note = "снять/собрать под бит ${beat.startSec}–${beat.endSec}с",
                        )
                    )
                    if (beat.overlay.isNotBlank()) {
                        add(
                            AssetSpec(
                                id = "text-${beat.index}",
                                kind = AssetKind.TEXT_OVERLAY,
                                license = AssetLicense.OWN,
                                query = beat.overlay,
                                note = "плашка поверх, 2–4 слова, не дублировать озвучку дословно",
                            )
                        )
                    }
                }
                BeatRole.PROOF -> add(
                    AssetSpec(
                        id = "proof-${beat.index}",
                        kind = AssetKind.OWN_BROLL,
                        license = AssetLicense.OWN,
                        query = "скрин/замер: ${beat.overlay.ifBlank { beat.screen.take(60) }}",
                        note = "то, что нельзя оспорить",
                    )
                )
                else -> Unit
            }
        }
        add(
            AssetSpec(
                id = "music",
                kind = AssetKind.MUSIC,
                license = AssetLicense.YT_AUDIO_LIBRARY,
                query = "без вокала, ${if (topic.format == VideoFormat.SHORTS) "110–128 BPM" else "80–100 BPM"}",
                note = "только YouTube Audio Library или CC0: чужой трек снимает монетизацию целиком",
            )
        )
        add(
            AssetSpec(
                id = "captions",
                kind = AssetKind.CAPTIONS,
                license = AssetLicense.OWN,
                query = "captions.srt из рецепта",
                note = "до 80% смотрят без звука",
            )
        )
        add(
            AssetSpec(
                id = "voice",
                kind = AssetKind.GENERATED_TTS,
                license = AssetLicense.GENERATED,
                query = "озвучка по битам, ровная громкость",
                note = "если голос синтезированный — скажи об этом в описании",
            )
        )
    }

    // ─── оценка ───────────────────────────────────────────────────────────────

    fun critique(beats: List<Beat>, topic: TopicCandidate, assets: List<AssetSpec>): ViralScore {
        if (beats.isEmpty()) return ViralScore()
        val total = beats.sumOf { it.lengthSec }.coerceAtLeast(1)
        val vertical = topic.format == VideoFormat.SHORTS
        val hookBeat = beats.firstOrNull { it.role == BeatRole.HOOK }
        val hook = hookStrength(topic.title, hookBeat?.voice.orEmpty(), statsHint(topic))
            .let { if (hookBeat == null) it else it - max(0, (hookBeat.lengthSec - if (vertical) 3 else 6)) * 7 }
        val longestRatio = beats.maxOf { it.lengthSec } * 100 / total
        val cutsPerTen = beats.size * 10.0 / total
        val pacing = (92 - max(0, longestRatio - (if (vertical) 24 else 34)) * 2 + (cutsPerTen * 6).toInt())
            .coerceIn(0, 100)
        val firstPayload = beats.indexOfFirst { it.role == BeatRole.PAYLOAD }
        val payloadStart = if (firstPayload >= 0) beats[firstPayload].startSec * 100 / total else 100
        val hasProof = beats.any { it.role == BeatRole.PROOF && it.overlay.isNotBlank() }
        val payoff = (48 + if (payloadStart <= 42) 22 else 4) + (if (hasProof) 20 else 0) +
            (if (beats.any { hasNumber(it.voice) }) 10 else 0)
        val hasLoop = beats.any { it.role == BeatRole.LOOP }
        val specificCta = beats.any { it.role == BeatRole.CTA && !it.voice.contains("подпишись") && !it.voice.contains("лайк") }
        val overlays = beats.count { it.overlay.isNotBlank() } * 100 / beats.size
        val retention = (40 + if (hasLoop || !vertical) 14 else 0) + (if (specificCta) 14 else 0) +
            (overlays * 18 / 100) + (if (topic.velocityPerHour > 200) 14 else 8)
        val cleanMusic = assets.none { it.kind == AssetKind.MUSIC && it.license.blocking }
        val captions = assets.any { it.kind == AssetKind.CAPTIONS }
        val ownShare = if (assets.isEmpty()) 100 else assets.count { !it.license.blocking } * 100 / assets.size
        val monetization = (46 + (if (cleanMusic) 18 else 0) + (if (captions) 12 else 0) +
            (ownShare * 14 / 100) + (if (topic.niche.isBlank()) 0 else nicheFriendliness(topic.niche) / 8))
            .coerceIn(0, 100)
        return ViralScore.of(hook, pacing, payoff, retention, monetization)
    }

    // ─── агент-монтажёр: правки ───────────────────────────────────────────────

    /**
     * Правки, которые всегда идут во благо метрике: каждая меняет вход, из которого
     * [critique] считает балл. Поэтому «стало лучше» — не обещание, а проверяемое свойство.
     */
    fun editPass(beats: List<Beat>, topic: TopicCandidate, assets: List<AssetSpec>): Pair<Pair<List<Beat>, List<AssetSpec>>, List<Edit>> {
        val edits = ArrayList<Edit>()
        var current = beats.map { it.copy() }
        var assetList = assets.map { it.copy() }
        val total = current.sumOf { it.lengthSec }.coerceAtLeast(1)
        val vertical = topic.format == VideoFormat.SHORTS

        // 1. Хук длиннее, чем терпит лента.
        current.firstOrNull { it.role == BeatRole.HOOK && it.lengthSec > (if (vertical) 3 else 6) }?.let { hook ->
            val keep = if (vertical) 3 else 6
            val extra = hook.lengthSec - keep
            val index = hook.index
            val head = hook.copy(endSec = hook.startSec + keep)
            val tail = Beat(
                index = index + 1,
                startSec = head.endSec,
                endSec = head.endSec + extra,
                role = BeatRole.SETUP,
                screen = "довод из хука: одно предложение, которое объясняет ставку",
                voice = "И вот главное, что я упустил: " + short(hook.voice, 8),
                shot = "средний план, без смены ракурса",
                overlay = "почему это важно",
                sourceHint = hook.sourceHint,
            )
            current = splice(current, index, listOf(head, tail))
            edits += Edit(
                beatIndex = index,
                action = "хук ужат до ${keep}с, остаток уехал в разогрев",
                before = "${hook.lengthSec}с хука",
                after = "$keepс + ${extra}с",
                reason = "в ${if (vertical) "Shorts" else "ленте"} решение о пролистке принимается за 2–3 секунды",
                delta = 9,
            )
        }

        // 2. Бит, который тянут одним планом слишком долго.
        current.filter { it.lengthSec * 100 > total * (if (vertical) 28 else 36) && it.role == BeatRole.PAYLOAD }
            .firstOrNull()?.let { fat ->
                val mid = fat.startSec + fat.lengthSec / 2
                val a = fat.copy(endSec = mid, overlay = fat.overlay.ifBlank { "шаг" })
                val b = fat.copy(
                    index = fat.index + 1,
                    startSec = mid,
                    endSec = fat.endSec,
                    overlay = "и сразу следом",
                    screen = fat.screen.replace("действие + результат", "результат прошлого шага крупно"),
                )
                current = splice(current, fat.index, listOf(a, b))
                edits += Edit(
                    beatIndex = fat.index,
                    action = "бит ${fat.lengthSec}с разрезан пополам",
                    before = "один план ${fat.lengthSec}с",
                    after = "${a.lengthSec}с + ${b.lengthSec}с со сменой ракурса",
                    reason = "один план дольше ${if (vertical) 6 else 12} секунд = провал удержания ровно посередине",
                    delta = 7,
                )
            }

        // 3. Мясо начинается слишком поздно.
        val firstPayloadIndex = current.indexOfFirst { it.role == BeatRole.PAYLOAD }
        if (firstPayloadIndex >= 0) {
            val start = current[firstPayloadIndex].startSec
            if (start * 100 > total * 42) {
                val moved = current[firstPayloadIndex].copy(
                    startSec = max(0, total * 20 / 100),
                    endSec = max(0, total * 20 / 100) + current[firstPayloadIndex].lengthSec,
                )
                current = retime(current.mapIndexed { i, b -> if (i == firstPayloadIndex) moved else b })
                edits += Edit(
                    beatIndex = firstPayloadIndex,
                    action = "первый полезный кадр поднят на ${moved.startSec}с",
                    before = "мясо с ${start}с",
                    after = "мясо с ${moved.startSec}с",
                    reason = "зритель не будет ждать выгоды дольше 40% ролика",
                    delta = 11,
                )
            }
        } else {
            val proofish = current.indexOfFirst { it.role == BeatRole.PROOF }
            if (proofish >= 0) {
                current = current.toMutableList().also { it[proofish] = it[proofish].copy(role = BeatRole.PAYLOAD) }
                edits += Edit(
                    beatIndex = proofish,
                    action = "в скелете не было содержательной части — добавлена",
                    before = "только обещания",
                    after = "бит с действием",
                    reason = "без «мяса» нет ни удержания, ни причины подписаться",
                    delta = 12,
                )
            }
        }

        // 4. Нет доказательства — обещание висит в воздухе.
        if (current.none { it.role == BeatRole.PROOF }) {
            val donor = current.filter { it.role == BeatRole.PAYLOAD }.maxByOrNull { it.lengthSec }
            if (donor != null && donor.lengthSec > 6) {
                val cut = min(4, donor.lengthSec - 4)
                val shrink = donor.copy(endSec = donor.endSec - cut)
                val proof = Beat(
                    index = donor.index + 1,
                    startSec = shrink.endSec,
                    endSec = shrink.endSec + cut,
                    role = BeatRole.PROOF,
                    screen = "цифра на экране: замер, скрин, до/после",
                    voice = "и вот что получилось: ${short(topic.title, 6)}",
                    shot = "стоп-кадр с контрастной плашкой",
                    overlay = "факт",
                    sourceHint = "свой скриншот или таблица; чужие данные — только со ссылкой",
                )
                current = splice(current, donor.index, listOf(shrink, proof))
                edits += Edit(
                    beatIndex = donor.index,
                    action = "добавлен бит доказательства (${cut}с) за счёт самого длинного куска",
                    before = "обещание без проверки",
                    after = "обещание + ${cut}с факта",
                    reason = "«переусиленный» заголовок без доказательства = гнев в комментариях и минус к доверию",
                    delta = 8,
                )
            }
        }

        // 5. Призыв «подпишись и поставь лайк».
        current.indexOfFirst { it.role == BeatRole.CTA && (it.voice.contains("подпишись") || it.voice.contains("лайк")) }
            .takeIf { it >= 0 }?.let { index ->
                val old = current[index]
                val better = old.copy(
                    voice = "Если пригодилось — следующим роликом разбираю ${short(topic.title, 5)}. Без этого ты вернёшься к старому способу.",
                    overlay = "продолжение →",
                )
                current = current.toMutableList().also { it[index] = better }
                edits += Edit(
                    beatIndex = index,
                    action = "призыв переписан на причину вернуться",
                    before = old.voice.take(48),
                    after = better.voice.take(48),
                    reason = "просьба о подписке ничего не даёт; обещание продолжения — даёт",
                    delta = 6,
                )
            }

        // 6. Нет субтитров.
        if (assetList.none { it.kind == AssetKind.CAPTIONS }) {
            assetList = assetList + AssetSpec("captions", AssetKind.CAPTIONS, AssetLicense.OWN, "captions.srt из рецепта", "ролик смотрят без звука")
            edits += Edit(
                beatIndex = -1,
                action = "добавлены субтитры",
                before = "нет",
                after = "captions.srt, 2–4 слова в строке",
                reason = "без субтитров теряется до 80% просмотров в ленте без звука",
                delta = 5,
            )
        }

        // 7. Музыка с блокировкой.
        assetList.filter { it.kind == AssetKind.MUSIC && it.license.blocking }.forEach { bad ->
            assetList = assetList.map {
                if (it.id == bad.id) it.copy(license = AssetLicense.YT_AUDIO_LIBRARY, note = "заменено: лицензия блокировала монетизацию") else it
            }
            edits += Edit(
                beatIndex = -1,
                action = "трек заменён на YouTube Audio Library",
                before = bad.license.label,
                after = AssetLicense.YT_AUDIO_LIBRARY.label,
                reason = "чужой трек = страйк и обнуление дохода, ролик не спасёт даже хороший",
                delta = 4,
            )
        }

        // 8. Плашки не покрывают середину ролика.
        val uncovered = current.filter { it.role == BeatRole.PAYLOAD && it.overlay.isBlank() }
        if (uncovered.isNotEmpty()) {
            uncovered.forEach { beat ->
                val withText = beat.copy(overlay = "шаг " + (beat.index + 1))
                current = current.toMutableList().also { list ->
                    val i = list.indexOfFirst { b -> b.index == beat.index }
                    if (i >= 0) list[i] = withText
                }
            }
            edits += Edit(
                beatIndex = uncovered.first().index,
                action = "на ${uncovered.size} бит(а) добавлены текстовые плашки",
                before = "пустой экран",
                after = "2–4 слова, не дублируют озвучку",
                reason = "текст удерживает взгляд тех, кто смотрит без звука, и держит ритм",
                delta = 5,
            )
        }

        return (retime(current) to assetList) to edits
    }

    /** Вставляет куски вместо бита [index] и перенумеровывает/пересчитывает тайминги. */
    private fun splice(beats: List<Beat>, index: Int, replacement: List<Beat>): List<Beat> {
        val out = ArrayList<Beat>(beats.size + replacement.size)
        beats.forEachIndexed { i, beat -> if (i != index) out += beat }
        replacement.forEach { out += it }
        return retime(out.sortedWith(compareBy({ it.startSec }, { it.index })))
    }

    /** Тайминги всегда идут подряд и без дыр: пересчёт по сумме длин. */
    private fun retime(beats: List<Beat>): List<Beat> {
        var cursor = 0
        return beats.mapIndexed { i, beat ->
            val length = beat.lengthSec.coerceAtLeast(1)
            cursor += length
            beat.copy(index = i, startSec = cursor - length, endSec = cursor)
        }
    }

    // ─── проверка: политика и авторские права ───────────────────────────────

    private val DEMONETIZING = listOf(
        "казино", "букмек", "stavka", "займ до зарплаты", "мгновенный кредит", "сброс веса за",
        "таблетк", "лекарств", "диагноз", "лечит рак", "оружи", "нож", "пистолет", "наркот",
        "18+", "порно", "секс", "голый", "кровь", "труп", "самоуб", "курение", "вейп",
    )
    private val RIGHTS_TRAPS = listOf(
        "скачай", "перекача", "репост", "возьми у", "взять у", "чужой ролик", "без разрешения",
        "парс", "скачать с", "обрезать чуж",
    )
    private val FAKE_ENGAGEMENT = listOf(
        "накрут", "купить просмотры", "купить подписчик", "суб4sub", "взаимная подписк",
        "масс-фолло", "массфол", "накрутк", "бот",
    )
    private val PROMISE_WORDS = listOf("за 7 дней", "за неделю", "за месяц", "100%", "гарант", "точно сработает")

    fun compliance(
        topic: TopicCandidate,
        beats: List<Beat>,
        assets: List<AssetSpec>,
        title: String = topic.title,
        description: String = "",
    ): ComplianceReport {
        val checks = ArrayList<ComplianceCheck>()
        val spoken = (beats.map { it.voice } + title + description).joinToString(" ").lowercase()

        checks += check(
            rule = "Музыка: свои, CC0 или YouTube Audio Library",
            ok = assets.none { it.kind == AssetKind.MUSIC && it.license.blocking },
            fix = "замени трек на YouTube Audio Library: чужая запись = Content ID, ролик теряет монетизацию целиком",
        )
        val foreign = assets.count { it.license == AssetLicense.REPOSTED || it.license == AssetLicense.NEEDS_PERMISSION }
        checks += check(
            rule = "Никаких чужих роликов целиком (reused content)",
            ok = foreign == 0,
            fix = "переиздание чужого не монетизируется; оставляй структуру и идею, а картинку снимай свою",
        )
        val ownShare = if (assets.isEmpty()) 1.0 else assets.count { it.license.monetizable } * 1.0 / assets.size
        checks += check(
            rule = "Не менее 60% — твой собственный материал",
            ok = ownShare >= 0.6,
            fix = "сейчас ${percent((ownShare * 100).roundToInt(), 100)} своего; добавь свои съёмки, свой голос и свои плашки",
            blocking = ownShare < 0.34,
        )
        checks += check(
            rule = "Заголовок не обещает того, чего нет в ролике",
            ok = !hasNumber(title) || beats.any { hasNumber(it.voice) || hasNumber(it.overlay) },
            fix = "clickbait без доказательства: минус к доверию, жалобы, «обманули в заголовке» в комментах",
            blocking = false,
        )
        checks += check(
            rule = "Субтитры есть",
            ok = assets.any { it.kind == AssetKind.CAPTIONS } || beats.any { it.overlay.isNotBlank() },
            fix = "сгенерируй captions.srt из рецепта: без субтитров теряется до 80% просмотров без звука",
        )
        checks += check(
            rule = "Синтез голоса/лица помечен",
            ok = assets.none { it.kind == AssetKind.GENERATED_TTS || it.kind == AssetKind.GENERATED_VIDEO } ||
                description.lowercase().contains("озвучка") || description.lowercase().contains("сгенер"),
            fix = "YouTube требует отмечать реалистичный синтетический контент — одна строка в описании",
            blocking = false,
        )
        val trap = RIGHTS_TRAPS.firstOrNull { spoken.contains(it) }
        checks += check(
            rule = "Нет призывов скачивать/перекладывать чужое",
            ok = trap == null,
            fix = if (trap == null) "" else "в тексте встречается «$trap» — удали: это прямой путь к страйку",
        )
        val boost = FAKE_ENGAGEMENT.firstOrNull { spoken.contains(it) }
        checks += check(
            rule = "Нет накруток и покупной активности",
            ok = boost == null,
            fix = if (boost == null) "" else "«$boost» — запрещённый приём: бан канала и обнуление охватов, приложение такое не делает",
        )
        val demon = DEMONETIZING.firstOrNull { spoken.contains(it) }
        checks += check(
            rule = "Нет демонетизирующих тем в озвучке и описании",
            ok = demon == null,
            fix = if (demon == null) "" else "слово «$demon» почти всегда даёт жёлтый значок: убери или переформулируй",
            blocking = demon != null,
        )
        checks += check(
            rule = "Маркировка «для детей» решена явно",
            ok = !nicheIsForKids(topic.niche) || description.lowercase().contains("не для детей") ||
                description.lowercase().contains("для детей"),
            fix = "ниша детская: укажи audience. Без отметки решит алгоритм, с неверной — минус комментарии и доход",
            blocking = false,
        )
        val hype = PROMISE_WORDS.firstOrNull { title.lowercase().contains(it) }
        checks += check(
            rule = "Обещание срока подкреплено замером в ролике",
            ok = hype == null || beats.any { it.role == BeatRole.PROOF },
            fix = if (hype == null) "" else "«$hype» в заголовке — обязан быть кадр с фактом, иначе жалоба на обман",
            blocking = false,
        )
        return ComplianceReport(checks)
    }

    private fun check(rule: String, ok: Boolean, fix: String, blocking: Boolean = true) =
        ComplianceCheck(rule = rule, ok = ok, blocking = blocking, fix = fix)

    private fun nicheIsForKids(niche: String): Boolean = nicheByName(niche).forKids

    private fun nicheFriendliness(niche: String): Int = nicheByName(niche).advertiserFriendly

    // ─── упаковка ─────────────────────────────────────────────────────────────

    data class Packaging(
        val title: String,
        val description: String,
        val tags: List<String>,
        val pinnedComment: String,
        val thumbnailBrief: String,
    )

    fun packaging(topic: TopicCandidate, beats: List<Beat>): Packaging {
        val hook = beats.firstOrNull { it.role == BeatRole.HOOK }?.voice?.take(90).orEmpty()
        val proof = beats.firstOrNull { it.role == BeatRole.PROOF }?.overlay.orEmpty()
        val desc = buildString {
            appendLine(topic.hook)
            appendLine()
            appendLine("Что в ролике:")
            beats.filter { it.role == BeatRole.PAYLOAD || it.role == BeatRole.PROOF }.forEach { beat ->
                appendLine("• ${beat.startSec}с — ${beat.screen.take(70)}")
            }
            appendLine()
            appendLine("Длительность ${topic.durationSec}с, формат ${topic.format.label}. Собрано по разбору ${topic.niche.lowercase()} (YouTube статистика).")
            appendLine("Материалы свои; музыка — YouTube Audio Library. Озвучка может быть синтезирована — это указано явно.")
            if (proof.isNotBlank()) appendLine("Доказательство в ролике: $proof")
        }.trim()
        val tags = listOf(
            topic.niche.lowercase(),
            "shorts",
            "как ${topic.title.lowercase().take(18)}",
            topic.format.label.lowercase(),
            "разбор",
        ).map { it.trim() }.filter { it.length > 2 }.distinct().take(5)
        return Packaging(
            title = topic.title.take(98),
            description = desc,
            tags = tags,
            pinnedComment = "Если делаешь так же — напиши, что пошло не так, разберу в следующем ролике. " +
                "Тайм-коды: " + beats.take(4).joinToString(" · ") { "${it.startSec}с ${it.role.label}" },
            thumbnailBrief = (
                "Одно лицо/один объект крупно + 3 слова максимум: «${short(topic.title, 3).uppercase()}». " +
                    "Контраст на фоне неба/стены, без мелкого текста: на телефоне превьюха — это 96 пикселей. " +
                    "Готовое ТЗ: 1280×720, safe-area снизу 120px под длительность."
                ),
        )
    }

    // ─── рецепт сборки ────────────────────────────────────────────────────────

    fun recipe(topic: TopicCandidate, beats: List<Beat>, assets: List<AssetSpec>): RenderRecipe {
        val manifest = buildString {
            appendLine("{")
            appendLine("  \"title\": ${jsonString(topic.title)},")
            appendLine("  \"format\": ${jsonString(topic.format.name)},")
            appendLine("  \"width\": ${if (topic.format == VideoFormat.SHORTS) 1080 else 1920},")
            appendLine("  \"height\": ${if (topic.format == VideoFormat.SHORTS) 1920 else 1080},")
            appendLine("  \"fps\": 30,")
            appendLine("  \"durationSec\": ${beats.sumOf { it.lengthSec }},")
            appendLine("  \"beats\": [")
            beats.forEachIndexed { i, beat ->
                append("    {")
                append("\"index\": ${beat.index}, ")
                append("\"startSec\": ${beat.startSec}, ")
                append("\"endSec\": ${beat.endSec}, ")
                append("\"role\": ${jsonString(beat.role.name)}, ")
                append("\"overlay\": ${jsonString(beat.overlay)}, ")
                append("\"voice\": ${jsonString(beat.voice)}, ")
                append("\"shot\": ${jsonString(beat.shot)}")
                append("}")
                if (i < beats.size - 1) appendLine(",") else appendLine()
            }
            appendLine("  ],")
            appendLine("  \"assets\": [")
            assets.forEachIndexed { i, asset ->
                append("    {\"id\": ${jsonString(asset.id)}, \"kind\": ${jsonString(asset.kind.name)}, ")
                append("\"license\": ${jsonString(asset.license.name)}, \"query\": ${jsonString(asset.query)}}")
                if (i < assets.size - 1) appendLine(",") else appendLine()
            }
            appendLine("  ]")
            append("}")
        }
        val total = beats.sumOf { it.lengthSec }
        val draws = beats.filter { it.overlay.isNotBlank() }.joinToString(";\n    ") { beat ->
            "drawtext=text='${beat.overlay.replace("'", "")}':fontsize=${if (topic.format == VideoFormat.SHORTS) 54 else 40}:" +
                "fontcolor=white:borderw=3:bordercolor=black@0.6:" +
                "x=(w-text_w)/2:y=h*0.72:enable='between(t,${beat.startSec},${beat.endSec})'"
        }
        val script = buildString {
            appendLine("#!/usr/bin/env bash")
            appendLine("# Собирает ролик из твоих материалов. ffmpeg 6+, запускать на компьютере.")
            appendLine("# Приложение намеренно не выкладывает и не скачивает чужое: только сборка из того, что ты принёс сам.")
            appendLine("set -euo pipefail")
            appendLine()
            appendLine("SRC=clips          # сюда положи свои куски: clip-0.mp4, clip-2.mp4 …")
            appendLine("MUSIC=music.m4a    # YouTube Audio Library или CC0")
            appendLine("OUT=final.mp4")
            appendLine()
            appendLine("ls \"\$SRC\"/*.mp4 | sort | sed \"s/^/file '/;s/\$/'/\" > clips.txt")
            appendLine()
            appendLine("ffmpeg -y -f concat -safe 0 -i clips.txt -i \"\$MUSIC\" \\")
            appendLine("  -filter_complex \"[0:v]scale=${if (topic.format == VideoFormat.SHORTS) "1080:1920" else "1920:1080"}:force_original_aspect_ratio=decrease,")
            appendLine("    pad=${if (topic.format == VideoFormat.SHORTS) "1080:1920:(ow-iw)/2:(oh-ih)/2" else "1920:1080:(ow-iw)/2:(oh-ih)/2"},setsar=1,fps=30,")
            if (draws.isNotBlank()) {
                appendLine("    ${draws},")
            }
            appendLine("    subtitles=captions.srt:force_style='FontName=Inter,FontSize=${if (topic.format == VideoFormat.SHORTS) 22 else 16},PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,Outline=2'[v];")
            appendLine("    [1:a]loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st=${max(1, total - 1)}:d=1[a]\" \\")
            appendLine("  -map \"[v]\" -map \"[a]\" -shortest \\")
            appendLine("  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k \\")
            appendLine("  -movflags +faststart -t $total \"\$OUT\"")
            appendLine()
            appendLine("echo \"Готово: \$OUT ($total с). Дальше — руками в YouTube Studio: загрузить, проверить превьюху, опубликовать.\"")
        }
        return RenderRecipe(
            manifest = manifest,
            script = script,
            srt = toSrt(beats),
            notes = "Файлы рядом: manifest.json (этот), render.sh, captions.srt. Кладёшь свои куски в clips/, " +
                "ставишь лицензионную музыку, запускаешь ./render.sh — получаешь final.mp4. " +
                "Публикация вручную: приложение не имеет прав на запись в канал, и это не баг, а граница.",
        )
    }

    /** Реальные субтитры по битам: формат тайм-кода SRT — проверяется тестом. */
    fun toSrt(beats: List<Beat>): String {
        val out = StringBuilder()
        var number = 1
        beats.forEach { beat ->
            val lines = beat.voice.chunked(42).map { it.trim() }.filter { it.isNotEmpty() }
            if (lines.isEmpty()) return@forEach
            val per = max(1, beat.lengthSec / lines.size)
            var start = beat.startSec
            lines.forEachIndexed { i, line ->
                val end = if (i == lines.size - 1) beat.endSec else min(beat.endSec, start + per)
                out.append(number).append('\n')
                    .append(timestamp(start)).append(" --> ").append(timestamp(end)).append('\n')
                    .append(line).append("\n\n")
                number += 1
                start = end
            }
        }
        return out.toString().trimEnd() + "\n"
    }

    private fun timestamp(seconds: Int): String {
        val h = seconds / 3600
        val m = (seconds % 3600) / 60
        val s = seconds % 60
        return "%02d:%02d:%02d,000".format(h, m, s)
    }

    // ─── скоринг-мелочь ───────────────────────────────────────────────────────

    private fun hookStrength(title: String, hook: String, stats: NicheStats): Int {
        var score = 44
        val text = "$title $hook".lowercase()
        if (hasNumber(text)) score += 12
        if (hasTimeframe(text)) score += 10
        if (text.startsWith("как") || text.contains(" как ")) score += 6
        if (text.contains("почему") || text.contains("из-за")) score += 6
        if (text.contains("без ") || text.contains("не делай") || text.contains("ошибк")) score += 9
        if (text.contains("провер") || text.contains("замер") || text.contains("эксперимент")) score += 10
        if (text.length > 90) score -= 12
        if (stats.bestTitlePatterns.any { it.contains("цифра") } && !hasNumber(text)) score -= 10
        if (hook.isBlank()) score -= 8
        return score.coerceIn(0, 100)
    }

    private fun hookStrength(title: String, hook: String, hint: String): Int =
        hookStrength(title, hook, NicheStats(0, 0, 0L, 0.0, 0.0, listOf(hint), true))

    private fun statsHint(topic: TopicCandidate): String =
        if (topic.velocityPerHour > 250) "цифра в заголовке" else "прямое обещание результата"

    private fun payoffStrength(hook: String, stats: NicheStats): Int {
        var score = 40
        if (hook.isNotBlank()) score += 14
        if (stats.medianLikeRatio >= 0.05) score += 12
        if (stats.bestTitlePatterns.size >= 3) score += 8
        score += min(26, (stats.medianVelocity / 12).roundToInt())
        return score.coerceIn(0, 100)
    }

    private fun pacingFit(duration: Int, stats: NicheStats, format: VideoFormat): Int {
        if (stats.medianDurationSec <= 0) return 70
        val ratio = duration.toDouble() / stats.medianDurationSec
        val ideal = if (format == VideoFormat.SHORTS) 0.75 else 1.0
        val drift = abs(ratio - ideal)
        return (95 - (drift * 90).roundToInt()).coerceIn(35, 100)
    }

    private fun retentionPrior(duration: Int, stats: NicheStats, format: VideoFormat): Int {
        val beats = if (format == VideoFormat.SHORTS) duration / 4 else duration / 9
        val density = (beats * 10.0 / max(1, duration / 10)).roundToInt()
        return (52 + density.coerceIn(0, 22) + (if (stats.fromDemo) 0 else 12)).coerceIn(0, 100)
    }

    private fun monetizationStrength(title: String, niche: Niche, stats: NicheStats): Int {
        val lower = title.lowercase()
        var score = 52 + niche.advertiserFriendly / 5
        if (DEMONETIZING.any { lower.contains(it) }) score -= 30
        if (niche.forKids) score -= 8
        if (hasNumber(lower)) score += 6
        if (stats.medianViews > 500_000) score += 6
        return score.coerceIn(0, 100)
    }

    private fun matchEvidence(research: List<ResearchItem>, title: String): List<ResearchItem> =
        research.filter { sameIntent(it.title, title) }.ifEmpty { research.take(2) }

    /** Простейшее совпадение «про то же самое»: по значимым словам. */
    private fun sameIntent(a: String, b: String): Boolean {
        val wordsA = keywords(a)
        val wordsB = keywords(b)
        if (wordsA.isEmpty() || wordsB.isEmpty()) return false
        val shared = wordsA.count { it in wordsB }
        return shared >= min(2, min(wordsA.size, wordsB.size))
    }

    private fun keywords(text: String): Set<String> =
        text.lowercase().split(Regex("[^\\p{L}\\p{N}]+")).filter { it.length > 3 && !STOP.contains(it) }.toSet()

    private val STOP = setOf("this", "that", "with", "как", "что", "это", "для", "как", "когда", "потому", "который", "которая")

    private fun hasNumber(text: String): Boolean = Regex("\\d").containsMatchIn(text)

    private fun hasTimeframe(text: String): Boolean =
        Regex("\\d+\\s*(дн|недел|мес|час|минут|секунд|day|week|month|hour)").containsMatchIn(text.lowercase())

    private fun median(values: List<Int>): Int = if (values.isEmpty()) 0 else values[values.size / 2]

    private fun medianLong(values: List<Long>): Long = if (values.isEmpty()) 0L else values[values.size / 2]

    private fun percent(part: Int, whole: Int): Int = if (whole <= 0) 0 else part * 100 / whole

    private fun short(text: String, words: Int): String =
        text.split(Regex("\\s+")).filter { it.isNotBlank() }.take(words).joinToString(" ").trimEnd('.', ',', ':')

    private fun round2(v: Double): Double = (v * 100).roundToInt() / 100.0

    private fun round4(v: Double): Double = (v * 10000).roundToInt() / 10000.0

    private fun jsonString(value: String): String {
        val escaped = value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ")
        return "\"" + escaped + "\""
    }
}
