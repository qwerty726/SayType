@echo off
REM Build SayType into a distributable folder under dist\SayType\
REM Prerequisites: pip install pyinstaller
REM
REM First-time setup:
REM   pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
REM
REM The build can take 5-20 minutes depending on disk speed because torch
REM has thousands of files. Output exe: dist\SayType\SayType.exe

setlocal
cd /d "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [build] pyinstaller not found. Installing...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [build] pip install failed. Aborting.
        exit /b 1
    )
)

echo [build] Cleaning previous build outputs...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

echo [build] Running PyInstaller...
pyinstaller voice_input.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [build] FAILED. Common fixes:
    echo   - Missing hidden import: add it to extra_hidden in voice_input.spec
    echo   - DLL load errors: ensure torch/funasr installed in the same Python
    exit /b 1
)

echo.
echo [build] Done. Run:  dist\SayType\SayType.exe
echo [build] To distribute, zip the entire dist\SayType\ folder.
endlocal
