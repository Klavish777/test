package work.day.app.ui.shift

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import work.day.app.domain.engine.ShiftEngine
import work.day.app.domain.engine.ShiftPhase
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.EventKind
import work.day.app.domain.model.TaskStatus
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.Panel
import work.day.app.ui.common.Pill
import work.day.app.ui.common.ProgressBar
import work.day.app.ui.common.SectionHeader
import work.day.app.ui.common.StatTile

@Composable
fun ShiftScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val shift by vm.shift.collectAsStateWithLifecycle()

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Panel(background = MaterialTheme.colorScheme.surfaceVariant) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Work Day", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text(
                            "${shift.day.ifBlank { "смена не назначена" }} · ${shift.phase.label} · ${clock(shift.clock)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Box(
                        Modifier
                            .size(44.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(if (shift.phase == ShiftPhase.WORKING) Color(0x334ADE80) else Color(0x22FFFFFF)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            if (shift.phase == ShiftPhase.WORKING) "●" else "○",
                            color = if (shift.phase == ShiftPhase.WORKING) Color(0xFF4ADE80) else MaterialTheme.colorScheme.outline,
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))
                ProgressBar(shift.shiftProgress, color = VioletAccent, track = Color(0x22FFFFFF))
                Spacer(Modifier.height(6.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(clock(ShiftEngine.SHIFT_START), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                    Text("рабочий день ${shift.shiftProgress.times(100).toInt()}%", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(clock(ShiftEngine.SHIFT_END), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                }

                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    val running = shift.phase == ShiftPhase.WORKING
                    Button(
                        onClick = { vm.startShift() },
                        enabled = !running,
                        colors = ButtonDefaults.buttonColors(containerColor = VioletAccent),
                    ) { Text(if (shift.phase == ShiftPhase.PAUSED) "Продолжить" else "Начать смену") }
                    OutlinedButton(onClick = { vm.pauseShift() }, enabled = running) { Text("Пауза") }
                    OutlinedButton(onClick = { vm.stopShift() }, enabled = shift.phase != ShiftPhase.IDLE) { Text("Стоп") }
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("темп", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    listOf(1, 2, 4, 8).forEach { s ->
                        Pill("${s}×", color = VioletAccent, selected = shift.speed == s, onClick = { vm.setSpeed(s) })
                    }
                }
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                StatTile("задач", "${shift.doneTasks}/${shift.plannedTasks}")
                StatTile("одобрение", "${shift.pendingApproval}", valueColor = if (shift.pendingApproval > 0) SunAccent else MaterialTheme.colorScheme.onBackground)
                StatTile("материалы", "${shift.artifacts.size}")
                StatTile("очередь", "${shift.publishQueue.size}", valueColor = MintAccent)
            }
        }

        item { SectionHeader("Агенты в смене", "Каждый ведёт свои задачи и сам решает, что делать следующим") }

        items(AgentId.ordered, key = { "agent-${it.key}" }) { agent ->
            AgentRuntimeRow(vm, agent)
        }

        item {
            SectionHeader(
                "Лента смены",
                if (shift.events.isEmpty()) "нажми «Начать смену» — здесь появится, что делают агенты"
                else "${shift.events.size} записей за день",
            )
        }

        items(shift.events.take(40), key = { "ev-${it.at}-${it.hashCode()}" }) { event ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.Top,
            ) {
                Text(event.clock, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline, modifier = Modifier.width(44.dp))
                Spacer(Modifier.width(8.dp))
                Text(
                    event.agent?.emoji ?: "•",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(event.agent?.accent ?: 0xFF9AA4BF),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    event.text,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (event.kind == EventKind.NEED_APPROVAL) SunAccent else MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.weight(1f, fill = false),
                )
            }
        }

        item {
            Spacer(Modifier.height(40.dp))
            Text(
                "Агенты не публикуют и не накручивают активность. Всё публичное проходит через тебя.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline,
            )
        }
    }
}

@Composable
private fun AgentRuntimeRow(vm: WorkDayViewModel, agent: AgentId) {
    val shift by vm.shift.collectAsStateWithLifecycle()
    val runtime = shift.agent(agent)
    val tasks = shift.tasks.filter { it.agent == agent }
    val accent = Color(agent.accent)
    val current = tasks.firstOrNull { it.status == TaskStatus.RUNNING }

    Panel(
        background = MaterialTheme.colorScheme.surface,
        border = if (runtime.busy) accent.copy(alpha = 0.5f) else Color.Transparent,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(38.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(accent.copy(alpha = 0.18f)),
                contentAlignment = Alignment.Center,
            ) { Text(agent.emoji) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(agent.codename, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(agent.direction, style = MaterialTheme.typography.bodySmall, color = accent)
            }
            Text(
                if (runtime.busy) "работает" else if (runtime.tasksDone + runtime.waiting > 0) "готово" else "ждёт",
                style = MaterialTheme.typography.labelMedium,
                color = if (runtime.busy) accent else MaterialTheme.colorScheme.outline,
            )
        }

        Spacer(Modifier.height(10.dp))
        Text(
            current?.let { "«${it.kind.title}» · ${it.kind.what}" } ?: runtime.message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(8.dp))
        ProgressBar(runtime.progress, color = accent)
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("закрыто ${runtime.tasksDone}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
            Text("на одобрении ${runtime.waiting}", style = MaterialTheme.typography.bodySmall, color = if (runtime.waiting > 0) SunAccent else MaterialTheme.colorScheme.outline)
            Text("материалов ${runtime.artifacts}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
        if (runtime.lastOutput.isNotBlank()) {
            Spacer(Modifier.height(10.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.background)
                    .padding(10.dp)
            ) {
                Text(
                    runtime.lastOutput,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

private fun clock(minutes: Int): String = ShiftEngine.clockLabel(minutes)

private val VioletAccent = Color(0xFF5B5CFF)
private val MintAccent = Color(0xFF12B886)
private val SunAccent = Color(0xFFFFD23F)
