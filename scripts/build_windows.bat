@echo off
rem Сборка Smartphone Repair OS для Windows: EXE + установщик.
rem Требования: Python 3.10+, Inno Setup 6 (для установщика).

setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Создание виртуального окружения...
    python -m venv .venv || goto :error
)
set PY=.venv\Scripts\python.exe

echo [2/5] Установка зависимостей...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install -r requirements-dev.txt || goto :error

echo [3/5] Тесты...
set QT_QPA_PLATFORM=offscreen
%PY% -m pytest tests -q || goto :error
set QT_QPA_PLATFORM=

echo [4/5] Сборка приложения...
if exist dist\SmartphoneRepairOS rmdir /s /q dist\SmartphoneRepairOS
%PY% -m PyInstaller build\smartphone_repair_os.spec --noconfirm --clean --distpath dist --workpath build\pyinstaller || goto :error

echo [5/5] Установщик Inno Setup...
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" (
    "%ISCC%" build\installer.iss || goto :error
    echo Установщик: installer\Output\SmartphoneRepairOS-*-setup.exe
) else (
    echo Inno Setup 6 не найден: https://jrsoftware.org/isinfo.php
    echo Портативная сборка: dist\SmartphoneRepairOS\SmartphoneRepairOS.exe
)

echo Сборка завершена.
goto :eof

:error
echo Ошибка сборки. Смотрите сообщения выше.
exit /b 1
