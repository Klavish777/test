package work.day.app.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import android.content.Context
import androidx.compose.ui.platform.LocalContext
import work.day.app.WorkDayApp
import work.day.app.ui.agents.AgentsScreen
import work.day.app.ui.growth.GrowthScreen
import work.day.app.ui.settings.SettingsScreen
import work.day.app.ui.shift.ShiftScreen
import work.day.app.ui.tasks.TasksScreen

private data class Tab(val label: String, val icon: ImageVector)

@Composable
fun WorkDayRoot() {
    val context = LocalContext.current
    val app = context.applicationContext as WorkDayApp
    val vm: WorkDayViewModel = viewModel(factory = ViewModelProvider.AndroidViewModelFactory.getInstance(app))

    val tabs = listOf(
        Tab("Смена", Icons.Filled.Home),
        Tab("Агенты", Icons.Filled.Person),
        Tab("Задачи", Icons.Filled.List),
        Tab("Рост", Icons.Filled.DateRange),
        Tab("Настройки", Icons.Filled.Settings),
    )
    var selected by rememberSaveable { mutableStateOf(0) }
    val snackbar = remember { SnackbarHostState() }
    val session by vm.session.collectAsStateWithLifecycle()
    var unlocked by rememberSaveable { mutableStateOf(false) }

    androidx.compose.runtime.LaunchedEffect(Unit) {
        vm.messages.collect { snackbar.showSnackbar(it) }
    }

    // Порядок: если стоит замок — сначала он; если человек ещё не входил и не отказался — экран входа.
    if (session.lockEnabled && !unlocked) {
        work.day.app.ui.auth.LockScreen(vm, onUnlocked = { unlocked = true })
        return
    }
    if (session.needsAuth) {
        work.day.app.ui.auth.AuthScreen(vm)
        return
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                tabs.forEachIndexed { index, tab ->
                    NavigationBarItem(
                        selected = index == selected,
                        onClick = { selected = index },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label, style = MaterialTheme.typography.labelMedium) },
                    )
                }
            }
        },
    ) { padding ->
        val content: @Composable (Modifier) -> Unit = when (selected) {
            0 -> { m -> ShiftScreen(vm, m) }
            1 -> { m -> AgentsScreen(vm, m) }
            2 -> { m -> TasksScreen(vm, m) }
            3 -> { m -> GrowthScreen(vm, m) }
            else -> { m -> SettingsScreen(vm, m) }
        }
        content(Modifier.padding(padding))
    }
}
