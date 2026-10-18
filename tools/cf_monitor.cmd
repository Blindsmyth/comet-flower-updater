@echo off
rem Double-click: CF Monitor (listen to the pedal's USB channels, meters, record, play files).
cd /d "%USERPROFILE%\Documents\zoom project"
start "" ".venv\Scripts\pythonw.exe" tools\cf_monitor.py
