@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
powershell -ExecutionPolicy Bypass -File "scripts\build_apple_flash_windows.ps1" %*
if errorlevel 1 (
    echo Сборка завершилась с ошибкой.
    pause
    exit /b 1
)
