package work.day.app

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import work.day.app.data.llm.LlmClient
import work.day.app.data.llm.LlmResult
import work.day.app.data.llm.LlmSettings
import work.day.app.domain.agent.LlmBrief
import work.day.app.domain.agent.ViralEditor
import work.day.app.domain.engine.ViralLab
import work.day.app.domain.model.AssetKind
import work.day.app.domain.model.AssetLicense
import work.day.app.domain.model.AssetSpec
import work.day.app.domain.model.Beat
import work.day.app.domain.model.BeatRole
import work.day.app.domain.model.GenerationState
import work.day.app.domain.model.ResearchItem
import work.day.app.domain.model.TopicCandidate
import work.day.app.domain.model.VideoFormat

/**
 * Тесты «Генерации». Сюда попало только то, что обязано работать без сети и без ключей:
 * тайминги, арифметика балла, правки, проверка прав, разбор ответов YouTube.
 */
class ViralLabTest {

    private fun topic(
        format: VideoFormat = VideoFormat.SHORTS,
        duration: Int = 34,
        title: String = "3 приёма, которые экономят час на кухне",
    ) = TopicCandidate(
        title = title,
        niche = "Рецепты и кухня",
        hook = "Смотри: один приём — и плита чистая",
        why = "тест",
        format = format,
        durationSec = duration,
    )

    @Test
    fun `биты покрывают ролик без дыр и сумма равна заказанной длительности`() {
        VideoFormat.entries.forEach { format ->
            val edges = listOf(format.minSec, (format.minSec + format.maxSec) / 2, format.maxSec)
            val extra = if (format == VideoFormat.SHORTS) (format.minSec..format.maxSec).toList() else emptyList()
            (edges + extra).forEach { duration ->
                val beats = ViralLab.buildBeats(topic(format, duration))
                val sum = beats.sumOf { it.lengthSec }
                assertTrue("$format @ $duration: сумма битов $sum", sum == duration)
                var cursor = 0
                beats.forEach { beat ->
                    assertTrue("$format @ $duration: бит ${beat.index} начался с ${beat.startSec}", beat.startSec == cursor)
                    assertTrue("$format @ $duration: пустой бит", beat.lengthSec >= 1)
                    cursor = beat.endSec
                }
                assertTrue("$format @ $duration: первый бит — хук", beats.first().role == BeatRole.HOOK)
                assertTrue("$format @ $duration: есть доказательство", beats.any { it.role == BeatRole.PROOF })
            }
        }
    }

    @Test
    fun `длительность всегда в границах формата`() {
        val demo = ViralLab.statsOf(emptyList())
        val live = ViralLab.statsOf(List(6) { ResearchItem(videoId = "v$it", durationSec = 120, views = 900_000L) })
        VideoFormat.entries.forEach { format ->
            listOf(demo, live).forEach { stats ->
                val picked = ViralLab.pickDuration(format, stats)
                assertTrue(
                    "${format.name} @ $picked вне ${format.minSec}..${format.maxSec}",
                    picked in format.minSec..format.maxSec,
                )
            }
        }
        // явная просьба за границами форматируется, а не летит в ТЗ
        val forced = ViralLab.proposeTopics(
            niche = ViralLab.nicheByName("Рецепты и кухня"),
            research = emptyList(),
            format = VideoFormat.SHORTS,
            requestedDuration = 900,
        )
        assertTrue(forced.isNotEmpty())
        forced.forEach { assertTrue("демо-тема ${it.durationSec}с", it.durationSec in 20..58) }
    }

    @Test
    fun `темы отранжированы по баллу и их не больше шести`() {
        val research = List(9) { i ->
            ResearchItem(
                videoId = "v$i",
                title = "как ${ViralLab.nicheByName("Рецепты и кухня").query} за ${i + 1} минут",
                publishedAt = "2026-10-0${1 + i % 8}T08:00:00Z",
                views = 200_000L + i * 50_000L,
                likes = 9_000L + i * 300L,
                durationSec = 40 + i * 4,
            )
        }
        val topics = ViralLab.proposeTopics(
            niche = ViralLab.nicheByName("Рецепты и кухня"),
            research = research,
            format = VideoFormat.SHORTS,
        )
        assertTrue("тем ${topics.size}", topics.size in 1..6)
        topics.zip(topics.drop(1)).forEach { (a, b) ->
            assertTrue("${a.score.total} < ${b.score.total}", a.score.total >= b.score.total)
        }
        assertFalse("живая статистика не должна помечаться демо", topics.first().fromDemo)
        assertTrue(topics.first().evidence.isNotEmpty())
    }

