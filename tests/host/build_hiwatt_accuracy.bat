@echo off
rem build_hiwatt_accuracy.bat [folder] [extra cl flags]: build + run the bench into build\host\<folder> (default hw)
set OUT=%~dp0..\..\build\host
set CF=C:\Users\z\Documents\exhboost\VirtualPedalBoardEngine\tools\dsp_validate
set DIR=%1
if "%DIR%"=="" set DIR=hw
if not exist "%OUT%\%DIR%" mkdir "%OUT%\%DIR%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
cl /nologo /O2 /std:c++17 /EHsc /I"%CF%" %2 %3 %4 %5 "%~dp0hiwatt_accuracy.cpp" /Fe"%OUT%\hiwatt_accuracy_%DIR%.exe" /Fo"%OUT%\hiwatt_accuracy_%DIR%.obj" || exit /b 1
rem set HW_VARIANTS=variants to also write the double chain at 4x / 8x (R4_, R8_)
"%OUT%\hiwatt_accuracy_%DIR%.exe" "%OUT%\%DIR%" %HW_VARIANTS%
