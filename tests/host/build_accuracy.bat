@echo off
set OUT=%~dp0..\..\build\host
if not exist "%OUT%\acc" mkdir "%OUT%\acc"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0ts808_accuracy.cpp" /Fe"%OUT%\ts808_accuracy.exe" /Fo"%OUT%\\" >nul || exit /b 1
"%OUT%\ts808_accuracy.exe" "%OUT%\acc"
