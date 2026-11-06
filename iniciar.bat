@echo off
rem Doble clic para abrir la interfaz grafica del mini-lenguaje de partituras.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 interfaz.py
) else (
    python interfaz.py
)
if errorlevel 1 (
    echo.
    echo No se pudo abrir la interfaz. Verifica que Python 3 este instalado
    echo desde python.org y marcado "Add Python to PATH" durante la instalacion.
    pause
)
