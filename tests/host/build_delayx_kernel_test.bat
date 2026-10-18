@echo off
rem 32-bit host test of the real CF Delay kernel (effects\delayx\delayx.c). Needs the stomphacks build's sh_params.h.
set OUT=%~dp0..\..\build\host
set SHB=C:\Users\z\zoomlab\stomphacks\effects\delayx\build
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%~dp0..\..\effects\delayx" /I"%~dp0..\..\effects\common" /I"%SHB%" "%~dp0delayx_kernel_test.cpp" /Fe"%OUT%\delayx_kernel_test.exe" /Fo"%OUT%\delayx_kernel_test.obj" >nul || exit /b 1
"%OUT%\delayx_kernel_test.exe"
