package work.day.app

import java.io.File
import java.security.MessageDigest
import java.util.Base64
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import work.day.app.core.PersistedStore
import work.day.app.data.auth.AuthRepository
import work.day.app.data.auth.PasswordHasher
import work.day.app.data.auth.Pkce
import work.day.app.data.auth.TokenResponse
import work.day.app.data.auth.TokenVault
import work.day.app.data.auth.Urls
import work.day.app.domain.model.AuthClients
import work.day.app.domain.model.AuthProvider
import work.day.app.domain.model.ProviderLink
import work.day.app.domain.model.Session

class PasswordHasherTest {

    @Test
    fun `один пароль с разной солью даёт разные хеши`() {
        val a = PasswordHasher.newSalt()
        val b = PasswordHasher.newSalt()
        assertNotEqualsCompat(a, b)
        assertNotEqualsCompat(PasswordHasher.hash("secret1", a), PasswordHasher.hash("secret1", b))
    }

    @Test
    fun `проверка пароля проходит только для правильного`() {
        val salt = PasswordHasher.newSalt()
        val hash = PasswordHasher.hash("kanal-2026", salt)
        assertTrue(PasswordHasher.verify("kanal-2026", salt, hash))
        assertFalse(PasswordHasher.verify("kanal-2025", salt, hash))
        assertFalse(PasswordHasher.verify("", salt, hash))
        assertFalse(PasswordHasher.verify("kanal-2026", "", hash))
    }

    @Test
    fun `в хеш не утекает сам пароль`() {
        val salt = PasswordHasher.newSalt()
        val hash = PasswordHasher.hash("superpass", salt)
        assertFalse(hash.contains("superpass"))
        assertTrue(hash.length >= 64)
    }

    private fun assertNotEqualsCompat(a: String, b: String) = assertTrue(a != b)
}

class PkceTest {

    @Test
    fun `challenge это base64url от sha256 верификатора`() {
        val verifier = Pkce.verifier()
        val expected = Base64.getUrlEncoder().withoutPadding()
            .encodeToString(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII)))
        assertEquals(expected, Pkce.challenge(verifier))
    }

    @Test
    fun `верификатор в допустимом алфавите и без паддинга`() {
        repeat(5) {
            val v = Pkce.verifier()
            assertTrue("символы: $v", v.all { c -> c.isLetterOrDigit() || c == '-' || c == '_' })
            assertTrue("длина ${v.length}", v.length in 43..128)
            assertFalse(v.endsWith("="))
        }
    }

    @Test
    fun `state уникален на каждый заход`() = assertTrue(Pkce.state() != Pkce.state())
}

class UrlsTest {

    @Test
    fun `scope кодируется через пробел и не ломает query`() {
        val url = Urls.build(
            "https://accounts.google.com/o/oauth2/v2/auth",
            mapOf("scope" to "a b", "state" to "x/y+z", "empty" to ""),
        )
        assertTrue(url.contains("scope=a%20b"))
        assertTrue(url.contains("state=x%2Fy%2Bz"))
        assertFalse("пустые параметры не добавляются", url.contains("empty"))
    }

    @Test
    fun `редирект разбирается и из query и из fragment`() {
        val query = Urls.redirectOf("workdayauth://oauth2callback?code=Ab12&state=zz")
        assertEquals("Ab12", query?.code)
        assertEquals("zz", query?.state)
        assertNull(query?.error)

        val fragment = Urls.redirectOf("workdayauth://oauth2callback#access_token=Tok&state=zz")
        assertEquals("Tok", fragment?.raw?.get("access_token"))

        val error = Urls.redirectOf("workdayauth://oauth2callback?error=access_denied&error_description=user+denied")
        assertEquals("access_denied", error?.error)
        assertEquals("user denied", error?.errorDescription)
    }

    @Test
    fun `не редирект возвращает null`() = assertNull(Urls.redirectOf("workdayauth://oauth2callback"))
}

class TokenResponseTest {

    @Test
    fun `google-ответ разбирается`() {
        val t = TokenResponse.parse(
            AuthProvider.GOOGLE,
            """{"access_token":"ya29.x","expires_in":3599,"refresh_token":"1//y","scope":"a b","id_token":"eyJ"}""",
        )
        assertEquals("ya29.x", t.accessToken)
        assertEquals(3599L, t.expiresInSec)
        assertNotNull(t.refreshToken)
        assertTrue(t.expiresAt > System.currentTimeMillis())
    }

    @Test
    fun `tiktok-ответunpack-из-data`() {
        val t = TokenResponse.parse(
            AuthProvider.TIKTOK,
            """{"data":{"access_token":"act","expires_in":86400,"refresh_expires_in":604800,"scope":"user.info.basic"}}""",
        )
        assertEquals("act", t.accessToken)
        assertEquals(86400L, t.expiresInSec)
        assertEquals("user.info.basic", t.scope)
    }

