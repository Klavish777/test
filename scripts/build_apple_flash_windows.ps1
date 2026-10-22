<#
.SYNOPSIS
    Сборка Apple Flash Studio для Windows 10/11 x64 (AppleFlashStudio.exe + portable ZIP + установщик Inno Setup).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_apple_flash_windows.ps1 -Version 1.0.0
#>
param(
    [string]$Version = "1.0.0",
    [switch]$SkipTests,
    [switch]$UseCurrentPython
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

# Очистка версии от символов пути (например, если передано имя ветки со слэшем)
$SafeVersion = ($Version -replace '[^A-Za-z0-9._\-]', '-')

Write-Host "== Apple Flash Studio build $SafeVersion ==" -ForegroundColor Cyan
Write-Host "Каталог проекта: $root"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python не найден. Установите Python 3.10+ (x64) с python.org и повторите."
}

if ($UseCurrentPython) {
    $pyExe = (Get-Command python).Source
    Write-Host "Используется системный Python: $pyExe"
} else {
    if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
        Write-Host "Создание виртуального окружения .venv..."
        python -m venv .venv
    }
    $pyExe = Join-Path $root ".venv\Scripts\python.exe"
    & $pyExe -m pip install --upgrade pip
    & $pyExe -m pip install -r requirements-dev.txt
}

if (-not $SkipTests) {
    Write-Host "Запуск автотестов Apple Flash Studio..." -ForegroundColor Cyan
    $env:QT_QPA_PLATFORM = "offscreen"
    & $pyExe -m pytest tests/apple_flash -q
    if ($LASTEXITCODE -ne 0) { throw "Тесты не прошли — сборка остановлена." }
    Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
}

Write-Host "Проверка инициализации SQLite базы..." -ForegroundColor Cyan
& $pyExe apple_flash_main.py --check --no-demo
if ($LASTEXITCODE -ne 0) { throw "Проверка базы данных завершилась с ошибкой." }

$icoPath = Join-Path $root "apple_flash\resources\apple_flash.ico"
if (-not (Test-Path $icoPath)) {
    Write-Host "Генерация иконки Windows (.ico)..." -ForegroundColor Cyan
    $env:QT_QPA_PLATFORM = "offscreen"
    & $pyExe apple_flash_main.py --export-ico $icoPath
    Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
}

Write-Host "Сборка EXE (PyInstaller)..." -ForegroundColor Cyan
if (Test-Path "$root\dist\AppleFlashStudio") { Remove-Item -Recurse -Force "$root\dist\AppleFlashStudio" }
& $pyExe -m PyInstaller "packaging\apple_flash_studio.spec" --noconfirm --clean --distpath dist --workpath build\pyinstaller_apple_flash
if ($LASTEXITCODE -ne 0) { throw "PyInstaller завершился с ошибкой." }

$exe = Join-Path $root "dist\AppleFlashStudio\AppleFlashStudio.exe"
if (-not (Test-Path $exe)) { throw "EXE не создан: $exe" }
Write-Host "Портативная сборка готова: $exe" -ForegroundColor Green

$outDir = Join-Path $root "installer\Output"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$portableZip = Join-Path $outDir "AppleFlashStudio-$SafeVersion-portable-win64.zip"
if (Test-Path $portableZip) { Remove-Item -Force $portableZip }
Compress-Archive -Path "$root\dist\AppleFlashStudio\*" -DestinationPath $portableZip -Force
Write-Host "Портативный ZIP-архив готов: $portableZip" -ForegroundColor Green

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    Write-Host "Сборка установщика Windows (Inno Setup 6)..." -ForegroundColor Cyan
    & $iscc "packaging\apple_flash_installer.iss" "/DAppVersion=$SafeVersion"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup завершился с ошибкой." }
    $installer = Join-Path $outDir "AppleFlashStudio-$SafeVersion-setup.exe"
    if (Test-Path $installer) {
        Write-Host "Установщик готов: $installer" -ForegroundColor Green
    }
} else {
    Write-Warning "Inno Setup 6 не найден. Портативная сборка находится в dist\AppleFlashStudio."
}

Write-Host "== Сборка Apple Flash Studio завершена ==" -ForegroundColor Cyan
