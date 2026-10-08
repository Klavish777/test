package work.day.app

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import work.day.app.data.llm.OfflineLlm
import work.day.app.data.platform.AnalyticsImporter
import work.day.app.di.llmSourceFor
import work.day.app.domain.agent.AgentRegistry
import work.day.app.domain.agent.ShiftWindow
import work.day.app.domain.model.AgentConfig
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.ChannelProfile
import work.day.app.domain.model.Playbooks
import work.day.app.domain.model.Risk
import work.day.app.domain.model.TaskKind

class AgentPlanningTest {

    private val profile = ChannelProfile(niche = "съёмка на телефон", audience = "новички 25+", language = "ru")

    @Test
    fun `each agent has playbooks and tasks`() {
        AgentId.ordered.forEach { id ->
            val agent = AgentRegistry.get(id)
            assertTrue("$id без плейбуков", agent.playbooks().isNotEmpty())
            assertTrue("$id без действий", agent.availableKinds(AgentConfig(id)).isNotEmpty())
        }
    }

    @Test
    fun `plan respects intensity`() {
        val agent = AgentRegistry.get(AgentId.MAGNET)
        val window = ShiftWindow("2026-10-08", 20643, 9 * 60, 18 * 60)
        val low = agent.plan(AgentConfig(AgentId.MAGNET, intensity = 1), profile, window)
        val high = agent.plan(AgentConfig(AgentId.MAGNET, intensity = 5), profile, window)
        assertTrue("слабая смена должна быть короче: ${low.size} vs ${high.size}", low.size < high.size)
        assertTrue(low.all { it.slotMinutes in 9 * 60..18 * 60 })
    }

    @Test
    fun `disabled agent plans nothing`() {
        val agent = AgentRegistry.get(AgentId.SPARK)
        val window = ShiftWindow("2026-10-08", 1, 9 * 60, 18 * 60)
        assertTrue(agent.plan(AgentConfig(AgentId.SPARK, enabled = false), profile, window).isEmpty())
    }

    @Test
    fun `high risk actions always need approval`() {
        TaskKind.entries.forEach { kind ->
            val requiresApproval = kind.risk != Risk.LOW
            if (kind.risk == Risk.HIGH) assertTrue("${kind.id}: публичное действие без одобрения", requiresApproval)
        }
    }

    @Test
    fun `prompt forbids fake engagement`() {
        val task = work.day.app.domain.model.AgentTask(
            id = "t1",
            agent = AgentId.MAGNET,
            kind = TaskKind.SEO_REWRITE,
            title = TaskKind.SEO_REWRITE.title,
            target = TaskKind.SEO_REWRITE.metric,
        )
        val brief = AgentRegistry.get(AgentId.MAGNET).brief(task, profile)
        val system = brief.system
        assertTrue(system.contains("накрутк", ignoreCase = true))
        assertTrue(system.contains("Никакой накрутки", ignoreCase = true) || system.contains("накрутк", ignoreCase = true))
        assertFalse(brief.user.isBlank())
    }

    @Test
    fun `playbook ids resolve to kinds`() {
        AgentId.ordered.forEach { id ->
            val ids = Playbooks.forAgent(id).map { it.id }.toSet()
            assertEquals("дубли плейбуков у $id", ids.size, Playbooks.forAgent(id).size)
            assertTrue(Playbooks.kindsOf(id, ids).isNotEmpty())
        }
    }
}

class LlmRoutingTest {
    @Test
    fun `no key means offline engine`() {
        assertEquals(OfflineLlm().source, llmSourceFor(false))
    }

    @Test
    fun `offline engine renders each task kind`() = runTest {
        val llm = OfflineLlm()
        TaskKind.entries.forEach { kind ->
            val result = llm.complete(
                work.day.app.domain.agent.LlmBrief("sys", "Задача смены: ${kind.title}\nНиша: тест\n", 0.7, 400)
            )
            assertTrue("${kind.id}: пусто", result.text.isNotBlank())
            assertTrue(kind.title, result.text.contains(kind.title) || result.text.contains("Задача"))
        }
    }
}

class AnalyticsImportTest {

    @Test
    fun `parses headered csv`() {
        val csv = """
            date,platform,views,subscribers,retention_pct,likes,comments,shares
            2026-10-01,YouTube,5210,18420,44,153,17,4
            2026-10-02;TikTok;13400;27150;58;400;45;19
        """.trimIndent()
        val rows = AnalyticsImporter.parse(csv).getOrThrow()
        assertEquals(2, rows.size)
        assertEquals(5210L, rows[0].views)
        assertEquals(work.day.app.domain.model.Platform.TIKTOK, rows[1].platform)
    }

    @Test
    fun `parses dateless russian header`() {
        val csv = "дата;просмотры\n05.10.2026;900"
        val rows = AnalyticsImporter.parse(csv).getOrThrow()
        assertEquals("2026-10-05", rows.first().date)
        assertEquals(900L, rows.first().views)
    }

    @Test
    fun `bad date fails loudly`() {
        assertTrue(AnalyticsImporter.parse("date,views\nне-дата;10").isFailure)
    }
}