    @Test
    fun `ошибка провайдера превращается в исключение с описанием`() {
        val failed = runCatching {
            TokenResponse.parse(AuthProvider.GOOGLE, """{"error":"invalid_grant","error_description":"Code was already redeemed."}""")
        }
        assertTrue(failed.isFailure)
        assertTrue(failed.exceptionOrNull()!!.message!!.contains("already redeemed"))
    }

    @Test
    fun `пустой ответ — это ошибка, а не пустой токен`() {
        assertTrue(runCatching { TokenResponse.parse(AuthProvider.GOOGLE, """{"token_type":"Bearer"}""") }.isFailure)
    }
}

/**
 * Поведение входа проверяется без сети: сетевые обмены начинаются только после того,
 * как редирект признан валидным, а до этого моменты — чистая логика, и она здесь покрыта.
 */
class AuthRepositoryTest {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private class Fixture(vault: TokenVault = TokenVault.InMemory()) {
        val file: File = File.createTempFile("workday-session", ".json").apply { delete() }
        val store = PersistedStore(file, Session.serializer(), Json { encodeDefaults = true }, scope) { Session() }
        var clients = AuthClients()
        val repo = AuthRepository(store, vault, { clients }, scope)
        val session: Session get() = store.value

        /** Google и TikTok формально разошлись в разделителе scope — проверяем то, что улетело в сеть. */
        fun scopeOf(url: String): String =
            java.net.URLDecoder.decode(url.substringAfter("scope=", "").substringBefore("&"), "UTF-8")
    }

