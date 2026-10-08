package work.day.app.core

import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json

/**
 * Один JSON-файл на состоянии. Читается синхронно при старте (приложение локальное,
 * файл маленький), пишется асинхронно на IO. Никаких SQLite-миграций и зависимостей.
 */
class PersistedStore<T : Any>(
    private val file: File,
    private val serializer: KSerializer<T>,
    private val json: Json,
    private val scope: CoroutineScope,
    initial: () -> T,
) {

    private val _state = MutableStateFlow(read() ?: initial())
    val state: StateFlow<T> = _state.asStateFlow()
    val value: T get() = _state.value

    var lastError: String? = null
        private set

    private fun read(): T? = runCatching {
        if (file.exists()) json.decodeFromString(serializer, file.readText()) else null
    }.getOrNull()

    fun update(block: (T) -> T) {
        val next = block(_state.value)
        _state.value = next
        persist(next)
    }

    fun replace(next: T) = update { next }

    /** Немедленно сбросить на диск — вызывается при выходе/сохранении настроек. */
    fun flush() = persistBlocking(_state.value)

    private fun persist(next: T) {
        scope.launch(Dispatchers.IO) { persistBlocking(next) }
    }

    private fun persistBlocking(next: T) {
        runCatching {
            file.parentFile?.mkdirs()
            val tmp = File(file.parentFile, file.name + ".tmp")
            tmp.writeText(json.encodeToString(serializer, next))
            if (!tmp.renameTo(file)) {
                file.writeText(json.encodeToString(serializer, next))
                tmp.delete()
            }
        }.onFailure { lastError = it.message }
    }
}
