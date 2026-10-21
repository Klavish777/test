<#
.SYNOPSIS
    Сборка Smartphone Repair OS для Windows 10/11 (EXE + установщик).

.DESCRIPTION
    Скрипт создаёт виртуальное окружение, устанавливает зависимости, запускает
    тесты, собирает приложение через PyInstaller и (если установлен Inno Setup)
    формирует установочный файл.

    Каждый шаг пишет полный вывод в build\logs\build.log. При ошибке хвост лога
    печатается в консоль и в аннотацию GitHub Actions, поэтому причину сбоя
    видно даже без доступа к сырым логам сборки.

.PARAMETER Version
    Версия сборки. По умолчанию берётся из repair_os/version.py.
    Недопустимые для имени файла символы вычищаются автоматически.

.PARAMETER SkipTests
    Пропустить тесты (не рекомендуется).

.PARAMETER RequireInstaller
    Считать отсутствие Inno Setup ошибкой (используется в CI).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -Version 0.1.0
#>
param(
    [string]$Version = "",
    [switch]$SkipTests,
    [switch]$RequireInstaller
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

# Windows по умолчанию использует cp1252 для пайпов — кириллица в выводе Python
# падает с UnicodeEncodeError. Принудительно включаем UTF-8.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$logDir = Join-Path $root "build\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "build.log"
if (Test-Path $logPath) { Remove-Item -Force $logPath }

function Write-Log([string]$text, [string]$color = "Gray") {
    Write-Host $text -ForegroundColor $color
    Add-Content -Path $logPath -Value $text -Encoding utf8
}

function Fail([string]$message, [string]$logFile = "") {
    Write-Log "ОШИБКА: $message" "Red"
    if ($logFile -and (Test-Path $logFile)) {
        $tail = Get-Content $logFile -Tail 60 -Encoding utf8
        Write-Log "----- последние строки $(Split-Path -Leaf $logFile) -----" "Yellow"
        foreach ($line in $tail) { Write-Log $line "Yellow" }
        $joined = ($tail -join " | ")
        if ($joined.Length -gt 3000) { $joined = $joined.Substring($joined.Length - 3000) }
        $joined = $joined.Replace("%", "%25").Replace("`r", "%0D").Replace("`n", "%0A")
        Write-Host "::error title=$message::$joined"
    } else {
        Write-Host "::error title=$message::$message"
    }
    throw $message
}

# Версия: из version.py, если не передана; иначе чистим под имя файла --------
$versionFile = Join-Path $root "repair_os\version.py"
if (-not $Version -and (Test-Path $versionFile)) {
    $match = Select-String -Path $versionFile -Pattern 'APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($match) { $Version = $match.Matches[0].Groups[1].Value }
}
if (-not $Version) { $Version = "0.0.0" }
$Version = $Version -replace "^refs/tags/", "" -replace "^refs/heads/", "" -replace "^v", ""
$Version = ($Version -replace "[^0-9A-Za-z\.\-]", ".")
if ($Version -match "^\d+\.\d+\.\d+$") { } elseif ($Version -match "^\d+\.\d+") { } else { $Version = "0.0.0" }

Write-Log "== Smartphone Repair OS build $Version ==" "Cyan"
Write-Log "Каталог проекта: $root"
Write-Log "Лог сборки: $logPath"

# 1. Python и виртуальное окружение -----------------------------------------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "Python не найден. Установите Python 3.10+ с python.org и повторите."
}
$pythonVersion = (python --version) 2>&1
Write-Log "Python: $pythonVersion"

if (-not (Test-Path "$root\.venv")) {
    Write-Log "Создание виртуального окружения..." "Cyan"
    python -m venv .venv
}
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip *>&1 | Out-File -FilePath $logPath -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Fail "Не удалось обновить pip" $logPath }
& $venvPython -m pip install -r requirements-dev.txt *>&1 | Out-File -FilePath $logPath -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Fail "Не удалось установить зависимости" $logPath }

