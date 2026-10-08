package work.day.app.ui.generation

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import work.day.app.domain.agent.ViralEditor
import work.day.app.domain.model.Beat
import work.day.app.domain.model.GenerationPlan
import work.day.app.domain.model.TopicCandidate
import work.day.app.domain.model.VideoFormat
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.EmptyHint
import work.day.app.ui.common.LabeledField
import work.day.app.ui.common.Panel
import work.day.app.ui.common.Pill
import work.day.app.ui.common.ProgressBar
import work.day.app.ui.common.SectionHeader

private val ACCENT = Color(0xFFFF7A45)
private val OK = Color(0xFF4ADE80)
private val BAD = Color(0xFFFF6B6B)

/**
 * Вкладка «Генерация». Три шага, каждый — отдельная кнопка, чтобы было видно,
 * где заканчивается статистика и начинается фантазия модели:
 *
 *   1. темы + длительность (ранжирует статистика нишы);
 *   2. скелет по битам + правки агента-монтажёра (балл обязан вырасти);
 *   3. проверка прав/монетизации + пакет и ffmpeg-рецепт.
 *
 * Публикации здесь нет намеренно: кнопка кладёт ролик в очередь, выкладываешь ты.
 */
@Composable
fun GenerationScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val state by vm.generation.collectAsStateWithLifecycle()
    val busy by vm.generationBusy.collectAsStateWithLifecycle()
    val llm by vm.llmSettings.collectAsStateWithLifecycle()
    val workspace by vm.workspace.collectAsStateWithLifecycle()

    val format = VideoFormat.of(state.format)
    var durationText by remember(format, state.durationSec) {
        mutableStateOf(if (state.durationSec > 0) state.durationSec.toString() else "")
    }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SectionHeader(
                "Генерация",
                "Ролик собирается из статистики YouTube: что в нише залетает, какой длины и с каким хуком. " +
                    "На выходе — биты, озвучка, субтитры, проверка прав и скрипт сборки.",
            )
        }

        item {
            Panel {
                Text("Ниша", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    // по 4 чипа в ряд, иначе на узком экране превращается в кашу
                    vm.generationNiches().chunked(4).forEach { row ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            row.forEach { name ->
                                Pill(
                                    text = name,
                                    color = ACCENT,
                                    selected = (state.niche.ifBlank { workspace.profile.niche }) == name,
                                    modifier = Modifier.weight(1f),
                                    onClick = { vm.genNiche(name) },
                                )
                            }
                        }
                    }
                }

                Spacer(Modifier.height(14.dp))
                Text("Формат", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    vm.genAvailableFormats().forEach { candidate ->
                        Pill(
                            text = candidate.label,
                            color = ACCENT,
                            selected = candidate == format,
                            modifier = Modifier.weight(1f),
                            onClick = { vm.genFormat(candidate) },
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))
                LabeledField(
                    label = "Длительность, секунд (можно оставить 0 — предложу по статистике)",
                    value = durationText,
                    onValueChange = { raw ->
                        val digits = raw.filter { it.isDigit() }.take(4)
                        durationText = digits
                        vm.genDuration(digits.toIntOrNull() ?: 0)
                    },
                    placeholder = "${format.minSec}–${format.maxSec}",
                )
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = {
                        val suggested = vm.genSuggestDuration()
                        durationText = suggested.toString()
                        vm.genDuration(suggested)
                    }) { Text("Предложить: ${vm.genSuggestDuration()} с", color = ACCENT) }
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (llm.isUsable) "тексты: ${llm.model}" else "тексты: офлайн-движок",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }

                Spacer(Modifier.height(12.dp))
                Button(
                    onClick = { vm.generate() },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Считаю…" else "Сгенерировать темы") }
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = { vm.researchNow() },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Подтянуть статистику YouTube по этой нише") }
                Text(
                    if (state.researchFresh) {
                        "Живые данные: ${state.research.size} роликов, медиана " +
                            "${state.research.map { it.durationSec }.filter { it > 0 }.run { if (isEmpty()) 0 else this[size / 2] }}с"
                    } else {
                        "Живой статистики нет: search.list YouTube стоит 100 единиц квоты, поэтому она кэшируется на 6 часов. " +
                            "Без ключа API считаю по демо-приорам нишы и помечаю это явно."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }

        item {
            Panel {
                Text("${ViralEditor.NAME} — ${ViralEditor.ROLE}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                ViralEditor.RULES.forEach { rule ->
                    Text("• $rule", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        if (state.topics.isEmpty()) {
            item { EmptyHint("Пока пусто. Выбери нишу и формат — и нажми «Сгенерировать темы».") }
        } else {
            item {
                Text(
                    "Темы: ${state.topics.size}. Отранжированы по просмотрам на час, а не по любви модели",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
            }
            items(state.topics) { topic ->
                TopicCard(topic, busy, onBuild = { vm.buildPlan(topic) })
            }
        }

        state.plan?.let { plan ->
            item { PlanCard(plan, busy, vm) }
        }

        if (state.history.isNotEmpty()) {
            item {
                Panel {
                    Text("Журнал мастерской", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(6.dp))
                    state.history.take(6).forEach { line ->
                        Text(line, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                    }
                }
            }
        }
        item { Spacer(Modifier.height(20.dp)) }
    }
}

@Composable
private fun TopicCard(topic: TopicCandidate, busy: Boolean, onBuild: () -> Unit) {
    var open by remember(topic.title) { mutableStateOf(false) }
    Panel {
        Row(verticalAlignment = Alignment.Top) {
            Box(
                Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(ACCENT.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center,
            ) { Text("${topic.score.total}", color = ACCENT, fontWeight = FontWeight.Bold) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(topic.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(3.dp))
                Text(
                    "${topic.niche} · ${topic.format.label} · ${topic.durationSec}с · " +
                        "${"%.0f".format(topic.velocityPerHour)} просм/ч · конкуренция ${topic.competition}",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (topic.fromDemo) MaterialTheme.colorScheme.outline else MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (topic.fromDemo) {
                    Text("демо-приоры нишы (нет ключа YouTube API)", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                }
            }
        }
        Spacer(Modifier.height(10.dp))
        ScoreRow("хук", topic.score.hook)
        ScoreRow("ритм", topic.score.pacing)
        ScoreRow("раскрытие", topic.score.payoff)
        ScoreRow("удержание", topic.score.retention)
        ScoreRow("монетизация", topic.score.monetization)

        Spacer(Modifier.height(8.dp))
        Text(topic.why, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(6.dp))
        Text(
            if (open) "свернуть доказательства" else "почему я так думаю (${topic.evidence.size})",
            style = MaterialTheme.typography.labelMedium,
            color = ACCENT,
            modifier = Modifier.clickable { open = !open },
        )
        if (open) {
            Spacer(Modifier.height(6.dp))
            topic.evidence.forEach { line ->
                Text("· $line", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
            }
            Spacer(Modifier.height(6.dp))
            Text("Хук: ${topic.hook}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(10.dp))
        Button(onClick = onBuild, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
            Text("Собрать ролик: биты, правки, проверка прав")
        }
    }
}

@Composable
private fun PlanCard(plan: GenerationPlan, busy: Boolean, vm: WorkDayViewModel) {
    var showRecipe by remember(plan.id) { mutableStateOf(false) }
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "Пакет к публикации",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
            )
            Box(
                Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(if (plan.compliance.allowedToPublish) OK.copy(alpha = 0.16f) else BAD.copy(alpha = 0.16f))
                    .padding(horizontal = 10.dp, vertical = 4.dp)
            ) {
                Text(
                    if (plan.compliance.allowedToPublish) "права чисты" else "есть блокеры",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (plan.compliance.allowedToPublish) OK else BAD,
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(
            "Балл ${plan.scoreBefore.total} → ${plan.scoreAfter.total} после правок ${ViralEditor.NAME} · ${plan.totalSec}с · ${plan.beats.size} битов · ${plan.modelSource}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(10.dp))
        ScoreRow("хук", plan.scoreBefore.hook, plan.scoreAfter.hook)
        ScoreRow("ритм", plan.scoreBefore.pacing, plan.scoreAfter.pacing)
        ScoreRow("раскрытие", plan.scoreBefore.payoff, plan.scoreAfter.payoff)
        ScoreRow("удержание", plan.scoreBefore.retention, plan.scoreAfter.retention)
        ScoreRow("монетизация", plan.scoreBefore.monetization, plan.scoreAfter.monetization)

        HorizontalDivider(Modifier.padding(vertical = 12.dp))
        Text("Скелет по битам", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        plan.beats.forEach { beat -> BeatRow(beat) }

        if (plan.edits.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text("Правки агента-монтажёра", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            plan.edits.forEach { edit ->
                Column(Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
                    Text("${edit.action}  (+${edit.delta})", style = MaterialTheme.typography.bodySmall, color = ACCENT, fontWeight = FontWeight.Bold)
                    Text("было: ${edit.before}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                    Text("стало: ${edit.after}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("зачем: ${edit.reason}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Text("Материалы и лицензии", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        plan.assets.forEach { asset ->
            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.Top) {
                Text(
                    if (asset.license.blocking) "✕" else "✓",
                    color = if (asset.license.blocking) BAD else OK,
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text("${asset.kind.label} · ${asset.id}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
                    Text("${asset.license.label} · ${asset.query.take(110)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                    if (asset.note.isNotBlank()) {
                        Text(asset.note, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Text("Проверка перед публикацией", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        plan.compliance.checks.forEach { check ->
            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.Top) {
                Text(
                    if (check.ok) "✓" else if (check.blocking) "✕" else "!",
                    color = if (check.ok) OK else if (check.blocking) BAD else Color(0xFFFACC15),
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(check.rule, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (!check.ok && check.fix.isNotBlank()) {
                        Text(check.fix, style = MaterialTheme.typography.labelSmall, color = if (check.blocking) BAD else MaterialTheme.colorScheme.outline)
                    }
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Text("Упаковка", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        SelectionContainer {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(plan.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                Text(plan.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("Теги: ${plan.tags.joinToString(", ")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                Text("Закреплённый комментарий: ${plan.pinnedComment}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                Text("Превьюха: ${plan.thumbnailBrief}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
            }
        }

        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { showRecipe = !showRecipe }, modifier = Modifier.weight(1f)) {
                Text(if (showRecipe) "Скрыть сборку" else "Как собирать", color = ACCENT)
            }
            OutlinedButton(onClick = { vm.reEditPlan() }, enabled = !busy, modifier = Modifier.weight(1f)) {
                Text("Ещё правки", color = ACCENT)
            }
        }
        Button(
            onClick = { vm.enqueueGenerated() },
            enabled = plan.compliance.allowedToPublish && !busy,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        ) { Text(if (plan.compliance.allowedToPublish) "В очередь публикации" else "Сначала закрой блокирующие проверки") }

        if (showRecipe) {
            Spacer(Modifier.height(10.dp))
            Text(plan.recipe.notes, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
            Spacer(Modifier.height(6.dp))
            TextButton(onClick = { vm.saveRecipe() }) {
                Text("Сохранить recipe-файл в приложение", color = ACCENT)
            }
            Spacer(Modifier.height(8.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color(0xFF0D1017))
                    .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), RoundedCornerShape(12.dp))
                    .padding(12.dp)
            ) {
                SelectionContainer {
                    Column {
                        Text("render.sh", style = MaterialTheme.typography.labelSmall, color = ACCENT)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            plan.recipe.script,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            color = Color(0xFFD7E0F5),
                        )
                        Spacer(Modifier.height(10.dp))
                        Text("captions.srt", style = MaterialTheme.typography.labelSmall, color = ACCENT)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            plan.recipe.srt.take(1400),
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            color = Color(0xFF9FB0CE),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun BeatRow(beat: Beat) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.Top) {
        Text(
            "${beat.startSec}–${beat.endSec}с",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.width(58.dp),
        )
        Column(Modifier.weight(1f)) {
            Text(
                beat.role.label + if (beat.overlay.isNotBlank()) " · «${beat.overlay}»" else "",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Bold,
            )
            Text(beat.voice, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("${beat.screen} · ${beat.shot}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
private fun ScoreRow(label: String, value: Int, after: Int? = null) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            if (after == null) label else "$label  $value→$after",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.width(120.dp),
        )
        ProgressBar(
            progress = (after ?: value) / 100f,
            color = when {
                (after ?: value) >= 75 -> OK
                (after ?: value) >= 50 -> ACCENT
                else -> BAD
            },
            modifier = Modifier.weight(1f),
        )
    }
}
