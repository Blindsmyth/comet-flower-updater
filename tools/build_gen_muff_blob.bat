@echo off
rem Rebuilds and runs tools/gen_muff_blob.cpp against VirtualPedalBoardEngine's current
rem VioletSpecs/ToneStackMath (picks up the 2026-10-24 C10 fix). Must run from the repo
rem root: it writes effects/common/muff_blob.h and effects/muffx/blob.bin as relative paths.
set VPBE=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\Source
set OUT=build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%VPBE%" "tools\gen_muff_blob.cpp" /Fe"%OUT%\gen_muff_blob.exe" /Fo"%OUT%\gen_muff_blob.obj" || exit /b 1
"%OUT%\gen_muff_blob.exe"
