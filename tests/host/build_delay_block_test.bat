@echo off
rem Builds and runs the CF Delay block-form equivalence test (delay_block vs delay_process, bit for bit).
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /fp:strict /std:c++17 /EHsc /I"%~dp0..\..\effects\common" "%~dp0delay_block_test.cpp" /Fe"%OUT%\delay_block_test.exe" /Fo"%OUT%\delay_block_test.obj" || exit /b 1
"%OUT%\delay_block_test.exe"
