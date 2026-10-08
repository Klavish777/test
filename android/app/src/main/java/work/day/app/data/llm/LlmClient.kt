package work.day.app.data.llm

import work.day.app.domain.agent.LlmBrief

data class LlmSettings(
    val enabled: Boolean = false,
    val baseUrl: String = "https://api.openai.com/v1",
    val apiKey: String = "",
    val model: String = "gpt-4o-mini",
    val timeoutSeconds: Int = 60,
) {
    val isUsable: Boolean get() = enabled && apiKey.isNotBlank() && baseUrl.isNotBlank() && model.isNotBlank()
}

class LlmException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Абстракция генератора. Приложения-агенты не знают, кто за ним: облачная модель
 * или офлайн-движок — они лишь просят текст по брифу.
 */
interface LlmClient {
    suspend fun complete(brief: LlmBrief): LlmResult
    val source: Source

    enum class Source { REMOTE, OFFLINE }
}

data class LlmResult(val text: String, val source: LlmClient.Source, val chars: Int = text.length)
