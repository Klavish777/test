# Плагины

Плагин — способ добавить поддержку производителя, не меняя ядро приложения. Ядро ничего не знает
о брендах: всё, что специфично, описывает модуль.

## Контракт

```csharp
public interface INexusPlugin
{
    PluginManifest Manifest { get; }
    IReadOnlyList<CompatibilityItem> CheckCompatibility(DeviceInfo device);
    IReadOnlyList<string> DescribeOperations(DeviceInfo device);
}
```

`CheckCompatibility` возвращает проверки с уровнями `Info/Warning/Blocking`; `DescribeOperations` —
список доступных операций. Сам плагин не выполняет запись: любые операции проходят через
`FlashPlanner` и подтверждения ядра.

## Манифест

Файл `*.plugin.json` в каталоге плагинов. Поля:

| Поле | Назначение |
|------|------------|
| `id`, `name`, `version` | идентификация и версия (SemVer, допускается `1.0`) |
| `assemblyFile`, `entryType` | сборка и тип точки входа |
| `sha256` | SHA-256 сборки — **обязателен** |
| `publisher` | издатель; должен быть в списке доверенных |
| `signature` | отсоединённая подпись манифеста (RSA-SHA256, base64); также читается из `{assembly}.sig` |
| `supportedBrands`, `supportedPlatforms`, `supportedModels` | заявленная область поддержки |
| `requiredDrivers` | драйверы, без которых модуль не работает |
| `operations` | операции, которые модуль реализует |
| `checks` | проверки, которые модуль выполняет перед операцией |
| `firmwareFormats` | поддерживаемые форматы |
| `requiredPermissions` | `read-device`, `read-files`, `write-device`, … |
| `limitations` | что модуль не делает — показывается пользователю |
| `limits` | `maxFirmwareSizeBytes`, `canWriteDevice`, `requiresNetwork`, `allowedPartitions` |
| `requiresElevation`, `minimumHostVersion` | требования к хосту |

## Проверка доверия

`PluginTrustPolicy.Validate` выполняется в фиксированном порядке:

1. обязательные поля и корректность версии;
2. `minimumHostVersion` не выше версии хоста;
3. файл сборки существует;
4. SHA-256 сборки совпадает с манифестом (иначе `HashMismatch`);
5. издатель указан (иначе `Unsigned`);
6. издатель в списке доверенных (иначе `UntrustedPublisher`);
7. если для издателя сохранён открытый ключ — подпись манифеста обязана быть верной
   (иначе `SignatureInvalid`); модуль с `canWriteDevice: true` без проверенной подписи не
   загружается;
8. глобальный флаг `AllowPluginLoading` включён (иначе `NotAllowedByPolicy`).

Только после этого сборка загружается в отдельный `AssemblyLoadContext`. Причина отказа
сохраняется в `PluginHost.LastRejected` и показывается в разделе «Плагины».

## Подпись

Подписывается строка:

```
{id}|{version}|{sha256 в нижнем регистре}|{publisher}
```

алгоритм RSA-SHA256 (PKCS#1 v1.5), результат — base64 в `signature` или в файле
`{assemblyFile}.sig`. Открытый ключ издателя хранится в таблице `publisher_key`
(задаётся администратором/пользователем, который доверяет этому издателю). Проверка реализована
в `NexusFirmware.Core.Plugins.PluginSignature` и покрыта тестами (валидная подпись, подмена
манифеста, чужой ключ).

## Встроенный модуль

`GenericAndroidPlugin` (`nexus.builtin.generic-android`) не требует внешней сборки и описывает
общие операции Android: список разделов, чтение свойств, проверку целостности, диагностику
загрузчика. Он не заявляет запись и не обходит защиту.

## Чего плагин не может

* Расширить права приложения, отключить подтверждения или проверку целостности.
* Загрузиться без совпадения хэша, доверенного издателя и включённого флага.
* Выполнять запись, если ядро не построило план и пользователь не подтвердил операцию.
