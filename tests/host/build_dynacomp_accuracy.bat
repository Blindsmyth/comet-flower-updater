@echo off
rem build_dynacomp_accuracy.bat [folder] [--skip-ref]
rem Builds the CF Dyna Comp bench and writes outputs to build\host\<folder>
rem (default dynacomp). --skip-ref reuses existing reference/input files (they
rem depend only on this bench, not on the candidate header).
set OUT=%~dp0..\..\build\host
set DIR=%1
if "%DIR%"=="" set DIR=dynacomp
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0dynacomp_accuracy.cpp" /Fe"%OUT%\dynacomp_accuracy_%DIR%.exe" /Fo"%OUT%\dynacomp_accuracy_%DIR%.obj" >nul || exit /b 1
"%OUT%\dynacomp_accuracy_%DIR%.exe" "%OUT%\%DIR%" %2
