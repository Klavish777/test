package work.day.app

import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.browser.customtabs.CustomTabsIntent
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import work.day.app.di.AppContainer

/**
 * Точка возврата из браузера для OAuth: workdayauth://oauth2callback?code=…&state=…
 * Экран ничего не показывает: забирает query-параметры, отдаёт их AuthRepository и закрывается.
 * Отдельная Activity нужна потому, что браузер резолвит именно intent-filter приложения.
 */
class OAuthRedirectActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = (application as WorkDayApp).container
        val data = intent?.data
        if (data == null) {
            container.auth.cancelLink("браузер вернул пустой redirect")
            finish()
            return
        }
        handle(container, data.toString())
    }

    private fun handle(container: AppContainer, uri: String) {
        lifecycleScope.launch {
            container.auth.completeRedirect(uri)
                .onSuccess { container.notifyAuth("Подключено: ${it.title} · ${it.provider.label}") }
                .onFailure { container.notifyAuth("Не вышло: ${it.message?.take(180)}") }
            finish()
        }
    }

    companion object {
        /** Открывает страницу согласия в Custom Tab (то есть в системном браузере, не во «встроенном webview»). */
        /** @return false, если на устройстве вообще нечем открыть ссылку — вызывающий обязан снять pending-состояние. */
        fun open(context: Context, url: String): Boolean = runCatching {
            CustomTabsIntent.Builder()
                .setShowTitle(true)
                .build()
                .launchUrl(context, Uri.parse(url))
        }.recoverCatching {
            // если Custom Tabs нет (без Google Play), уходим в обычный VIEW-интент
            context.startActivity(
                android.content.Intent(android.content.Intent.ACTION_VIEW, Uri.parse(url)),
            )
        }.isSuccess
    }
}
