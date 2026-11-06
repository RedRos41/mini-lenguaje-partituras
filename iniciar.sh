#!/bin/sh
# Abre la interfaz gráfica del mini-lenguaje de partituras (macOS / Linux).
# Uso: sh iniciar.sh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    python3 interfaz.py
else
    python interfaz.py
fi
