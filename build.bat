@echo off
echo Building Git Version Manager...
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

cd /d "%~dp0"

REM Build single exe
pyinstaller --onefile --windowed ^
    --name "GitVersionManager" ^
    --icon "resources/icon.ico" ^
    --add-data "config.example.json;." ^
    main.py

echo.
echo Build complete!
echo Executable: dist\GitVersionManager.exe
echo.
echo Remember to create a "data" folder next to the exe for config.json
pause
