@echo off
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%~dp0..\..\effects\common" "%~dp0tsx_block_test.cpp" /Fe"%OUT%\tsx_block_test.exe" /Fo"%OUT%\tsx_block_test.obj" || exit /b 1
"%OUT%\tsx_block_test.exe"
