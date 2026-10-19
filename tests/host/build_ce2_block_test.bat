@echo off
rem Builds and runs the CF CE-2 block-form equivalence test (ce2_block vs ce2_process, bit for bit).
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /fp:strict /std:c++17 /EHsc /I"%~dp0..\..\effects\common" "%~dp0ce2_block_test.cpp" /Fe"%OUT%\ce2_block_test.exe" /Fo"%OUT%\ce2_block_test.obj" || exit /b 1
"%OUT%\ce2_block_test.exe"
