@echo off
rem Regenerates effects\common\hiwatt_cab.h from Comet Flower's CabSimMath.h.
set OUT=%~dp0..\build\host
set CF=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\Source
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%CF%" "%~dp0gen_fane_cab.cpp" /Fe"%OUT%\gen_fane_cab.exe" /Fo"%OUT%\gen_fane_cab.obj" >nul || exit /b 1
"%OUT%\gen_fane_cab.exe" "%~dp0..\effects\common\hiwatt_cab.h"
