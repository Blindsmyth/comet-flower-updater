@echo off
rem Builds the offline A/B renders (32-bit, as the pedal: the work-buffer descriptor holds 32-bit addresses).
rem Needs the stomphacks builds' sh_params.h (tools/build_g1.sh cftone / hiwatt first).
set OUT=%~dp0..\..\build\host
set SH=C:\Users\z\zoomlab\stomphacks\effects
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /DAB_TONE /I"%~dp0..\..\effects\cftone" /I"%SH%\cftone\build" "%~dp0ab_render.cpp" /Fe"%OUT%\cftone_render.exe" /Fo"%OUT%\ab_tone.obj" >nul || exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DHW_OS=4 /I"%~dp0..\..\effects\hiwatt" /I"%~dp0..\..\effects\common" /I"%SH%\hiwatt\build" "%~dp0ab_render.cpp" /Fe"%OUT%\hiwatt_render_os4.exe" /Fo"%OUT%\ab_os4.obj" >nul || exit /b 1
cl /nologo /O2 /std:c++17 /EHsc /DHW_OS=2 /I"%~dp0..\..\effects\hiwatt" /I"%~dp0..\..\effects\common" /I"%SH%\hiwatt\build" "%~dp0ab_render.cpp" /Fe"%OUT%\hiwatt_render_os2.exe" /Fo"%OUT%\ab_os2.obj" >nul || exit /b 1
echo built cftone_render, hiwatt_render_os4, hiwatt_render_os2 in %OUT%
