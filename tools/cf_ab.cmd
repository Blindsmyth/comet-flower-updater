@echo off
rem Double-click: A/B two patches with the CF Tone test program (tools/ua_ab.py), then open the graphs.
cd /d "%USERPROFILE%\Documents\zoom project"
echo Patch A: CF Tone in slot 1, the first version (e.g. CF Watt) in slot 2.
pause
".venv\Scripts\python.exe" tools\ua_ab.py capture A
echo.
echo Patch B: CF Tone in slot 1, the second version (e.g. CF Watt2x) in slot 2, same knobs.
pause
".venv\Scripts\python.exe" tools\ua_ab.py capture B
".venv\Scripts\python.exe" tools\ua_ab.py compare build\ab\A.wav build\ab\B.wav --out build\ab\report
start "" "build\ab\report\ab_report.png"
start "" "build\ab\report\ab_sweep.png"
pause
