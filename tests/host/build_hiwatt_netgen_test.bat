@echo off
rem Builds and runs the generated network derivation check (hiwatt_netgen.h vs double mna_derive).
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /c /Dfloat=double "%~dp0hiwatt_netgen_dbl.cpp" /Fo"%OUT%\hiwatt_netgen_dbl.obj" || exit /b 1
cl /nologo /O2 /std:c++17 /EHsc "%~dp0hiwatt_netgen_test.cpp" "%OUT%\hiwatt_netgen_dbl.obj" /Fe"%OUT%\hiwatt_netgen_test.exe" /Fo"%OUT%\hiwatt_netgen_test.obj" || exit /b 1
"%OUT%\hiwatt_netgen_test.exe"
