package work.day.app.ui.growth

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlin.math.max
import work.day.app.domain.model.DailyMetrics
import work.day.app.domain.model.Platform
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.Panel
import work.day.app.ui.common.Pill
import work.day.app.ui.common.ProgressBar
import work.day.app.ui.common.SectionHeader
import work.day.app.ui.common.StatTile

private enum class ChartMetric(val label: String, val unit: String) {
    SUBS("Подписчики", "чел."),
    VIEWS("Просмотры", ""),
    RETENTION("Удержание", "%"),
    ENGAGEMENT("Вовлечённость", "%"),
    NEW("Новая аудитория", "%"),
}

@Composable
fun GrowthScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val shift by vm.shift.collectAsStateWithLifecycle()
    var metric by remember { mutableStateOf(ChartMetric.SUBS) }
    var platform by remember { mutableStateOf(Platform.YOUTUBE) }
    var csv by remember { mutableStateOf("") }

    val all = shift.metrics
    val series = all.filter { it.platform == platform }
    val last = series.lastOrNull()
    val prev = series.getOrNull(series.lastIndex - 7)
    val goals = runCatching { vm.workspace.value.goals }.getOrNull()

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionHeader(
                "Прирост",
                if (series.size < 14) "Мало импортированных данных — часть графика из демо-режима. Вставь CSV ниже, чтобы видеть своё."
                else "Последние ${series.size} дней · ${platform.label}",
            )
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Platform.entries.forEach { p ->
                    Pill(
                        text = p.label,
                        color = Color(0xFF5B5CFF),
                        selected = platform == p,
                        onClick = { platform = p },
                    )
                }
            }
        }

        item {
            Panel {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ChartMetric.entries.forEach { m ->
                        Pill(text = m.label, color = Color(0xFF12B886), selected = metric == m, onClick = { metric = m })
                    }
                }
                Spacer(Modifier.height(14.dp))
                GrowthChart(
                    values = series.map { value(it, metric) },
                    labels = series.map { it.date.takeLast(5) },
                    color = Color(metricColor(metric)),
                    modifier = Modifier.fillMaxWidth().height(150.dp),
                )
                Spacer(Modifier.height(8.dp))
                val first = series.firstOrNull()?.let { value(it, metric) } ?: 0.0
                val current = last?.let { value(it, metric) } ?: 0.0
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("${format(current, metric)} ${metric.unit}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(
                        "за период ${format(current - first, metric)} ${metric.unit}",
                        style = MaterialTheme.typography.bodySmall,
                        color = if (current >= first) Color(0xFF4ADE80) else Color(0xFFFF5C7A),
                    )
                }
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                StatTile("подписчиков", formatNumber(last?.let { metricOf(it, ChartMetric.SUBS) } ?: 0.0))
                StatTile("просмотров", formatNumber(last?.let { metricOf(it, ChartMetric.VIEWS) } ?: 0.0))
                StatTile("ER", "${last?.engagementPct?.let { "%.1f".format(it) } ?: "0"}%", caption = "лайки+комменты+репосты")
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                StatTile("удержание", "${last?.retentionPct ?: 0}%")
                StatTile("новая ауд.", "${last?.newAudiencePct ?: 0}%")
                StatTile("CTR", "${last?.ctrPct ?: 0}%")
            }
        }

        if (prev != null && last != null) {
            item {
                Panel(background = MaterialTheme.colorScheme.surfaceVariant) {
                    Text("Неделя к неделе", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    DeltaRow("просмотры", last.views.toDouble(), prev.views.toDouble(), "")
                    DeltaRow("подписчики", last.subscribers.toDouble(), prev.subscribers.toDouble(), "")
                    DeltaRow("комментарии", last.comments.toDouble(), prev.comments.toDouble(), "")
                    DeltaRow("удержание", last.retentionPct, prev.retentionPct, "%")
                }
            }
        }

        item {
            Panel {
                Text("Цели Work Day", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                GoalRow("Новые подписчики / нед", 128.0, (goals?.newSubscribersPerWeek ?: 350).toDouble(), Color(0xFF5B5CFF))
                GoalRow("Задач закрыто сегодня", shift.doneTasks.toDouble(), shift.plannedTasks.coerceAtLeast(1).toDouble(), Color(0xFF12B886))
                GoalRow("На одобрении", (shift.pendingApproval == 0).toDouble(), 1.0, Color(0xFFFFD23F))
                GoalRow("Удержание", last?.retentionPct ?: 0.0, goals?.retentionPct ?: 45.0, Color(0xFFFF8A3D))
                Text(
                    "Цели заданы автору, а не алгоритму: агент подстраивает план смены под них, но не обещает, что они будут достигнуты.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }

        item {
            Panel {
                Text("Свои цифры вместо демо", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text(
                    "YouTube Studio → Аналитика → «Скачать CSV»; TikTok Studio → Analytics → Export. " +
                        "Формат строки: дата,площадка,просмотры,подписчики,удержание,лайки,комментарии,репосты",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = csv,
                    onValueChange = { csv = it },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    placeholder = { Text("2026-10-01,YouTube,5210,18420,44,153,17,4", style = MaterialTheme.typography.bodySmall) },
                )
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = { vm.importMetrics(csv) }, enabled = csv.isNotBlank()) { Text("Импортировать") }
                    Button(onClick = { vm.connectYoutube() }) { Text("Подтянуть YouTube API") }
                }
            }
        }
        item { Spacer(Modifier.height(40.dp)) }
    }
}

@Composable
private fun GrowthChart(values: List<Double>, labels: List<String>, color: Color, modifier: Modifier = Modifier) {
    Column(modifier = modifier.fillMaxWidth()) {
      Box(Modifier.fillMaxWidth().weight(1f)) {
        Canvas(Modifier.fillMaxSize()) {
            if (values.size < 2) return@Canvas
            val minV = values.min()
            val maxV = max(values.max(), minV + 1.0)
            val stepX = size.width / (values.size - 1)
            val path = Path()
            val fill = Path()
            values.forEachIndexed { i, v ->
                val x = stepX * i
                val y = size.height - (size.height * ((v - minV) / (maxV - minV)).toFloat())
                if (i == 0) {
                    path.moveTo(x, y)
                    fill.moveTo(x, size.height)
                    fill.lineTo(x, y)
                } else {
                    path.lineTo(x, y)
                    fill.lineTo(x, y)
                }
            }
            fill.lineTo(size.width, size.height)
            fill.close()
            drawPath(fill, color.copy(alpha = 0.16f))
            drawPath(path, color, style = androidx.compose.ui.graphics.drawscope.Stroke(width = 3f, cap = StrokeCap.Round))
            // сетка
            for (i in 1..3) {
                val y = size.height * i / 4f
                drawLine(color.copy(alpha = 0.10f), Offset(0f, y), Offset(size.width, y), 1f)
            }
        }
      }
      Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(labels.firstOrNull().orEmpty(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
            Text(labels.lastOrNull().orEmpty(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
private fun DeltaRow(label: String, now: Double, before: Double, unit: String) {
    val delta = if (before == 0.0) 0.0 else (now - before) / before * 100.0
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        Text(formatNumber(now) + unit, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
        Spacer(Modifier.width(10.dp))
        Text(
            "%+.1f%%".format(delta),
            style = MaterialTheme.typography.labelMedium,
            color = if (delta >= 0) Color(0xFF4ADE80) else Color(0xFFFF5C7A),
            modifier = Modifier.width(64.dp),
        )
    }
}

@Composable
private fun GoalRow(label: String, current: Double, target: Double, color: Color) {
    val progress = if (target <= 0) 0f else (current / target).toFloat().coerceIn(0f, 1f)
    Column(Modifier.padding(vertical = 6.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            Text("${formatNumber(current)} / ${formatNumber(target)}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(6.dp))
        ProgressBar(progress, color)
    }
}

private fun metricOf(m: DailyMetrics, metric: ChartMetric): Double = value(m, metric)

private fun value(m: DailyMetrics, metric: ChartMetric): Double = when (metric) {
    ChartMetric.SUBS -> m.subscribers.toDouble()
    ChartMetric.VIEWS -> m.views.toDouble()
    ChartMetric.RETENTION -> m.retentionPct
    ChartMetric.ENGAGEMENT -> m.engagementPct
    ChartMetric.NEW -> m.newAudiencePct
}

private fun metricColor(metric: ChartMetric): Long = when (metric) {
    ChartMetric.SUBS -> 0xFF5B5CFF
    ChartMetric.VIEWS -> 0xFF12B886
    ChartMetric.RETENTION -> 0xFFFF8A3D
    ChartMetric.ENGAGEMENT -> 0xFFFFD23F
    ChartMetric.NEW -> 0xFF4ADE80
}

private fun format(v: Double, metric: ChartMetric): String =
    if (metric.unit == "%") "%.1f".format(v) else formatNumber(v)

private fun formatNumber(v: Double): String = when {
    v >= 1_000_000 -> "%.2fM".format(v / 1_000_000)
    v >= 1_000 -> "%.1fk".format(v / 1_000)
    else -> v.toInt().toString()
}

private fun formatNumber(v: Long): String = formatNumber(v.toDouble())
