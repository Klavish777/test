package work.day.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import work.day.app.ui.WorkDayViewModel
import work.day.app.ui.common.LabeledField

/**
 * Замок на приложении. Проверяется локальным хешем, поэтому работает без сети;
 * цифры канала и планы агентов при этом остаются на устройстве и внутрь экрана не попадают.
 */
@Composable
fun LockScreen(vm: WorkDayViewModel, onUnlocked: () -> Unit, modifier: Modifier = Modifier) {
    val session by vm.session.collectAsStateWithLifecycle()
    var password by remember { mutableStateOf("") }
    var errorText by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(PaddingValues(24.dp)),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Work Day", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text(
            if (session.email.isNotBlank()) "Приложение защищено паролем · ${session.email}" else "Приложение защищено паролем",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(24.dp))
        LabeledField("Пароль", password, { password = it; errorText = null }, placeholder = "••••••")
        Spacer(Modifier.height(14.dp))
        Button(
            onClick = { if (vm.unlock(password)) onUnlocked() else errorText = "Пароль не подошёл" },
            enabled = password.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Разблокировать") }
        errorText?.let {
            Spacer(Modifier.height(10.dp))
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(16.dp))
        Text(
            "Если пароль потерян — единственный путь это сброс данных в «Настройках»: " +
                "приложение принципиально не хранит пароль в виде, который можно восстановить.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}
