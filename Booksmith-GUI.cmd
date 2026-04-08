@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%dist\Booksmith-GUI\Booksmith-GUI.exe" (
    start "" /B "%ROOT%dist\Booksmith-GUI\Booksmith-GUI.exe"
    exit /b 0
)

if exist "%ROOT%dist\Booksmith-GUI.exe" (
    start "" /B "%ROOT%dist\Booksmith-GUI.exe"
    exit /b 0
)

rem Let module imports work even when the package is not installed globally.
set "PYTHONPATH=%ROOT%src;%PYTHONPATH%"

where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" /B pythonw -m booksmith.gui
    exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python -m booksmith.gui
    exit /b 0
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -m booksmith.gui
    exit /b 0
)

echo [Booksmith] Python runtime not found.
echo Install Python or activate your environment first.
pause
exit /b 1
