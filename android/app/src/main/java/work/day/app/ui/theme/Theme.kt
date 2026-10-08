package work.day.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val scheme = darkColorScheme(
    primary = Violet,
    onPrimary = Color.White,
    secondary = Mint,
    onSecondary = Ink0,
    background = Ink0,
    onBackground = TextPrimary,
    surface = Ink1,
    onSurface = TextPrimary,
    surfaceVariant = Ink2,
    onSurfaceVariant = TextSecondary,
    outline = Line,
    error = Danger,
    onError = Color.White,
)

@Composable
fun WorkDayTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = scheme,
        typography = WorkDayTypography,
        shapes = MaterialTheme.shapes,
        content = content,
    )
}