# 2. Тесты ------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Log "Запуск тестов..." "Cyan"
    $env:QT_QPA_PLATFORM = "offscreen"
    $testLog = Join-Path $logDir "pytest.log"
    & $venvPython -m pytest tests -q *>&1 | Tee-Object -FilePath $testLog | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) { Fail "Тесты не прошли — сборка остановлена." $testLog }
    Remove-Item Env:\QT_QPA_PLATFORM
}

# 3. Проверка базы ----------------------------------------------------------
Write-Log "Проверка базы данных..." "Cyan"
$checkLog = Join-Path $logDir "check.log"
& $venvPython main.py --check --no-demo *>&1 | Tee-Object -FilePath $checkLog | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Fail "Проверка базы не пройдена." $checkLog }

# 4. PyInstaller ------------------------------------------------------------
Write-Log "Сборка приложения (PyInstaller)..." "Cyan"
if (Test-Path "$root\build\SmartphoneRepairOS") { Remove-Item -Recurse -Force "$root\build\SmartphoneRepairOS" }
if (Test-Path "$root\dist\SmartphoneRepairOS") { Remove-Item -Recurse -Force "$root\dist\SmartphoneRepairOS" }
$pyiLog = Join-Path $logDir "pyinstaller.log"
& $venvPython -m PyInstaller "build\smartphone_repair_os.spec" --noconfirm --clean --distpath dist --workpath build\pyinstaller *>&1 |
    Tee-Object -FilePath $pyiLog | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller завершился с ошибкой." $pyiLog }

$exe = Join-Path $root "dist\SmartphoneRepairOS\SmartphoneRepairOS.exe"
if (-not (Test-Path $exe)) { Fail "EXE не найден: $exe" $pyiLog }
Write-Log "Готово: $exe" "Green"

# Дымовой запуск собранного EXE в режиме проверки (без окна) -----------------
Write-Log "Дымовой запуск собранного EXE (--check)..." "Cyan"
$smokeLog = Join-Path $logDir "smoke.log"
& $exe --check --no-demo --data-dir (Join-Path $root "build\smoke-data") *>&1 |
    Tee-Object -FilePath $smokeLog | ForEach-Object { Write-Log $_ }
$smokeExit = $LASTEXITCODE
if ($smokeExit -ne 0) { Fail "Собранный EXE не проходит самопроверку (--check)." $smokeLog }
Write-Log "Самопроверка EXE пройдена." "Green"

# 5. Установщик (Inno Setup) ------------------------------------------------
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($iscc) {
    Write-Log "Сборка установщика (Inno Setup): $iscc" "Cyan"
    $isccLog = Join-Path $logDir "inno.log"
    & $iscc "build\installer.iss" "/DAppVersion=$Version" *>&1 |
        Tee-Object -FilePath $isccLog | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) { Fail "Inno Setup завершился с ошибкой." $isccLog }
    $installer = Join-Path $root "installer\Output\SmartphoneRepairOS-$Version-setup.exe"
    if (-not (Test-Path $installer)) { Fail "Установщик не создан: $installer" $isccLog }
    Write-Log "Установщик: $installer" "Green"
} elseif ($RequireInstaller) {
    Fail "Inno Setup 6 не найден, установщик не создан (нужен для CI)."
} else {
    Write-Log "Inno Setup 6 не найден. Установите https://jrsoftware.org/isinfo.php и повторите." "Yellow"
    Write-Log "Либо распространяйте портативную сборку из dist\SmartphoneRepairOS." "Yellow"
}

# 6. Портативный архив ------------------------------------------------------
$zip = Join-Path $root "installer\Output\SmartphoneRepairOS-$Version-portable.zip"
if (-not (Test-Path (Split-Path -Parent $zip))) { New-Item -ItemType Directory -Force -Path (Split-Path -Parent $zip) | Out-Null }
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $root "dist\SmartphoneRepairOS\*") -DestinationPath $zip -CompressionLevel Optimal
Write-Log "Портативная сборка: $zip" "Green"

Write-Log "== Сборка завершена ==" "Cyan"
