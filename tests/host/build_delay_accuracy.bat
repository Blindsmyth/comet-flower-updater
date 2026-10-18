@echo off
rem build_delay_accuracy.bat: CF Delay core vs Comet Flower's DelayMobileCore (compiled from its source).
set OUT=%~dp0..\..\build\host
set REF=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\Source\MobileDsp
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%REF%" "%~dp0delay_accuracy.cpp" /Fe"%OUT%\delay_accuracy.exe" /Fo"%OUT%\delay_accuracy.obj" >nul || exit /b 1
"%OUT%\delay_accuracy.exe"
