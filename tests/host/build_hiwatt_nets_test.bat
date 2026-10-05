@echo off
rem Builds and runs the Hiwatt network check against Comet Flower's desktop builders.
set OUT=%~dp0..\..\build\host
set CF=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\tools\dsp_validate
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%CF%" "%~dp0hiwatt_nets_test.cpp" /Fe"%OUT%\hiwatt_nets_test.exe" /Fo"%OUT%\hiwatt_nets_test.obj" || exit /b 1
"%OUT%\hiwatt_nets_test.exe"
