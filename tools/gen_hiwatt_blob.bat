@echo off
rem Regenerates effects\common\hw_blob.h and effects\{hiwatt,dr103diag}\blob.bin.
set OUT=%~dp0..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0gen_hiwatt_blob.cpp" /Fe"%OUT%\gen_hiwatt_blob.exe" /Fo"%OUT%\gen_hiwatt_blob.obj" >nul || exit /b 1
"%OUT%\gen_hiwatt_blob.exe" "%~dp0.."
