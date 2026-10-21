@echo off
rem Запуск Smartphone Repair OS из исходников на Windows.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Первый запуск: создание окружения и установка зависимостей...
    python -m venv .venv || goto :error
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
)

.venv\Scripts\python.exe main.py %*
goto :eof

:error
echo Не удалось запустить. Проверьте, что установлен Python 3.10+ (python.org).
pause
exit /b 1
