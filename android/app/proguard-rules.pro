# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class work.day.app.** {
    *** Companion;
}
-keepclasseswithmembers class work.day.app.** {
    kotlinx.serialization.KSerializer serializer(...);
}
# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
