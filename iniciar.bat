@echo off
rem Doble clic para abrir la interfaz grafica del mini-lenguaje de partituras.
rem Prueba varios interpretes y usa el primero que funcione y tenga tkinter
rem (evita fallar si "py" apunta a una instalacion de Python ya borrada).
cd /d "%~dp0"
setlocal

for %%P in ("py -3.13" "py -3.12" "py -3.11" "py -3.10" "py -3" "python" "python3") do (
    %%~P -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYCMD=%%~P"
        goto :encontrado
    )
)

echo.
echo No se encontro un Python 3 funcional con tkinter.
echo Instala Python 3 desde python.org y marca "Add Python to PATH"
echo y "tcl/tk and IDLE" durante la instalacion.
pause
exit /b 1

:encontrado
%PYCMD% interfaz.py
if errorlevel 1 (
    echo.
    echo La interfaz termino con un error ^(usando: %PYCMD%^).
    pause
)
