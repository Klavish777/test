package work.day.app.data.llm

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import work.day.app.domain.agent.LlmBrief
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Клиент к любому OpenAI-совместимому API (OpenAI, OpenRouter, Together, LM Studio, vLLM, Ollama).
 * Ключ хранится только на устройстве, запрос уходит напрямую — без промежуточного сервера.
 */
class OpenAiCompatLlm(
    private val settingsProvider: () -> LlmSettings,
) : LlmClient {

    override val source = LlmClient.Source.REMOTE

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = false }

    private val http by lazy {
        val timeout = settingsProvider().timeoutSeconds.coerceIn(10, 180).toLong()
        OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .callTimeout(timeout, TimeUnit.SECONDS)
            .readTimeout(timeout, TimeUnit.SECONDS)
            .build()
    }

    override suspend fun complete(brief: LlmBrief): LlmResult {
        val settings = settingsProvider()
        require(settings.isUsable) { "LLM не настроен" }

        val payload = buildString {
            append("{")
            append("\"model\":").append(json.quote(settings.model)).append(",")
            append("\"temperature\":").append(brief.temperature).append(",")
            append("\"max_tokens\":").append(brief.maxTokens).append(",")
            append("\"messages\":[")
            append(role("system", brief.system)).append(",")
            append(role("user", brief.user))
            append("]}")
        }

        val request = Request.Builder()
            .url(settings.baseUrl.trimEnd('/') + "/chat/completions")
            .header("Authorization", "Bearer ${settings.apiKey}")
            .header("Content-Type", "application/json")
            .post(payload.toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()

        val body = http.await(request)
        val text = extractContent(body)
        return LlmResult(text = text, source = source)
    }

    private fun role(role: String, content: String): String =
        "\"role\":${json.quote(role)},\"content\":${json.quote(content)}"

    private fun extractContent(raw: String): String = try {
        val root = json.parseToJsonElement(raw).jsonObject
        val choices = root["choices"]?.jsonArray ?: throw LlmException("Ответ без choices")
        val message = choices.first().jsonObject["message"]?.jsonObject
            ?: throw LlmException("Пустой ответ модели")
        val content = message["content"]?.jsonPrimitive?.content.orEmpty()
        val reasoning = message["reasoning_content"]?.jsonPrimitive?.content.orEmpty()
        content.ifBlank { reasoning }.ifBlank { throw LlmException("Модель вернула пустой текст") }
    } catch (e: LlmException) {
        throw e
    } catch (e: Exception) {
        throw LlmException("Не удалось разобрать ответ: ${e.message}", e)
    }

    private suspend fun OkHttpClient.await(request: Request): String =
        suspendCancellableCoroutine { cont ->
            val call = newCall(request)
            cont.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) = cont.resumeWithException(
                    LlmException("Сеть недоступна: ${e.message}", e)
                )

                override fun onResponse(call: Call, response: Response) {
                    val text = runCatching { response.use { it.body?.string().orEmpty() } }
                    response.close()
                    when {
                        !text.isSuccess -> cont.resumeWithException(
                            LlmException("Чтение ответа не удалось", text.exceptionOrNull())
                        )
                        response.code in 400..499 -> cont.resumeWithException(
                            LlmException("Ошибка API ${response.code}: ${text.getOrNull()?.take(240)}")
                        )
                        response.code in 500..599 -> cont.resumeWithException(
                            LlmException("Сервер API недоступен (${response.code})")
                        )
                        else -> cont.resume(text.getOrNull().orEmpty())
                    }
                }
            })
        }
}

internal fun Json.quote(value: String): String {
    val escaped = buildString {
        for (c in value) when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (c < ' ') append("\\u%04x".format(c.code)) else append(c)
        }
    }
    return "\"$escaped\""
}
