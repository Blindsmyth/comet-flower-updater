@echo off
rem Builds and runs the TS808 port comparison with MSVC.
set CF=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\Source
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /nologo /O2 /std:c++17 /EHsc /D_USE_MATH_DEFINES /I"%CF%" "%~dp0drv808_compare.cpp" /Fe"%OUT%\drv808_compare.exe" /Fo"%OUT%\\" || exit /b 1
"%OUT%\drv808_compare.exe"
