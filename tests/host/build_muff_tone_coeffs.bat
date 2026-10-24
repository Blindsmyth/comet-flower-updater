@echo off
rem Builds and runs muff_tone_coeffs.cpp: dumps CF Muff's real tone-stage biquad
rem coefficients across the Tone knob range. No VPBE dependency (unlike
rem build_muff_accuracy.bat) -- muff_g1.h is self-contained within effects/common.
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0muff_tone_coeffs.cpp" /Fe"%OUT%\muff_tone_coeffs.exe" /Fo"%OUT%\muff_tone_coeffs.obj" || exit /b 1
"%OUT%\muff_tone_coeffs.exe" > "%OUT%\muff_tone_coeffs.txt"
type "%OUT%\muff_tone_coeffs.txt"
