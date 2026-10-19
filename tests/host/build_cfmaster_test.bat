@echo off
rem 32-bit host test of the CF Master kernel (effects\cfmaster\cfmaster.c).
set OUT=%~dp0..\..\build\host
set SHB=C:\Users\z\zoomlab\stomphacks\effects\ra200x\build
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /D_USE_MATH_DEFINES /I"%~dp0..\..\effects\cfmaster" /I"%~dp0..\..\effects\common" /I"%~dp0." /I"%SHB%" "%~dp0cfmaster_test.cpp" /Fe"%OUT%\cfmaster_test.exe" /Fo"%OUT%\cfmaster_test.obj" || exit /b 1
"%OUT%\cfmaster_test.exe"
