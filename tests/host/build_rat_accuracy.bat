@echo off
rem build_rat_accuracy.bat [folder] [--skip-ref]
rem Builds the CF RAT bench and writes outputs to build\host\<folder> (default rat).
rem --skip-ref reuses existing reference files (they depend only on this bench).
set OUT=%~dp0..\..\build\host
set DIR=%1
if "%DIR%"=="" set DIR=rat
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0rat_accuracy.cpp" /Fe"%OUT%\rat_accuracy_%DIR%.exe" /Fo"%OUT%\rat_accuracy_%DIR%.obj" >nul || exit /b 1
"%OUT%\rat_accuracy_%DIR%.exe" "%OUT%\%DIR%" %2
