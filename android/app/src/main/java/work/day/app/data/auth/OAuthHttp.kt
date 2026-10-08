package work.day.app.data.auth

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.Callback
import okhttp3.FormBody
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class AuthHttpException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Один HTTP-клиент на все обменные эндпоинты (Google, TikTok, Firebase).
 * Никаких промежуточных серверов: обмен кода на токен идёт напрямую провайдеру.
 */
object OAuthHttp {

    private val json = kotlinx.serialization.json.Json { ignoreUnknownKeys = true; isLenient = true }

    private val http: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .callTimeout(45, TimeUnit.SECONDS)
            .build()
    }

    suspend fun postForm(url: String, fields: Map<String, String>, bearer: String? = null): String =
        withContext(Dispatchers.IO) {
            val form = FormBody.Builder().apply { fields.forEach { (k, v) -> add(k, v) } }.build()
            send(url, Request.Builder().url(url).post(form), bearer)
        }

    suspend fun postJson(url: String, body: String, bearer: String? = null): String =
        withContext(Dispatchers.IO) {
            val req = Request.Builder()
                .url(url)
                .post(body.toRequestBody("application/json; charset=utf-8".toMediaType()))
            send(url, req, bearer)
        }

    suspend fun get(url: String, bearer: String? = null): String =
        withContext(Dispatchers.IO) { send(url, Request.Builder().url(url).get(), bearer) }

    suspend fun getJson(url: String, bearer: String? = null): kotlinx.serialization.json.JsonObject =
        json.parseToJsonElement(get(url, bearer)).let { it as kotlinx.serialization.json.JsonObject }

    private fun send(url: String, builder: Request.Builder, bearer: String?): String {
        if (!bearer.isNullOrBlank()) builder.header("Authorization", "Bearer $bearer")
        builder.header("Accept", "application/json")
        val response = try {
            http.newCall(builder.build()).execute()
        } catch (e: IOException) {
            throw AuthHttpException("Сеть недоступна при обращении к ${host(url)}: ${e.message}", e)
        }
        val text = response.use { it.body?.string().orEmpty() }
        if (!response.isSuccessful) {
            val detail = runCatching {
                val root = json.parseToJsonElement(text).let { it as kotlinx.serialization.json.JsonObject }
                (root["error_description"] ?: root["error"] ?: root["message"])?.toString()?.take(200)
            }.getOrNull()
            throw AuthHttpException("${host(url)} ответил ${response.code}. ${detail.orEmpty()}".trim())
        }
        return text
    }

    private fun host(url: String): String = url.substringAfter("://").substringBefore('/')

    /** Тот же запрос, но корутиной — оставлено на случай, если понадобится отмена из UI. */
    @Suppress("unused")
    private suspend fun enqueue(call: Call): String = suspendCancellableCoroutine { cont ->
        cont.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) = cont.resumeWithException(AuthHttpException(e.message, e))
            override fun onResponse(call: Call, response: Response) =
                cont.resume(response.use { it.body?.string().orEmpty() })
        })
    }
}
