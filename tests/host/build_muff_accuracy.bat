@echo off
rem build_muff_accuracy.bat [folder] [--skip-ref]
rem Builds the CF Muff bench (includes Comet Flower's model code from the
rem VirtualPedalBoardEngine checkout) and writes outputs to build\host\<folder>.
set OUT=%~dp0..\..\build\host
set VPBE=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\Source
set DIR=%1
if "%DIR%"=="" set DIR=muff
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%VPBE%" /I"%VPBE%\MobileDsp" "%~dp0muff_accuracy.cpp" /Fe"%OUT%\muff_accuracy_%DIR%.exe" /Fo"%OUT%\muff_accuracy_%DIR%.obj" || exit /b 1
"%OUT%\muff_accuracy_%DIR%.exe" "%OUT%\%DIR%" %2
