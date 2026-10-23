@echo off
rem build_hiwatt_lite.bat: CF WattL bench. Renders effects/common/hiwatt_lite.h (2x) as build\host\hwl\L_*.f32.
rem The reference (ref_*) and the shipped CF Watt 2x (G_*) must already be in build\host\hwl:
rem   tests\host\build_hiwatt_accuracy.bat hwl /DHW_OS#2      (once, ~30 s)
rem Score: .venv\Scripts\python.exe tests\host\hiwatt_lite_score.py
set OUT=%~dp0..\..\build\host
set CF=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\tools\dsp_validate
if not exist "%OUT%\hwl\ref_noon_f440_a025.f32" (echo missing references: run build_hiwatt_accuracy.bat hwl /DHW_OS#2 first & exit /b 1)
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%CF%" /DHW_LITE /DHW_OS#2 "%~dp0hiwatt_accuracy.cpp" /Fe"%OUT%\hiwatt_lite.exe" /Fo"%OUT%\hiwatt_lite.obj" || exit /b 1
"%OUT%\hiwatt_lite.exe" "%OUT%\hwl"