    @Test
    fun `статистика ниже выборки не притворяется живую`() {
        val tiny = ViralLab.statsOf(listOf(ResearchItem(videoId = "x", views = 10L, durationSec = 30, publishedAt = "2026-10-01T08:00:00Z")))
        assertTrue("выборка 1 ролик не показатель", tiny.fromDemo)
        assertEquals(1, tiny.sample)
        val real = ViralLab.statsOf(List(4) { ResearchItem(videoId = "v$it", views = 100_000L * (it + 1), durationSec = 30 + it, publishedAt = "2026-10-01T08:00:00Z") })
        assertFalse(real.fromDemo)
        assertEquals(4, real.sample)
        assertTrue(real.medianDurationSec in 30..33)
    }

    @Test
    fun `правки монтажёра никогда не понижают балл и всегда объясняются`() {
        val t = topic()
        val full = ViralLab.buildBeats(t)
        val assetsFull = ViralLab.assetsFor(t, full)
        val beforeFull = ViralLab.critique(full, t, assetsFull)
        val passFull = ViralLab.editPass(full, t, assetsFull)
        val beatsFull = passFull.first.first
        val assetsAfter = passFull.first.second
        val editsFull = passFull.second
        val afterFull = ViralLab.critique(beatsFull, t, assetsAfter)
        assertTrue("полный скелет: ${beforeFull.total} → ${afterFull.total}", afterFull.total >= beforeFull.total)
        assertEquals("правки не ломают тайминги", t.durationSec, beatsFull.sumOf { it.lengthSec })
        editsFull.forEach { edit ->
            assertTrue("правка без объяснения: ${edit.action}", edit.action.isNotBlank() && edit.reason.isNotBlank())
            assertTrue("правка с нулевой ценой", edit.delta > 0)
        }

        // намеренно слабый скелет: один план длинный, ни хука, ни доказательства, ни субтитров
        val weak = listOf(
            Beat(index = 0, startSec = 0, endSec = 40, role = BeatRole.PAYLOAD, voice = "долгий рассказ без монтажа", screen = "один план"),
        )
        val beforeWeak = ViralLab.critique(weak, t, emptyList())
        val passWeak = ViralLab.editPass(weak, t, emptyList())
        val beatsWeak = passWeak.first.first
        val assetsWeak = passWeak.first.second
        val editsWeak = passWeak.second
        val afterWeak = ViralLab.critique(beatsWeak, t, assetsWeak)
        assertTrue("слабый скелет обязан расти: ${beforeWeak.total} → ${afterWeak.total}", afterWeak.total > beforeWeak.total)
        assertTrue("монтажёр не должен молчать", editsWeak.isNotEmpty())
        assertTrue("субтитры добавлены", assetsWeak.any { it.kind == AssetKind.CAPTIONS })
        assertTrue("доказательство появилось", beatsWeak.any { it.role == BeatRole.PROOF })
    }

