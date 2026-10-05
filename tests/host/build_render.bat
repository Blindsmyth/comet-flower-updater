@echo off
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /EHsc "%~dp0drv808_render.cpp" /Fe"%OUT%\drv808_render.exe" /Fo"%OUT%\\" >nul || exit /b 1
echo built %OUT%\drv808_render.exe
