package work.day.app.data.repo

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import work.day.app.data.llm.LlmSettings

private val Context.workDayDataStore: DataStore<Preferences> by preferencesDataStore(name = "work_day_settings")

/**
 * Настройки окружения: какая модель генерирует материалы, когда начинается смена,
 * какой ключ YouTube Data API. Ключи хранятся только на устройстве и никогда не отправляются
 * на чужие серверы — запрос идёт напрямую в API провайдера.
 */
class SettingsRepository(private val context: Context) {

    private object Keys {
        val LLM_ENABLED = booleanPreferencesKey("llm_enabled")
        val LLM_BASE_URL = stringPreferencesKey("llm_base_url")
        val LLM_API_KEY = stringPreferencesKey("llm_api_key")
        val LLM_MODEL = stringPreferencesKey("llm_model")
        val YOUTUBE_API_KEY = stringPreferencesKey("youtube_api_key")
        val SHIFT_START = intPreferencesKey("shift_start")
        val SHIFT_END = intPreferencesKey("shift_end")
        val SPEED = intPreferencesKey("speed")
        val ONBOARDING_DONE = booleanPreferencesKey("onboarding_done")
    }

    private val prefs get() = context.workDayDataStore

    val llmSettings: Flow<LlmSettings> = prefs.data.map { p ->
        LlmSettings(
            enabled = p[Keys.LLM_ENABLED] ?: false,
            baseUrl = p[Keys.LLM_BASE_URL] ?: DEFAULT_BASE_URL,
            apiKey = p[Keys.LLM_API_KEY] ?: "",
            model = p[Keys.LLM_MODEL] ?: "",
        )
    }

    val hasKey: Flow<Boolean> = llmSettings.map { it.isUsable }
    val onboardingDone: Flow<Boolean> = prefs.data.map { it[Keys.ONBOARDING_DONE] ?: false }

    suspend fun llmNow(): LlmSettings = llmSettings.first()

    suspend fun setLlm(enabled: Boolean, baseUrl: String, apiKey: String, model: String) {
        prefs.edit {
            it[Keys.LLM_ENABLED] = enabled
            it[Keys.LLM_BASE_URL] = baseUrl.ifBlank { DEFAULT_BASE_URL }
            it[Keys.LLM_API_KEY] = apiKey
            it[Keys.LLM_MODEL] = model
        }
    }

    suspend fun youtubeApiKey(): String = prefs.data.first()[Keys.YOUTUBE_API_KEY].orEmpty()

    suspend fun setYoutubeApiKey(key: String) {
        prefs.edit { it[Keys.YOUTUBE_API_KEY] = key.trim() }
    }

    suspend fun shiftStartMinutes(): Int = prefs.data.first()[Keys.SHIFT_START] ?: 9 * 60
    suspend fun shiftEndMinutes(): Int = prefs.data.first()[Keys.SHIFT_END] ?: 18 * 60
    suspend fun speed(): Int = prefs.data.first()[Keys.SPEED] ?: 1

    suspend fun setShift(startMinutes: Int, endMinutes: Int) {
        prefs.edit {
            it[Keys.SHIFT_START] = startMinutes.coerceIn(0, 22 * 60)
            it[Keys.SHIFT_END] = endMinutes.coerceIn(startMinutes + 60, 23 * 60 + 59)
        }
    }

    suspend fun setSpeed(multiplier: Int) {
        prefs.edit { it[Keys.SPEED] = multiplier.coerceIn(1, 8) }
    }

    suspend fun finishOnboarding() {
        prefs.edit { it[Keys.ONBOARDING_DONE] = true }
    }

    companion object {
        const val DEFAULT_BASE_URL = "https://api.openai.com/v1"
    }
}
