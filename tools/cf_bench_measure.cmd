@echo off
rem Double-click: measure the CPU cost of the patch now active on the pedal (bench firmware, USB mode on).
cd /d "%USERPROFILE%\Documents\zoom project"
:again
set "LABEL="
set /p LABEL=What is on the pedal now (e.g. CF Dyna alone)? 
if "%LABEL%"=="" set "LABEL=current patch"
".venv\Scripts\python.exe" tools\ua_bench.py measure --seconds 4 --label "%LABEL%"
echo %DATE% %TIME% %LABEL%>> build\bench\manual_runs.txt
echo.
choice /m "Measure another patch"
if errorlevel 2 goto end
goto again
:end
pause
