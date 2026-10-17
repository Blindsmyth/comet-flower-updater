@echo off
rem build_mistress_accuracy.bat [folder] [--skip-ref]
rem Builds the CF Mistress bench and writes outputs to build\host\<folder>
rem (default mistress). --skip-ref reuses existing reference files (they
rem depend only on this bench, not on the candidate header).
set OUT=%~dp0..\..\build\host
set DIR=%1
if "%DIR%"=="" set DIR=mistress
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0mistress_accuracy.cpp" /Fe"%OUT%\mistress_accuracy_%DIR%.exe" /Fo"%OUT%\mistress_accuracy_%DIR%.obj" >nul || exit /b 1
"%OUT%\mistress_accuracy_%DIR%.exe" "%OUT%\%DIR%" %2
