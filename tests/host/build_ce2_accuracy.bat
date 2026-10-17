@echo off
rem build_ce2_accuracy.bat [folder] [--skip-ref]
rem Builds the CF CE-2 bench and writes outputs to build\host\<folder>
rem (default ce2). --skip-ref reuses existing reference files (they depend
rem only on this bench, not on the candidate header).
set OUT=%~dp0..\..\build\host
set DIR=%1
if "%DIR%"=="" set DIR=ce2
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0ce2_accuracy.cpp" /Fe"%OUT%\ce2_accuracy_%DIR%.exe" /Fo"%OUT%\ce2_accuracy_%DIR%.obj" >nul || exit /b 1
"%OUT%\ce2_accuracy_%DIR%.exe" "%OUT%\%DIR%" %2
