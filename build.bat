@echo off
REM Build SayType into a distributable folder under dist\SayType\
REM Prerequisites: pyinstaller will be auto-installed/upgraded.
REM
REM The build can take 5-20 minutes because torch has thousands of files.
REM Output exe: dist\SayType\SayType.exe

setlocal
cd /d "%~dp0"

echo [build] Ensuring pyinstaller is up-to-date...
pip install -U pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [build] pip install failed. Aborting.
    exit /b 1
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
    echo   - DLL load errors at runtime: install MS VC++ Redistributable 2015-2022 x64
    echo     https://aka.ms/vs/17/release/vc_redist.x64.exe
    exit /b 1
)

echo.
echo [build] Done. Run:  dist\SayType\SayType.exe
echo [build] If you get "DLL load failed", install VC++ Redistributable:
echo         https://aka.ms/vs/17/release/vc_redist.x64.exe
echo [build] To distribute, zip the entire dist\SayType\ folder.
endlocal
