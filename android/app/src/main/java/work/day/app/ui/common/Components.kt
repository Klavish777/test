package work.day.app.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import work.day.app.domain.model.AgentId

val PanelShape = RoundedCornerShape(18.dp)
val ChipShape = RoundedCornerShape(999.dp)

@Composable
fun Panel(
    modifier: Modifier = Modifier,
    background: Color = MaterialTheme.colorScheme.surface,
    border: Color = Color.Transparent,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(PanelShape)
            .background(background)
            .then(if (border != Color.Transparent) Modifier.border(1.dp, border, PanelShape) else Modifier)
            .padding(16.dp),
        content = content,
    )
}

@Composable
fun SectionHeader(text: String, note: String = "", modifier: Modifier = Modifier) {
    Column(modifier = modifier.fillMaxWidth()) {
        Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (note.isNotBlank()) {
            Spacer(Modifier.height(2.dp))
            Text(note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun StatTile(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = MaterialTheme.colorScheme.onBackground,
    caption: String = "",
) {
    Column(modifier = modifier) {
        Text(label.uppercase(), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(4.dp))
        Text(value, style = MaterialTheme.typography.titleLarge, color = valueColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
        if (caption.isNotBlank()) {
            Text(caption, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
fun Pill(
    text: String,
    color: Color,
    selected: Boolean = false,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
) {
    Box(
        modifier = modifier
            .clip(ChipShape)
            .background(if (selected) color else color.copy(alpha = 0.14f))
            .then(if (onClick != null) Modifier.clickable { onClick() } else Modifier)
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Text(
            text,
            style = MaterialTheme.typography.labelMedium,
            color = if (selected) Color.Black else color,
            maxLines = 1,
        )
    }
}

@Composable
fun AgentBadge(agent: AgentId, size: Int = 34) {
    Box(
        modifier = Modifier
            .size(size.dp)
            .clip(RoundedCornerShape(size / 3))
            .background(Color(agent.accent).copy(alpha = 0.18f)),
        contentAlignment = Alignment.Center,
    ) {
        Text(agent.emoji, style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
fun ProgressBar(progress: Float, color: Color, modifier: Modifier = Modifier, track: Color = MaterialTheme.colorScheme.surfaceVariant) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(CircleShape2)
            .background(track)
    ) {
        Box(
            Modifier
                .fillMaxWidth(progress.coerceIn(0f, 1f))
                .height(6.dp)
                .clip(CircleShape2)
                .background(color)
        )
    }
}

private val CircleShape2 = RoundedCornerShape(999.dp)

@Composable
fun EmptyHint(text: String) {
    Box(Modifier.fillMaxWidth().padding(vertical = 28.dp), contentAlignment = Alignment.Center) {
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.outline)
    }
}

@Composable
fun LabeledField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String = "",
    singleLine: Boolean = true,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(6.dp))
        androidx.compose.material3.OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            placeholder = { Text(placeholder, color = MaterialTheme.colorScheme.outline) },
            singleLine = singleLine,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(14.dp),
        )
    }
}
