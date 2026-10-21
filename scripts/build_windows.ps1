<#
.SYNOPSIS
    Сборка Smartphone Repair OS для Windows 10/11 (EXE + установщик).

.DESCRIPTION
    Скрипт создаёт виртуальное окружение, устанавливает зависимости, запускает
    тесты, собирает приложение через PyInstaller и (если установлен Inno Setup)
    формирует установочный файл.

.PARAMETER Version
    Версия сборки (подставляется в имя установщика).

.PARAMETER SkipTests
    Пропустить тесты (не рекомендуется).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -Version 0.1.0
#>
param(
    [string]$Version = "0.1.0",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "== Smartphone Repair OS build $Version ==" -ForegroundColor Cyan
Write-Host "Каталог проекта: $root"

# 1. Python и виртуальное окружение -----------------------------------------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python не найден. Установите Python 3.10+ с python.org и повторите."
}
$pythonVersion = (python --version) 2>&1
Write-Host "Python: $pythonVersion"

if (-not (Test-Path "$root\.venv")) {
    Write-Host "Создание виртуального окружения..."
    python -m venv .venv
}
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements-dev.txt

# 2. Тесты ------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Host "Запуск тестов..." -ForegroundColor Cyan
    $env:QT_QPA_PLATFORM = "offscreen"
    & $venvPython -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw "Тесты не прошли — сборка остановлена." }
    Remove-Item Env:\QT_QPA_PLATFORM
}

# 3. Проверка базы ----------------------------------------------------------
Write-Host "Проверка базы данных..." -ForegroundColor Cyan
& $venvPython main.py --check --no-demo
if ($LASTEXITCODE -ne 0) { throw "Проверка базы не пройдена." }

# 4. PyInstaller ------------------------------------------------------------
Write-Host "Сборка приложения (PyInstaller)..." -ForegroundColor Cyan
if (Test-Path "$root\build\SmartphoneRepairOS") { Remove-Item -Recurse -Force "$root\build\SmartphoneRepairOS" }
if (Test-Path "$root\dist\SmartphoneRepairOS") { Remove-Item -Recurse -Force "$root\dist\SmartphoneRepairOS" }
& $venvPython -m PyInstaller "build\smartphone_repair_os.spec" --noconfirm --clean --distpath dist --workpath build\pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller завершился с ошибкой." }

$exe = Join-Path $root "dist\SmartphoneRepairOS\SmartphoneRepairOS.exe"
if (-not (Test-Path $exe)) { throw "EXE не найден: $exe" }
Write-Host "Готово: $exe" -ForegroundColor Green

# 5. Установщик (Inno Setup) ------------------------------------------------
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    Write-Host "Сборка установщика (Inno Setup)..." -ForegroundColor Cyan
    & $iscc "build\installer.iss" "/DAppVersion=$Version"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup завершился с ошибкой." }
    $installer = Join-Path $root "installer\Output\SmartphoneRepairOS-$Version-setup.exe"
    if (Test-Path $installer) {
        Write-Host "Установщик: $installer" -ForegroundColor Green
    }
} else {
    Write-Warning "Inno Setup 6 не найден. Установите https://jrsoftware.org/isinfo.php и повторите,"
    Write-Warning "либо распространяйте портативную сборку из dist\SmartphoneRepairOS."
}

Write-Host "== Сборка завершена ==" -ForegroundColor Cyan
