@echo off
rem Builds and runs the DR103 knob-table resolution study (hiwatt_tables_test.cpp).
set OUT=%~dp0..\..\build\host
if not exist "%OUT%" mkdir "%OUT%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc "%~dp0hiwatt_tables_test.cpp" /Fe"%OUT%\hiwatt_tables_test.exe" /Fo"%OUT%\hiwatt_tables_test.obj" || exit /b 1
"%OUT%\hiwatt_tables_test.exe" %*