    @Test
    fun `без client id вход не начинается и объясняет почему`() {
        val f = Fixture()
        val result = f.repo.beginLink(AuthProvider.GOOGLE)
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()!!.message!!.contains("Google Client ID"))
        assertNull(f.repo.pendingProvider)
    }

    @Test
    fun `google-ссылка содержит pkce и только read-only scope`() {
        val f = Fixture()
        f.clients = AuthClients(googleClientId = "abc.apps.googleusercontent.com")
        val url = f.repo.beginLink(AuthProvider.GOOGLE).getOrThrow()
        assertTrue(url.startsWith("https://accounts.google.com/o/oauth2/v2/auth"))
        assertTrue(url.contains("code_challenge_method=S256"))
        assertTrue(url.contains("response_type=code"))
        assertTrue(url.contains("redirect_uri=workdayauth%3A%2F%2Foauth2callback"))
        assertTrue(url.contains("youtube.readonly"))
        // ключевая граница продукта: права на запись приложение не запрашивает никогда
        val scopePart = java.net.URLDecoder.decode(url.substringAfter("scope=", "").substringBefore("&"), "UTF-8")
        assertTrue("scope должен оставаться read-only: $scopePart", scopePart.all { it.isBlank() || it.contains("readonly") })
        listOf("upload", "force-ssl", "insert", "update", "delete", "moderation").forEach { banned ->
            assertFalse("в scope просочилось право '$banned'", scopePart.contains(banned))
        }
        assertEquals(AuthProvider.GOOGLE, f.repo.pendingProvider)
    }

    @Test
    fun `tiktok-ссылка не запрашивает publish`() {
        val f = Fixture()
        f.clients = AuthClients(tiktokClientKey = "awj2lid6")
        val url = f.repo.beginLink(AuthProvider.TIKTOK).getOrThrow()
        val scopePart = url.substringAfter("scope=", "").substringBefore("&")
        assertTrue(scopePart.contains("user.info.basic"))
        assertTrue(scopePart.contains("video.list"))
        assertFalse(scopePart.contains("publish"))
        assertTrue(url.contains("client_key=awj2lid6"))
    }

    @Test
    fun `tiktok: scope через запятую, stats — только когда включено явно`() {
        val f = Fixture()
        f.clients = AuthClients(tiktokClientKey = "awj2lid6")
        val scope = f.scopeOf(f.repo.beginLink(AuthProvider.TIKTOK).getOrThrow())
        assertEquals("TikTok ждёт запятую между scope", "user.info.basic,video.list", scope)
        f.repo.cancelLink("тест")

        f.clients = AuthClients(tiktokClientKey = "awj2lid6", tiktokWithStats = true)
        val withStats = f.scopeOf(f.repo.beginLink(AuthProvider.TIKTOK).getOrThrow())
        assertTrue("без галочки stats запрашиваться не должен", withStats.contains("user.info.stats"))
        assertTrue(withStats.startsWith("user.info.basic"))
    }

    @Test
    fun `парольный вход не уводится в редирект`() {
        val f = Fixture()
        assertTrue(f.repo.beginLink(AuthProvider.PASSWORD).isFailure)
    }

    @Test
    fun `редирект без начатой попытки и с чужим state отклоняются`() {
        val f = Fixture()
        assertTrue(f.repo.completeRedirectBlocking("workdayauth://oauth2callback?code=1&state=zz").isFailure)

        f.clients = AuthClients(googleClientId = "cid")
        f.repo.beginLink(AuthProvider.GOOGLE)
        val bad = f.repo.completeRedirectBlocking("workdayauth://oauth2callback?code=1&state=не-тот")
        assertTrue(bad.isFailure)
        assertTrue(bad.exceptionOrNull()!!.message!!.contains("state"))
        assertNotNull(f.repo.pendingProvider) // попытка всё ещё жива до валидного ответа
    }

    @Test
    fun `отказ пользователя обрабатывается как отмена, а не как падение`() {
        val f = Fixture()
        f.clients = AuthClients(googleClientId = "cid")
        val state = f.repo.pendingStateForTest()
        val denied = f.repo.completeRedirectBlocking("workdayauth://oauth2callback?error=access_denied&state=$state")
        assertTrue(denied.isFailure)
        assertTrue(denied.exceptionOrNull()!!.message!!.contains("отказ"))
        assertNull(f.repo.pendingProvider)
    }

    @Test
    fun `локальная регистрация ставит замок и не хранит пароль`() {
        val f = Fixture()
        f.repo.registerBlocking("Author@Kanal.ru", "passw0rd", "passw0rd")
        val s = f.session
        assertEquals("author@kanal.ru", s.email)
        assertTrue(s.lockEnabled)
        assertTrue(s.hasPassword)
        assertFalse("пароль нигде не лежит", s.passwordHash.contains("passw0rd"))

        val dump = json.encodeToString(Session.serializer(), s)
        assertFalse(dump.contains("passw0rd"))

        assertTrue(f.repo.signInBlocking("author@kanal.ru", "passw0rd").isSuccess)
        assertTrue(f.repo.signInBlocking("author@kanal.ru", "ошибочный").isFailure)
        assertTrue(f.repo.signInBlocking("chujak@mail.ru", "passw0rd").isFailure)
    }

    @Test
    fun `слабый пароль и несовпадение подтверждения отсекаются`() {
        val f = Fixture()
        assertTrue(f.repo.registerBlocking("a@b.ru", "123", "123").isFailure)
        assertTrue(f.repo.registerBlocking("a@b.ru", "abcdefgh", "abcdefhh").isFailure)
        assertTrue(f.repo.registerBlocking("без-собаки", "abcdefgh", "abcdefgh").isFailure)
    }

    @Test
    fun `гостевой режим снимает требование входа`() {
        val f = Fixture()
        assertTrue(f.session.needsAuth)
        f.repo.continueAsGuest()
        assertFalse(f.session.needsAuth)
    }

    @Test
    fun `выход чистит токены и ссылки`() {
        val vault = TokenVault.InMemory()
        val f = Fixture(vault)
        f.repo.registerBlocking("me@kanal.ru", "passw0rd", "passw0rd")
        vault.set("tmp", "x")
        f.repo.signOut()
        assertTrue(vault.snapshot().none { it.key.startsWith("access_") })
        assertEquals(emptyList<ProviderLink>(), f.session.links)
        assertEquals("", f.session.email)
    }

    @Test
    fun `токен неистёкшего провайдера без refresh не отдаётся`() {
        val f = Fixture()
        assertNull(runBlocking { f.repo.accessToken(AuthProvider.GOOGLE) })
    }

    @Test
    fun `link считает истечение срока с запасом на перекос часов`() {
        val fresh = ProviderLink(AuthProvider.GOOGLE, expiresAt = System.currentTimeMillis() + 10 * 60_000)
        val expiring = ProviderLink(AuthProvider.TIKTOK, expiresAt = System.currentTimeMillis() + 1_000)
        val forever = ProviderLink(AuthProvider.PASSWORD)
        assertFalse(fresh.isExpired)
        assertTrue(expiring.isExpired)
        assertTrue(expiring.needsAttention)
        assertFalse(forever.isExpired)
    }

    @Test
    fun `session переживает перезапуск приложения`() {
        val f = Fixture()
        f.repo.registerBlocking("keep@kanal.ru", "passw0rd", "passw0rd")
        f.store.flush() // запись асинхронная, в тесте ждём детерминизма
        val restored = PersistedStore(f.file, Session.serializer(), json, scope) { Session() }
        assertEquals("keep@kanal.ru", restored.value.email)
        assertTrue(restored.value.lockEnabled)
    }
}

// ─── мостики: тестируем suspend-логика без runBlocking в каждом тесте ───────────
private fun AuthRepository.registerBlocking(email: String, password: String, confirm: String) =
    runBlocking { register(email, password, confirm) }

private fun AuthRepository.signInBlocking(email: String, password: String) = runBlocking { signIn(email, password) }

private fun AuthRepository.completeRedirectBlocking(uri: String) = runBlocking { completeRedirect(uri) }

/** Тесту нужен тот же state, который репозиторий сгенерировал internally. */
private fun AuthRepository.pendingStateForTest(): String {
    val field = javaClass.getDeclaredField("pending")
    field.isAccessible = true
    val pending = field.get(this) ?: error("pending не установлен")
    val stateField = pending.javaClass.getDeclaredField("state")
    stateField.isAccessible = true
    return stateField.get(pending) as String
}