    @Test
    fun `чистый пакет допускается, чужая музыка и накрутки блокируют`() {
        val t = topic()
        val safe = listOf(
            Beat(index = 0, startSec = 0, endSec = 3, role = BeatRole.HOOK, voice = "смотри: один приём", overlay = "0:00", screen = "крупно"),
            Beat(index = 1, startSec = 3, endSec = 14, role = BeatRole.PAYLOAD, voice = "делаешь так и плита чистая", overlay = "шаг 1", screen = "руки в кадре"),
            Beat(index = 2, startSec = 14, endSec = 20, role = BeatRole.PROOF, voice = "замер: было 12 минут, стало 4", overlay = "12→4", screen = "скрин с цифрой"),
        )
        val own = listOf(
            AssetSpec("clip-1", AssetKind.OWN_CLIP, AssetLicense.OWN, "свои съёмки"),
            AssetSpec("music", AssetKind.MUSIC, AssetLicense.YT_AUDIO_LIBRARY, "Audio Library"),
            AssetSpec("captions", AssetKind.CAPTIONS, AssetLicense.OWN, "captions.srt"),
        )
        val clean = ViralLab.compliance(t, safe, own, title = t.title, description = "Разбор приёма. Озвучка своя.")
        assertTrue(clean.checks.joinToString(" | ") { "${it.rule}=${it.ok}/${it.fix}" }, clean.allowedToPublish)

        val stolenMusic = ViralLab.compliance(
            t, safe, own + AssetSpec("music-2", AssetKind.MUSIC, AssetLicense.NEEDS_PERMISSION, "популярный трек из чарта"),
            title = t.title,
        )
        assertFalse("чужой трек не пропускает монетизацию", stolenMusic.allowedToPublish)
        assertTrue(stolenMusic.blockers.any { it.fix.contains("Audio Library") })

        val repost = ViralLab.compliance(
            t, safe, own + AssetSpec("clip-x", AssetKind.OWN_CLIP, AssetLicense.REPOSTED, "ролик целиком у другого автора"),
            title = t.title,
        )
        assertFalse(repost.allowedToPublish)

        val boosting = ViralLab.compliance(
            t,
            safe + Beat(index = 3, startSec = 20, endSec = 25, role = BeatRole.CTA, voice = "накрутка просмотров поможет залететь", overlay = "лайк"),
            own,
            title = t.title,
        )
        assertFalse("накрутку не пропустим никогда", boosting.allowedToPublish)
        assertTrue(boosting.blockers.any { it.rule.contains("накруток", ignoreCase = true) })
    }

    @Test
    fun `субтитры собираются по формату srt`() {
        val beats = listOf(
            Beat(index = 0, startSec = 0, endSec = 3, role = BeatRole.HOOK, voice = "раз"),
            Beat(index = 1, startSec = 3, endSec = 11, role = BeatRole.PAYLOAD, voice = ""),
            Beat(index = 2, startSec = 11, endSec = 15, role = BeatRole.PROOF, voice = "два"),
        )
        val srt = ViralLab.toSrt(beats)
        val blocks = srt.trimEnd().split("\n\n")
        assertEquals("пустой бит в субтитры не попадает", 2, blocks.size)
        val pattern = Regex("""^\d+\n\d{2}:\d{2}:\d{2},000 --> \d{2}:\d{2}:\d{2},000\n.+$""", RegexOption.DOT_MATCHES_ALL)
        blocks.forEach { block -> assertTrue("блок не по формату: «$block»", pattern.matches(block)) }
        assertTrue(blocks.first().startsWith("1\n00:00:00,000 --> 00:00:03,000"))
        assertTrue("нумерация сквозная", blocks[1].startsWith("2\n"))
    }

