@echo off
rem 32-bit host test of the real CF RA200 kernel (effects\ra200x\ra200x.c). Needs the stomphacks build's sh_params.h.
set OUT=%~dp0..\..\build\host
set SHB=C:\Users\z\zoomlab\stomphacks\effects\ra200x\build
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /D_USE_MATH_DEFINES /I"%~dp0..\..\effects\ra200x" /I"%~dp0..\..\effects\common" /I"%SHB%" "%~dp0ra200_test.cpp" /Fe"%OUT%\ra200_test.exe" /Fo"%OUT%\ra200_test.obj" || exit /b 1
"%OUT%\ra200_test.exe"
