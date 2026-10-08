package work.day.app

import android.app.Application
import work.day.app.di.AppContainer

class WorkDayApp : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        container.start()
    }
}
