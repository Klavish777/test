package work.day.app.ui.tasks

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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import work.day.app.domain.engine.ShiftEngine
import work.day.app.domain.model.AgentTask
import work.day.app.domain.model.Artifact
import work.day.app.domain.model.PublishItem
import work.day.app.domain.model.PublishState
import work.day.app.domain.model.Risk
import work.day.app.domain.model.TaskStatus
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.EmptyHint
import work.day.app.ui.common.Panel
import work.day.app.ui.common.Pill
import work.day.app.ui.common.SectionHeader

private enum class Filter(val label: String) {
    APPROVAL("Ждут одобрения"),
    QUEUE("Очередь"),
    DONE("Сделано"),
    ALL("Все"),
}

@Composable
fun TasksScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val shift by vm.shift.collectAsStateWithLifecycle()
    var filter by rememberSaveable { mutableStateOf(Filter.APPROVAL) }
    var expandedArtifact by rememberSaveable { mutableStateOf<String?>(null) }

    val tasks = when (filter) {
        Filter.APPROVAL -> shift.tasks.filter { it.status == TaskStatus.NEEDS_APPROVAL }
        Filter.DONE -> shift.tasks.filter { it.status == TaskStatus.DONE || it.status == TaskStatus.QUEUED }
        Filter.QUEUE -> emptyList()
        Filter.ALL -> shift.tasks
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionHeader(
                "Очередь и одобрение",
                "Агент готовит материал, но публичное действие всегда подтверждаешь ты. Это не перестраховка: аккаунт твой, и бан за накрутку тоже твой.",
            )
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Filter.entries.forEach { f ->
                    val count = when (f) {
                        Filter.APPROVAL -> shift.pendingApproval
                        Filter.QUEUE -> shift.publishQueue.count { it.state == PublishState.READY }
                        Filter.DONE -> shift.doneTasks
                        Filter.ALL -> shift.plannedTasks
                    }
                    Pill(
                        text = "${f.label} $count",
                        color = Color(0xFF5B5CFF),
                        selected = filter == f,
                        onClick = { filter = f },
                    )
                }
            }
        }

        if (filter == Filter.QUEUE) {
            items(shift.publishQueue, key = { "pub-${it.id}" }) { item ->
                PublishRow(vm, item)
            }
            if (shift.publishQueue.isEmpty()) {
                item { EmptyHint("Очередь пуста. Одобри задачу во вкладке «Ждут одобрения» — пакет появится здесь.") }
            }
        } else {
            items(tasks, key = { "task-${it.id}" }) { task ->
                TaskRow(
                    vm = vm,
                    task = task,
                    artifact = shift.artifacts.firstOrNull { it.taskId == task.id },
                    expanded = expandedArtifact == task.id,
                    onExpand = { expandedArtifact = if (expandedArtifact == task.id) null else task.id },
                )
            }
            if (tasks.isEmpty()) {
                item {
                    EmptyHint(
                        when (filter) {
                            Filter.APPROVAL -> "Ничего не ждёт одобрения — смена идёт чисто."
                            Filter.DONE -> "Закрытых задач пока нет."
                            else -> "План пуст. Запусти смену на вкладке «Смена»."
                        }
                    )
                }
            }
        }
        item { Spacer(Modifier.height(40.dp)) }
    }
}

@Composable
private fun TaskRow(
    vm: WorkDayViewModel,
    task: AgentTask,
    artifact: Artifact?,
    expanded: Boolean,
    onExpand: () -> Unit,
) {
    val accent = Color(task.agent.accent)
    val riskColor = when (task.kind.risk) {
        Risk.LOW -> Color(0xFF4ADE80)
        Risk.MEDIUM -> Color(0xFFFFD23F)
        Risk.HIGH -> Color(0xFFFF5C7A)
    }
    Panel(border = accent.copy(alpha = 0.28f)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(task.agent.emoji)
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Text(task.kind.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    "${task.agent.codename} · слот ${ShiftEngine.clockLabel(task.slotMinutes)} · ${task.kind.effortMin} мин",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(task.status.label, style = MaterialTheme.typography.labelMedium, color = accent)
        }
        Spacer(Modifier.height(8.dp))
        Text(task.kind.what, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Pill("риск: ${task.kind.risk.label}", color = riskColor)
            Pill("метрика: ${task.kind.metric}", color = accent)
        }

        if (artifact != null) {
            Spacer(Modifier.height(10.dp))
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.background)
                    .clickable { onExpand() }
                    .padding(12.dp)
            ) {
                Text(
                    if (expanded) artifact.body else artifact.body.take(220) + if (artifact.body.length > 220) "…" else "",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    if (expanded) "свернуть" else "развернуть материал · ${artifact.source.label}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }

        if (task.status == TaskStatus.NEEDS_APPROVAL) {
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = { vm.approve(task.id) },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4ADE80), contentColor = Color(0xFF06231A)),
                ) { Text("Одобрить → в очередь") }
                OutlinedButton(onClick = { vm.skip(task.id) }) { Text("Пропустить") }
            }
        }
    }
}

@Composable
private fun PublishRow(vm: WorkDayViewModel, item: PublishItem) {
    val accent = Color(item.agent.accent)
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(34.dp)
                    .clip(RoundedCornerShape(11.dp))
                    .background(accent.copy(alpha = 0.16f)),
                contentAlignment = Alignment.Center,
            ) { Text(item.agent.emoji, style = MaterialTheme.typography.bodyLarge) }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    "${item.platform.label} · слот ${ShiftEngine.clockLabel(item.slotMinutes)} · ${item.state.label}",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (item.state == PublishState.PUBLISHED) Color(0xFF4ADE80) else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(10.dp))
        Box(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.background)
                .padding(12.dp)
        ) {
            Text(item.body, style = MaterialTheme.typography.bodyMedium, maxLines = 12)
        }
        if (item.state == PublishState.READY) {
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = { vm.markPublished(item.id) }) { Text("Опубликовал") }
                OutlinedButton(onClick = { vm.dropItem(item.id) }) { Text("Убрать") }
            }
            Text(
                "Скопируй текст в ${item.platform.studioName} — приложение не имеет прав на публикацию и не получает их.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline,
            )
        }
    }
}
