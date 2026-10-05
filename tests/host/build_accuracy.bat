@echo off
rem build_accuracy.bat [folder] [extra cl flags, e.g. /DTSX_SOLVER=2]
rem Builds the bench and writes its outputs to build\host\<folder> (default acc).
set OUT=%~dp0..\..\build\host
set DIR=%1
if "%DIR%"=="" set DIR=acc
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc %2 %3 "%~dp0ts808_accuracy.cpp" /Fe"%OUT%\ts808_accuracy_%DIR%.exe" /Fo"%OUT%\ts808_accuracy_%DIR%.obj" >nul || exit /b 1
"%OUT%\ts808_accuracy_%DIR%.exe" "%OUT%\%DIR%"
