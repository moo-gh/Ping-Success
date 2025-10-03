@echo off
echo Closing any running instances...
taskkill /F /IM PingSuccessMonitor.exe 2>nul
timeout /t 2 /nobreak >nul

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Cleaning build directories...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building executable...
python -m PyInstaller --clean --noconfirm build_exe.spec

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Testing the executable...
    timeout /t 1 /nobreak >nul
    start dist\PingSuccessMonitor.exe
) else (
    echo.
    echo BUILD FAILED!
    pause
)

