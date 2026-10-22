@echo off
rem 32-bit host test of the real CF Rotary kernel (effects\rotx\rotx.c). Needs the stomphacks build's sh_params.h.
set OUT=%~dp0..\..\build\host
set SHB=C:\Users\z\zoomlab\stomphacks\effects\rotx\build
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%~dp0..\..\effects\rotx" /I"%~dp0..\..\effects\common" /I"%SHB%" "%~dp0rotx_test.cpp" /Fe"%OUT%\rotx_test.exe" /Fo"%OUT%\rotx_test.obj" >nul || exit /b 1
"%OUT%\rotx_test.exe"
