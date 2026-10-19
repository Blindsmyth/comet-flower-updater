@echo off
rem Builds and runs the CF Dyna block-form equivalence test (dynacomp_block vs dynacomp_process, bit for bit).
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /fp:strict /std:c++17 /EHsc /I"%~dp0..\..\effects\common" "%~dp0dynacomp_block_test.cpp" /Fe"%OUT%\dynacomp_block_test.exe" /Fo"%OUT%\dynacomp_block_test.obj" || exit /b 1
"%OUT%\dynacomp_block_test.exe"
