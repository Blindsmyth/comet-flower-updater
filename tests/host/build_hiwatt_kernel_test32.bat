@echo off
rem 32-bit build of the DR103 kernel host test: the work-buffer descriptor holds 32-bit addresses, as on the pedal.
rem Needs the stomphacks build's sh_params.h (run tools/build_g1.sh hiwatt first).
set OUT=%~dp0..\..\build\host
set SHB=C:\Users\z\zoomlab\stomphacks\effects\hiwatt\build
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%~dp0..\..\effects\hiwatt" /I"%~dp0..\..\effects\common" /I"%SHB%" "%~dp0hiwatt_kernel_test.cpp" /Fe"%OUT%\hiwatt_kernel_test32.exe" /Fo"%OUT%\hiwatt_kernel_test32.obj" || exit /b 1
"%OUT%\hiwatt_kernel_test32.exe"
