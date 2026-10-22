@echo off
chcp 65001 >nul
rem Запуск Apple Flash Studio из исходников на Windows 10/11.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Apple Flash Studio] Первый запуск: создание виртуального окружения .venv...
    python -m venv .venv || goto :error
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul
    echo [Apple Flash Studio] Установка интерфейса PySide6...
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
    echo [Apple Flash Studio] Установка движка прошивки pymobiledevice3 (опционально)...
    .venv\Scripts\python.exe -m pip install pymobiledevice3 || echo [Предупреждение] pymobiledevice3 не установлен, приложение запустится в штатном режиме.
)

.venv\Scripts\python.exe apple_flash_main.py %*
goto :eof

:error
echo.
echo [ОШИБКА] Не удалось подготовить окружение Python. Убедитесь, что установлен Python 3.10+ (https://www.python.org) с галочкой Add Python to PATH.
pause
exit /b 1
