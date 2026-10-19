@echo off
rem Builds and runs the CF Muff block-form equivalence test (muff_block vs muff_process, bit for bit).
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /fp:strict /std:c++17 /EHsc /I"%~dp0..\..\effects\common" "%~dp0muff_block_test.cpp" /Fe"%OUT%\muff_block_test.exe" /Fo"%OUT%\muff_block_test.obj" || exit /b 1
"%OUT%\muff_block_test.exe"
