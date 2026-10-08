package work.day.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import work.day.app.domain.model.AuthProvider
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.LabeledField
import work.day.app.ui.common.Panel

/**
 * Экран входа. Порядок мыслей такой: вход не является условием работы приложения —
 * агенты планируют смену и без привязанных площадок. Поэтому «продолжить без входа»
 * стоит наравне с провайдерами, а не мелким текстом внизу.
 */
@Composable
fun AuthScreen(vm: WorkDayViewModel, modifier: Modifier = Modifier) {
    val session by vm.session.collectAsStateWithLifecycle()
    val clients by vm.authClients.collectAsStateWithLifecycle()
    var mode by remember { mutableStateOf(Mode.SIGN_IN) }
    var email by remember { mutableStateOf(session.email) }
    var password by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(PaddingValues(20.dp)),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Spacer(Modifier.height(18.dp))
        Column {
            Text("Work Day", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(
                "Смена из четырёх AI-агентов: прирост, привлечение, ускорение и активность для YouTube и TikTok.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Panel {
            Text("Войти, чтобы видеть свои цифры", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(
                "Без входа приложение работает: агенты строят план, считают эксперименты и пишут тексты. " +
                    "Привязка площадки нужна, чтобы они опирались на реальную статистику, а не на демо-данные.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(14.dp))

            ProviderRow(
                icon = "▶",
                title = "Google",
                subtitle = if (clients.readyForGoogle) scopesGoogle() else "нужен Google Client ID в настройках",
                ready = clients.readyForGoogle,
                connected = session.link(AuthProvider.GOOGLE) != null,
                accent = Color(0xFFFF4E45),
                onClick = { busy = true; vm.link(AuthProvider.GOOGLE); busy = false },
            )
            ProviderRow(
                icon = "♪",
                title = "TikTok",
                subtitle = if (clients.readyForTikTok) "профиль, список роликов, статистика (по одобренным scope)"
                else "нужен Client Key из TikTok for Developers",
                ready = clients.readyForTikTok,
                connected = session.link(AuthProvider.TIKTOK) != null,
                accent = Color(0xFF25F4EE),
                onClick = { busy = true; vm.link(AuthProvider.TIKTOK); busy = false },
            )
        }

        Panel {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Логин и пароль", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text(
                    if (clients.readyForFirebase) "Firebase Auth" else "локальный режим",
                    style = MaterialTheme.typography.labelMedium,
                    color = Color(0xFF12B886),
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                if (clients.readyForFirebase)
                    "Аккаунт в твоём Firebase-проекте: пароль не хранится на устройстве, настройки можно перенести на другой телефон."
                else
                    "Своего сервера у приложения нет, поэтому аккаунт создаётся на устройстве: пароль превращается в PBKDF2-хеш " +
                        "(210 000 итераций, случайная соль) и проверяется офлайн. Это замок на приложение, а не переносимый аккаунт — " +
                        "для переносимого нужен Firebase API-ключ выше.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ModeTab("Вход", mode == Mode.SIGN_IN) { mode = Mode.SIGN_IN }
                ModeTab("Регистрация", mode == Mode.REGISTER) { mode = Mode.REGISTER }
                ModeTab("Забыли?", mode == Mode.RESET) { mode = Mode.RESET }
            }
            Spacer(Modifier.height(12.dp))
            LabeledField("Почта", email, { email = it }, placeholder = "you@mail.com")
            Spacer(Modifier.height(10.dp))
            if (mode != Mode.RESET) {
                LabeledField("Пароль", password, { password = it }, placeholder = "от 6 символов")
                if (mode == Mode.REGISTER) {
                    Spacer(Modifier.height(10.dp))
                    LabeledField("Повтори пароль", confirm, { confirm = it })
                }
            }
            Spacer(Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                when (mode) {
                    Mode.SIGN_IN -> Button(onClick = { busy = true; vm.signIn(email, password); busy = false }, enabled = password.isNotBlank()) { Text("Войти") }
                    Mode.REGISTER -> Button(onClick = { busy = true; vm.register(email, password, confirm); busy = false }, enabled = password.isNotBlank()) { Text("Создать аккаунт") }
                    Mode.RESET -> Button(onClick = { busy = true; vm.resetPassword(email); busy = false }, enabled = clients.readyForFirebase) { Text("Письмо для сброса") }
                }
                OutlinedButton(onClick = { vm.continueAsGuest() }) { Text("Без входа") }
            }
            if (mode == Mode.RESET && !clients.readyForFirebase) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Локальный пароль сбросить нельзя — он нигде не хранится в открытом виде. " +
                        "Вариант: стереть данные в настройках и завести аккаунт заново.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }

        Text(
            "Права, которые приложение запрашивает: только чтение статистики. Ни публикацию, ни удаление, " +
            "ни управление комментариями от твоего имени — и не попросит.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
        Spacer(Modifier.height(20.dp))
    }
}

private enum class Mode { SIGN_IN, REGISTER, RESET }

@Composable
private fun ModeTab(text: String, selected: Boolean, onClick: () -> Unit) {
    Box(
        Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant)
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(999.dp))
            .clickable { onClick() }
            .padding(horizontal = 14.dp, vertical = 7.dp)
    ) {
        Text(
            text,
            style = MaterialTheme.typography.labelMedium,
            color = if (selected) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ProviderRow(
    icon: String,
    title: String,
    subtitle: String,
    ready: Boolean,
    connected: Boolean,
    accent: Color,
    onClick: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .then(if (ready) Modifier.clickable { onClick() } else Modifier)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(11.dp))
                .background(accent.copy(alpha = 0.18f)),
            contentAlignment = Alignment.Center,
        ) { Text(icon, color = accent, fontWeight = FontWeight.Bold) }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = if (ready) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
            )
        }
        Text(
            when {
                connected -> "подключено"
                !ready -> "не настроено"
                else -> "подключить"
            },
            style = MaterialTheme.typography.labelMedium,
            color = if (connected) Color(0xFF4ADE80) else accent,
        )
    }
}

@Composable
private fun scopesGoogle(): String = "канал, просмотры, удержание и источники трафика · только чтение"


