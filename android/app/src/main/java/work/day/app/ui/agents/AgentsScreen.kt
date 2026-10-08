package work.day.app.ui.agents

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import work.day.app.domain.agent.AgentRegistry
import work.day.app.domain.model.AgentConfig
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.Artifact
import work.day.app.domain.model.Autonomy
import work.day.app.domain.model.ModelSource
import work.day.app.domain.model.Playbook
import work.day.app.domain.model.Playbooks
import work.day.app.domain.model.TaskKind
import work.day.app.domain.model.TaskStatus
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.Panel
import work.day.app.ui.common.Pill
import work.day.app.ui.common.SectionHeader

@Composable
fun AgentsScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val workspace by vm.workspace.collectAsStateWithLifecycle()
    var expanded by rememberSaveable { mutableStateOf<String?>(null) }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionHeader(
                "Четыре агента",
                "Каждый отвечает за своё направление и ведёт смену 09:00–18:00. Интенсивность = сколько задач агент берёт в день.",
            )
        }

        AgentId.ordered.forEach { agentId ->
            val config = workspace.agents.firstOrNull { it.agent == agentId } ?: AgentConfig(agentId)
            item(key = "agent-card-${agentId.key}") {
                AgentCard(
                    vm = vm,
                    agentId = agentId,
                    config = config,
                    open = expanded == agentId.key,
                    onToggleOpen = { expanded = if (expanded == agentId.key) null else agentId.key },
                )
            }
            if (expanded == agentId.key) {
                item(key = "agent-detail-${agentId.key}") {
                    AgentDetail(vm, agentId)
                }
            }
        }

        item {
            Panel(background = MaterialTheme.colorScheme.surfaceVariant) {
                Text("Как читать оценку агента", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Оценка = сумма влияния закрытых задач (impact плейбука), а не «активность ради активности». " +
                        "100 из 100 означает, что агент успел прогнать всё включённое. Это не прогноз роста — " +
                        "реальную цену задач видно только через 7–14 дней по метрике, которую агент сам и называет.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun AgentCard(
    vm: WorkDayViewModel,
    agentId: AgentId,
    config: AgentConfig,
    open: Boolean,
    onToggleOpen: () -> Unit,
) {
    val accent = Color(agentId.accent)
    val playbooks = Playbooks.forAgent(agentId)
    val active = Playbooks.active(agentId, config.enabledPlaybooks)

    Panel(
        background = if (config.enabled) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.surface.copy(alpha = 0.5f),
        border = if (open) accent.copy(alpha = 0.6f) else Color.Transparent,
        modifier = Modifier.clickable { onToggleOpen() },
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(42.dp)
                    .clip(RoundedCornerShape(13.dp))
                    .background(accent.copy(alpha = 0.18f)),
                contentAlignment = Alignment.Center,
            ) { Text(agentId.emoji, style = MaterialTheme.typography.titleLarge) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(agentId.codename, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(agentId.direction, style = MaterialTheme.typography.bodySmall, color = accent)
                Text(agentId.mission, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(
                checked = config.enabled,
                onCheckedChange = { vm.setAgentEnabled(agentId, it) },
            )
        }

        Spacer(Modifier.height(10.dp))
        Text("KPI: ${agentId.kpi}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.height(10.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Autonomy.entries.forEach { autonomy ->
                Pill(
                    text = autonomy.label,
                    color = accent,
                    selected = config.autonomy == autonomy,
                    onClick = { vm.setAutonomy(agentId, autonomy) },
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(
            config.autonomy.description + if (config.autonomy == Autonomy.SCHEDULE) " Публикация всё равно за тобой." else "",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("интенсивность", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.width(8.dp))
            Slider(
                value = config.intensity.toFloat(),
                onValueChange = { vm.setIntensity(agentId, it.toInt()) },
                valueRange = 1f..5f,
                steps = 3,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            Text("${config.intensity}", style = MaterialTheme.typography.titleMedium, color = accent, modifier = Modifier.width(20.dp))
        }
        Text(
            "плейбуков включено: ${active.size} из ${playbooks.size} · задач в смену ≈ ${2 + config.intensity}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}

@Composable
private fun AgentDetail(vm: WorkDayViewModel, agentId: AgentId) {
    val workspace by vm.workspace.collectAsStateWithLifecycle()
    val config = workspace.agents.firstOrNull { it.agent == agentId } ?: AgentConfig(agentId)
    val accent = Color(agentId.accent)
    val tasks = workspace.tasks.filter { it.agent == agentId }.take(6)
    val artifacts = workspace.artifacts.filter { it.agent == agentId }.take(3)
    var selectedArtifact by remember { mutableStateOf<Artifact?>(null) }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Panel {
            Text("Плейбуки", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Playbooks.forAgent(agentId).forEach { playbook ->
                PlaybookRow(
                    playbook = playbook,
                    checked = config.enabledPlaybooks.isEmpty() || playbook.id in config.enabledPlaybooks,
                    accent = accent,
                    onToggle = { vm.togglePlaybook(agentId, playbook.id) },
                )
            }
        }

        Panel {
            Text(
                if (selectedArtifact == null) "Последние задачи смены" else "Материал: ${selectedArtifact?.kind?.title}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(8.dp))
            if (selectedArtifact != null) {
                val artifact = selectedArtifact!!
                Text(artifact.body, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill("источник: ${artifact.source.label}", color = if (artifact.source == ModelSource.OFFLINE) Color(0xFFFF8A3D) else accent, onClick = { selectedArtifact = null })
                    Text(
                        "платформы: ${artifact.platforms.joinToString(", ") { it.short }}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
            } else if (tasks.isEmpty()) {
                Text("Смену ещё не запускали — задач нет.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.outline)
            } else {
                tasks.forEach { task ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.background)
                            .clickable {
                                selectedArtifact = artifacts.firstOrNull { it.taskId == task.id }
                            }
                            .padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(task.kind.title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                            Text("цель: ${task.kind.metric}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                        }
                        Text(
                            task.status.label,
                            style = MaterialTheme.typography.labelMedium,
                            color = when (task.status) {
                                TaskStatus.NEEDS_APPROVAL -> Color(0xFFFFD23F)
                                TaskStatus.DONE, TaskStatus.QUEUED -> Color(0xFF4ADE80)
                                TaskStatus.FAILED -> Color(0xFFFF5C7A)
                                else -> MaterialTheme.colorScheme.onSurfaceVariant,
                            },
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                }
            }
        }
    }
}

@Composable
private fun PlaybookRow(playbook: Playbook, checked: Boolean, accent: Color, onToggle: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(18.dp)
                    .clip(RoundedCornerShape(5.dp))
                    .background(if (checked) accent else MaterialTheme.colorScheme.surfaceVariant)
                    .clickable { onToggle() }
            )
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(playbook.title, style = MaterialTheme.typography.bodyLarge)
                Text(playbook.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(playbook.cadence, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.outline)
        }
        Spacer(Modifier.height(4.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            playbook.kinds.forEach { kind: TaskKind ->
                Pill(kind.title, color = accent)
            }
        }
    }
}