    @Test
    fun `разбор ответов youtube — длительность, дата и скорость`() {
        assertEquals(3723, ResearchItem.parseDuration("PT1H2M3S"))
        assertEquals(37, ResearchItem.parseDuration("PT37S"))
        assertEquals(240, ResearchItem.parseDuration("PT4M"))
        assertEquals(0, ResearchItem.parseDuration(""))
        assertEquals(0, ResearchItem.parseDuration("4M12S"))

        assertEquals(0L, ResearchItem.epochDays(1970, 1, 1))
        // 2000-02-29 — последний день високосного века, удобная проверка календаря
        assertEquals(11017L, ResearchItem.epochDays(2000, 3, 1))
        val epoch = ResearchItem.parseIsoEpoch("2026-10-01T08:00:00Z")
        assertNotNull(epoch)
        assertEquals(ResearchItem.epochDays(2026, 10, 1) * 86_400_000L + 8L * 3_600_000L, epoch!!)
        assertNull(ResearchItem.parseIsoEpoch("давно"))
        assertNull(ResearchItem.parseIsoEpoch(""))

        val twoHoursAgo = System.currentTimeMillis() - 2L * 3_600_000L
        val iso = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US).apply {
            timeZone = java.util.TimeZone.getTimeZone("UTC")
        }.format(java.util.Date(twoHoursAgo))
        val fresh = ResearchItem(videoId = "v", title = "x", publishedAt = iso, views = 240L)
        assertTrue("просмотры/час считаются от публикации", fresh.velocityPerHour in 100.0..125.0)
        assertEquals(0.05, ResearchItem(videoId = "v", views = 1000L, likes = 50L).likeRatio, 1e-9)
    }

    @Test
    fun `рецепт отдаёт валидный манифест ffmpeg и субтитры`() {
        val t = topic()
        val beats = ViralLab.buildBeats(t)
        val assets = ViralLab.assetsFor(t, beats)
        val recipe = ViralLab.recipe(t, beats, assets)
        val root = Json.parseToJsonElement(recipe.manifest).jsonObject
        assertEquals(t.title, root["title"]?.jsonPrimitive?.content)
        assertEquals(1080, root["width"]?.jsonPrimitive?.int)
        assertEquals(1920, root["height"]?.jsonPrimitive?.int)
        assertEquals(beats.size, root["beats"]?.jsonArray?.size)
        assertEquals(beats.sumOf { it.lengthSec }, root["durationSec"]?.jsonPrimitive?.int)
        root["beats"]!!.jsonArray.forEach { beat ->
            val obj = beat.jsonObject
            assertTrue(obj.containsKey("startSec") && obj.containsKey("overlay") && obj.containsKey("voice"))
        }
        assertTrue(recipe.script.startsWith("#!/usr/bin/env bash"))
        assertTrue(recipe.script.contains("ffmpeg"))
        // сборка не должна скачивать чужое — это принцип продукта
        assertFalse(recipe.script.contains("yt-dlp"))
        assertFalse(recipe.script.contains("curl "))
        assertTrue(recipe.srt.contains("-->"))
    }

    @Test
    fun `кэш статистики нишы протухает`() {
        val item = ResearchItem(videoId = "v", title = "x", views = 10L, durationSec = 30)
        val fresh = GenerationState(research = listOf(item), researchAt = System.currentTimeMillis())
        assertTrue(fresh.researchFresh)
        val stale = GenerationState(research = listOf(item), researchAt = System.currentTimeMillis() - GenerationState.RESEARCH_TTL_MS - 5_000L)
        assertFalse(stale.researchFresh)
        assertFalse(GenerationState(research = emptyList(), researchAt = System.currentTimeMillis()).researchFresh)
    }

    @Test
    fun `агент молчит без ключа модели и не выдумывает статистику`() = runTest {
        val calls = ArrayList<LlmBrief>()
        val llm = object : LlmClient {
            override val source = LlmClient.Source.OFFLINE
            override suspend fun complete(brief: LlmBrief): LlmResult {
                calls += brief
                return LlmResult(text = "Заголовок | Хук | Почему", source = source)
            }
        }
        val offline = LlmSettings(enabled = false, apiKey = "")
        val topics = ViralEditor.topics(
            settings = offline,
            llm = llm,
            niche = ViralLab.nicheByName("Фитнес и тело"),
            format = VideoFormat.SHORTS,
            durationSec = 32,
            stats = ViralLab.statsOf(emptyList()),
            audience = "новички",
        )
        assertTrue("без ключа модель дёргать нельзя", topics.isEmpty() && calls.isEmpty())

        val beats = ViralLab.buildBeats(topic(VideoFormat.SHORTS, 30))
        val same = ViralEditor.voice(offline, llm, topic(VideoFormat.SHORTS, 30), beats)
        assertEquals("без модели озвучка остаётся шаблонной", beats, same)

        val usable = LlmSettings(enabled = true, apiKey = "sk-test", model = "gpt-4o-mini")
        val parsed = ViralEditor.topics(
            settings = usable,
            llm = llm,
            niche = ViralLab.nicheByName("Фитнес и тело"),
            format = VideoFormat.SHORTS,
            durationSec = 32,
            stats = ViralLab.statsOf(emptyList()),
            audience = "новички",
        )
        assertEquals(1, calls.size)
        assertTrue("строки модели идут в движок как есть", parsed.size == 1 && parsed.first().contains("|"))
        // правила агента — часть продукта: их видит человек перед тем, как доверить ролику канал
        assertTrue(ViralEditor.RULES.any { it.contains("чужие ролики") })
        assertTrue(ViralEditor.RULES.all { it.startsWith("не ") })
    }
}
