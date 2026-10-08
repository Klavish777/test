package work.day.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.staticCompositionLocalOf
import work.day.app.di.AppContainer
import work.day.app.ui.WorkDayRoot
import work.day.app.ui.theme.WorkDayTheme

val LocalContainer = staticCompositionLocalOf<AppContainer> { error("AppContainer not provided") }

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val container = (application as WorkDayApp).container
        setContent {
            CompositionLocalProvider(LocalContainer provides container) {
                WorkDayTheme {
                    WorkDayRoot()
                }
            }
        }
    }

    override fun onPause() {
        super.onPause()
        (application as WorkDayApp).container.persistFlush()
    }
}
