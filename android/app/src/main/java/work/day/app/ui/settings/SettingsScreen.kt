package work.day.app.ui.settings

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import work.day.app.domain.SafetyPolicy
import work.day.app.domain.model.ChannelProfile
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.LabeledField
import work.day.app.ui.common.Panel
import work.day.app.ui.common.Pill
import work.day.app.ui.common.SectionHeader

@Composable
fun SettingsScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val workspace by vm.workspace.collectAsStateWithLifecycle()
    val llm by vm.llmSettings.collectAsStateWithLifecycle()

    var profile by remember { mutableStateOf(workspace.profile) }
    var baseUrl by remember { mutableStateOf(llm.baseUrl) }
    var apiKey by remember { mutableStateOf(llm.apiKey) }
    var model by remember { mutableStateOf(llm.model) }
    var enabled by remember { mutableStateOf(llm.enabled) }
    var youtubeKey by remember { mutableStateOf("") }
    var shiftStart by remember { mutableStateOf(9 * 60) }
    var shiftEnd by remember { mutableStateOf(18 * 60) }
    var showReset by remember { mutableStateOf(false) }
    var exported by remember { mutableStateOf("") }

    LaunchedEffect(Unit) { youtubeKey = "" }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { SectionHeader("Настройки", "Ключи хранятся только на устройстве. Приложение не имеет собственного сервера.") }

        // ── модель ────────────────────────────────────────────────────────────
        item {
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Модель для генерации", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(
                            if (enabled && apiKey.isNotBlank()) "онлайн · $model" else "офлайн-движок (шаблоны, без сети)",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = enabled, onCheckedChange = { enabled = it })
                }
                Spacer(Modifier.height(12.dp))
                LabeledField("API-адрес (OpenAI-совместимый)", baseUrl, { baseUrl = it }, placeholder = "https://api.openai.com/v1")
                Spacer(Modifier.height(10.dp))
                LabeledField("Ключ", apiKey, { apiKey = it }, placeholder = "sk-…")
                Spacer(Modifier.height(10.dp))
                LabeledField("Модель", model, { model = it }, placeholder = "gpt-4o-mini / llama-3.1-70b / qwen2.5")
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = { vm.saveLlm(enabled, baseUrl, apiKey, model) }) { Text("Сохранить") }
                    OutlinedButton(onClick = { vm.testLlm("Одним предложением: что такое CTR обложки?") }) { Text("Проверить") }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Можно оставить выключенным: агенты продолжат планировать смены и собирать материалы офлайн-движком. " +
                        "Качество текстов будет шаблонным, но интерфейс и порядок работы — те же.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }

        // ── канал ─────────────────────────────────────────────────────────────
        item {
            Panel {
                Text("Канал", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                LabeledField("ID канала YouTube", profile.youtubeChannelId, { profile = profile.copy(youtubeChannelId = it.trim()) }, placeholder = "UC…")
                Spacer(Modifier.height(10.dp))
                LabeledField("Ник в TikTok", profile.tiktokHandle, { profile = profile.copy(tiktokHandle = it.trim()) }, placeholder = "@username")
                Spacer(Modifier.height(10.dp))
                LabeledField("Ниша", profile.niche, { profile = profile.copy(niche = it) }, placeholder = "например: съёмка на телефон для новичков")
                Spacer(Modifier.height(10.dp))
                LabeledField("Кто зритель", profile.audience, { profile = profile.copy(audience = it) }, placeholder = "например: 22–35, хотят монетизировать хобби")
                Spacer(Modifier.height(10.dp))
                LabeledField("Тон автора", profile.tone, { profile = profile.copy(tone = it) }, singleLine = false)
                Spacer(Modifier.height(10.dp))
                LabeledField(
                    "Ключевые фразы (через запятую)",
                    profile.keywords.joinToString(", "),
                    { profile = profile.copy(keywords = it.split(',').map { k -> k.trim() }.filter { k -> k.isNotBlank() }) },
                )
                Spacer(Modifier.height(10.dp))
                LabeledField(
                    "Слоты публикаций",
                    profile.publishWindows.joinToString(", "),
                    { profile = profile.copy(publishWindows = it.split(',').map { w -> w.trim() }.filter { w -> w.isNotBlank() }) },
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = { vm.updateProfile(profile) }) { Text("Сохранить канал") }
                    OutlinedButton(onClick = { vm.connectYoutube() }) { Text("Подтянуть статистику") }
                }
                Spacer(Modifier.height(10.dp))
                LabeledField("Ключ YouTube Data API (только чтение)", youtubeKey, { youtubeKey = it }, placeholder = "AIza…")
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = { vm.setYoutubeApiKey(youtubeKey) }, enabled = youtubeKey.isNotBlank()) { Text("Сохранить ключ") }
            }
        }

        // ── аккаунт и доступы ─────────────────────────────────────────────────
        item {
            Panel {
                val session by vm.session.collectAsStateWithLifecycle()
                val clients by vm.authClients.collectAsStateWithLifecycle()
                var googleId by remember { mutableStateOf(clients.googleClientId) }
                var tiktokKey by remember { mutableStateOf(clients.tiktokClientKey) }
                var tiktokSecret by remember { mutableStateOf(clients.tiktokClientSecret) }
                var firebaseKey by remember { mutableStateOf(clients.firebaseApiKey) }
                var redirect by remember { mutableStateOf(clients.redirectUri) }
                var tiktokStats by remember { mutableStateOf(clients.tiktokWithStats) }
                var lockOn by remember { mutableStateOf(session.lockEnabled) }
                var lockPassword by remember { mutableStateOf("") }

                Text("Аккаунт и доступы", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Text(
                    "Токены лежат в ${vm.tokenStorage()}. В выгрузку настроек и в логи они не попадают.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                Spacer(Modifier.height(12.dp))
                if (session.links.isEmpty()) {
                    Text("Ни один провайдер не привязан. Агенты работают на демо-данных и офлайн-движке.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
                } else {
                    session.links.forEach { link ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("${link.provider.label} · ${link.title}", style = MaterialTheme.typography.bodyLarge)
                                Text(
                                    listOfNotNull(
                                        link.email.takeIf { it.isNotBlank() },
                                        "scope: ${link.scopes.size}",
                                        if (link.expiresAt > 0) {
                                            val until = java.text.SimpleDateFormat("dd.MM HH:mm", java.util.Locale.getDefault())
                                                .format(java.util.Date(link.expiresAt))
                                            if (link.isExpired) "токен истёк${if (link.canRefresh) ", обновлю сам" else " — войди заново"}"
                                            else "действует до $until"
                                        } else null,
                                        if (link.followers > 0) "подписчиков: ${link.followers}" else null,
                                    ).filter { it.isNotBlank() }.joinToString(" · "),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (link.needsAttention) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.outline,
                                )
                            }
                            OutlinedButton(onClick = { vm.revoke(link.provider) }) { Text("Отвязать") }
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { vm.link(work.day.app.domain.model.AuthProvider.GOOGLE) }, enabled = clients.readyForGoogle) { Text("Google") }
                    OutlinedButton(onClick = { vm.link(work.day.app.domain.model.AuthProvider.TIKTOK) }, enabled = clients.readyForTikTok) { Text("TikTok") }
                    OutlinedButton(onClick = { vm.refreshTikTokStats() }) { Text("Цифры TikTok") }
                }

                Spacer(Modifier.height(14.dp))
                Text("Клиенты авторизации", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Work Day — публичный клиент: секрета приложения у него нет и быть не может. " +
                        "Поэтому Google настраивается клиентом «Android» (пакет + SHA-1 сборки), а TikTok — Client Key из " +
                        "твоего приложения в TikTok for Developers с тем же redirect. Пошагово — в docs/AUTH.md.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
                Spacer(Modifier.height(10.dp))
                LabeledField("Google Client ID", googleId, { googleId = it.trim() }, placeholder = "xxxx.apps.googleusercontent.com")
                Spacer(Modifier.height(10.dp))
                LabeledField("TikTok Client Key", tiktokKey, { tiktokKey = it.trim() }, placeholder = "aw…")
                Spacer(Modifier.height(10.dp))
                LabeledField("TikTok Client Secret (если приложение серверного типа)", tiktokSecret, { tiktokSecret = it.trim() })
                Spacer(Modifier.height(10.dp))
                LabeledField("Firebase Web API Key (для переносимого логина/пароля)", firebaseKey, { firebaseKey = it.trim() }, placeholder = "AIza…")
                Spacer(Modifier.height(10.dp))
                LabeledField(
                    "Redirect URI",
                    redirect,
                    { redirect = it.trim() },
                    placeholder = "https://<user>.github.io/auth-callback/",
                )
                Text(
                    "Google с 2025 года не принимает на Android кастомные схемы вида workdayauth:// — " +
                        "в это поле нужен https-адрес страницы-перехвата, и та же строка должна стоять " +
                        "в консоли провайдера. Быстрее всего поднять её на GitHub Pages из папки docs/ " +
                        "(docs/auth-callback/index.html уже лежит в репозитории), остальное — по шагам в docs/AUTH.md. " +
                        "Для отладки на своём устройстве можно оставить и workdayauth://oauth2callback: " +
                        "Activity слушает обе схемы.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Просить user.info.stats у TikTok", style = MaterialTheme.typography.bodyLarge)
                        Text(
                            "Только если TikTok одобрил этот scope в твоём приложении: с неодобренным " +
                                "scope страница согласия отклоняет весь запрос целиком. Без него подписчики " +
                                "и просмотры придут нулями — выдумывать их приложение не будет.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = tiktokStats, onCheckedChange = { tiktokStats = it })
                }
                Spacer(Modifier.height(12.dp))
                Button(onClick = {
                    vm.saveAuthClients(
                        clients.copy(
                            googleClientId = googleId.trim(),
                            tiktokClientKey = tiktokKey.trim(),
                            tiktokClientSecret = tiktokSecret.trim(),
                            firebaseApiKey = firebaseKey.trim(),
                            tiktokWithStats = tiktokStats,
                            redirectUri = redirect.trim().ifBlank { work.day.app.domain.model.AuthClients.DEFAULT_REDIRECT },
                        )
                    )
                }) { Text("Сохранить клиенты") }

                Spacer(Modifier.height(16.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Замок на приложении", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(
                            "Проверка пароля идёт локальным PBKDF2-хешем, поэтому работает без сети.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = lockOn, onCheckedChange = { lockOn = it })
                }
                if (lockOn != session.lockEnabled) {
                    Spacer(Modifier.height(8.dp))
                    LabeledField("Новый пароль замка (от 6 символов)", lockPassword, { lockPassword = it })
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(onClick = {
                        vm.saveLock(lockOn, lockPassword.ifBlank { null })
                        lockPassword = ""
                    }) { Text(if (lockOn) "Поставить замок" else "Снять замок") }
                }
                Spacer(Modifier.height(10.dp))
                OutlinedButton(onClick = { vm.signOut() }) { Text("Выйти из аккаунта и отвязать всё") }
            }
        }

        // ── распорядок ────────────────────────────────────────────────────────
        item {
            Panel {
                Text("Распорядок смены", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text("начало", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            listOf(6, 8, 9, 10, 12).forEach { h ->
                                Pill("${h}:00", color = Color(0xFF5B5CFF), selected = shiftStart / 60 == h, onClick = { shiftStart = h * 60 })
                            }
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                Column {
                    Text("финал", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf(15, 17, 18, 20, 22).forEach { h ->
                            Pill("${h}:00", color = Color(0xFF12B886), selected = shiftEnd / 60 == h, onClick = { shiftEnd = h * 60 })
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = { vm.setShiftWindow(shiftStart, shiftEnd) }) { Text("Применить") }
                Text(
                    "Смена — это ритм, а не обязаловка: агенты успевают ${((shiftEnd - shiftStart) / 60 * 0.8).toInt()} часов работы, " +
                        "а дальше ты сам решаешь, что из их материалов публиковать.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }

        // ── безопасность ──────────────────────────────────────────────────────
        item {
            Panel(background = Color(0xFF1A1420), border = Color(0x55FF5C7A)) {
                Text("Что агенты не делают никогда", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = Color(0xFFFF8FA3))
                Spacer(Modifier.height(8.dp))
                SafetyPolicy.never.forEach { line ->
                    Text("• $line", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 3.dp))
                }
                Spacer(Modifier.height(10.dp))
                Text(SafetyPolicy.reason, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(10.dp))
                Text("Что они делают свободно", style = MaterialTheme.typography.labelMedium, color = Color(0xFF4ADE80))
                SafetyPolicy.always.forEach { line ->
                    Text("• $line", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 2.dp))
                }
            }
        }

        // ── данные ────────────────────────────────────────────────────────────
        item {
            Panel {
                Text("Данные", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Всё живёт в одном JSON-файле на устройстве: профиль, конфиги агентов, материалы, отчёты. " +
                        "Выгрузка — чтобы перенести или показать свою работу без доступа к телефону.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = { exported = vm.export() }) { Text("Выгрузить") }
                    OutlinedButton(onClick = { showReset = true }) { Text("Сбросить всё") }
                }
                if (exported.isNotBlank()) {
                    Spacer(Modifier.height(10.dp))
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.background)
                            .padding(12.dp)
                    ) {
                        Text(exported.take(2000), style = MaterialTheme.typography.bodySmall, maxLines = 14)
                    }
                }
            }
        }

        if (showReset) {
            item {
                Panel(background = Color(0xFF26141A), border = Color(0x88FF5C7A)) {
                    Text("Точно стереть всё?", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("Материалы, отчёты и настройки агентов удалятся безвозвратно.", style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(onClick = { vm.resetAll(); showReset = false }) { Text("Стереть") }
                        OutlinedButton(onClick = { showReset = false }) { Text("Отмена") }
                    }
                }
            }
        }

        item {
            Text(
                "Work Day 0.1.0 · сборка для разработчика. Плейбуки: ${work.day.app.domain.model.Playbooks.all.size}, действий: ${work.day.app.domain.model.TaskKind.entries.size}.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline,
            )
            Spacer(Modifier.height(40.dp))
        }
    }
}
