"""
Punto de entrada del analizador del mini-lenguaje de partituras.

Sin argumentos abre un menú interactivo en la terminal:
    python main.py

Con un archivo, funciona como herramienta de línea de comandos:
    python main.py <archivo.part> [opciones]

Opciones:
    --tokens          muestra la secuencia de tokens producida por el lexer
    --dot ARCHIVO     guarda el árbol de derivación en formato Graphviz (.dot)
    --ejecutar        ejecuta el programa con el intérprete (extra)
    --wav ARCHIVO     ruta del audio generado (por defecto, la carpeta salidas/)
    --sin-arbol       no imprime el árbol (útil junto con --ejecutar)

Salida: el árbol de derivación sintáctica, o el listado de errores
léxicos y sintácticos con su línea y columna.
"""

import argparse
import sys
import unittest
from pathlib import Path

from sintactico import analizar, arbol_a_texto, arbol_a_dot
from interprete import Interprete, ErrorEjecucion

CARPETA = Path(__file__).resolve().parent
EJEMPLOS = CARPETA / "ejemplos"
ERRORES = CARPETA / "errores"
SALIDAS = CARPETA / "salidas"


def configurar_consola():
    # Permite imprimir ├── └── ♪ y tildes también en la consola de Windows.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Modo línea de comandos
# ---------------------------------------------------------------------------

def main(argv=None):
    configurar_consola()
    opciones = argparse.ArgumentParser(
        description="Analizador léxico, sintáctico e intérprete del mini-lenguaje de partituras.")
    opciones.add_argument("archivo", help="programa fuente del mini-lenguaje")
    opciones.add_argument("--tokens", action="store_true", help="mostrar los tokens")
    opciones.add_argument("--dot", metavar="ARCHIVO", help="guardar el árbol en formato Graphviz")
    opciones.add_argument("--ejecutar", action="store_true", help="ejecutar el programa")
    opciones.add_argument("--wav", metavar="ARCHIVO", help="ruta del audio generado")
    opciones.add_argument("--sin-arbol", action="store_true", help="no imprimir el árbol")
    args = opciones.parse_args(argv)

    ruta = Path(args.archivo)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"No se encontró el archivo: {ruta}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print(f"El archivo {ruta} no está guardado en UTF-8", file=sys.stderr)
        return 2

    arbol, tokens, errores_lexicos, errores_sintacticos = analizar(texto)

    if args.tokens:
        print("=== Tokens ===")
        print(" ".join(str(t) for t in tokens))
        print()

    if errores_lexicos or errores_sintacticos:
        total = len(errores_lexicos) + len(errores_sintacticos)
        print(f"=== Se encontraron {total} error(es) ===")
        for error in errores_lexicos + errores_sintacticos:
            print(error)
        if errores_lexicos:
            print("\n(El análisis sintáctico no se ejecuta mientras haya errores léxicos.)")
        return 1

    if not args.sin_arbol:
        print("=== Árbol de derivación sintáctica ===")
        print("\n".join(arbol_a_texto(arbol)))

    if args.dot:
        Path(args.dot).write_text(arbol_a_dot(arbol), encoding="utf-8")
        print(f"\nÁrbol guardado en formato Graphviz en: {args.dot}")

    if args.ejecutar:
        print("\n=== Ejecución ===")
        interprete = Interprete()
        try:
            interprete.ejecutar(arbol)
        except ErrorEjecucion as error:
            print(error)
            return 1
        if interprete.audio:
            if args.wav:
                destino = Path(args.wav)
            else:
                SALIDAS.mkdir(exist_ok=True)
                destino = SALIDAS / (ruta.stem + ".wav")
            segundos = interprete.guardar_wav(destino)
            print(f"\nAudio generado: {destino} ({segundos:.1f} s)")
        else:
            print("\n(El programa no tocó ninguna nota: no se generó audio.)")

    return 0


# ---------------------------------------------------------------------------
# Modo menú (python main.py sin argumentos)
# ---------------------------------------------------------------------------

def _elegir_archivo(carpeta, titulo):
    archivos = sorted(carpeta.glob("*.part"))
    print(f"\n{titulo}:")
    for numero, archivo in enumerate(archivos, 1):
        print(f"  {numero:>2}. {archivo.name}")
    print("   0. Volver")
    while True:
        eleccion = input("Número del archivo: ").strip()
        if eleccion == "0" or eleccion == "":
            return None
        if eleccion.isdigit() and 1 <= int(eleccion) <= len(archivos):
            return archivos[int(eleccion) - 1]
        print("  Opción no válida, intenta de nuevo.")


def _pedir_ruta():
    texto = input("\nRuta del archivo (puedes arrastrarlo a la terminal): ").strip()
    texto = texto.strip('"').strip("'")          # "Copiar como ruta" de Windows agrega comillas
    if not texto:
        return None
    ruta = Path(texto).expanduser()
    if not ruta.is_absolute() and not ruta.exists():
        ruta = CARPETA / ruta
    return ruta


def _correr_pruebas():
    cargador = unittest.TestLoader()
    suite = cargador.discover(start_dir=str(CARPETA / "pruebas"), top_level_dir=str(CARPETA))
    resultado = unittest.TextTestRunner(verbosity=1).run(suite)
    print("\n✓ Todas las pruebas pasaron." if resultado.wasSuccessful()
          else "\n✗ Algunas pruebas fallaron.")


def _abrir_interfaz():
    try:
        import interfaz
    except SystemExit:                        # interfaz.py sale si no hay tkinter
        return
    interfaz.iniciar()


OPCIONES_MENU = [
    ("1", "Abrir la interfaz gráfica"),
    ("2", "Ver el árbol de derivación de un ejemplo"),
    ("3", "Ver los tokens y el árbol de un ejemplo"),
    ("4", "Ejecutar un ejemplo y generar el audio .wav"),
    ("5", "Probar un programa con errores"),
    ("6", "Analizar un archivo propio"),
    ("7", "Correr las pruebas automáticas"),
    ("0", "Salir"),
]


def menu():
    configurar_consola()
    while True:
        print("\n" + "=" * 52)
        print("   Mini-lenguaje de partituras · Teoría de Lenguajes")
        print("=" * 52)
        for clave, texto in OPCIONES_MENU:
            print(f"  {clave}. {texto}")
        try:
            eleccion = input("\nElige una opción: ").strip()
            if eleccion == "0":
                print("¡Hasta luego!")
                return 0
            if eleccion == "1":
                _abrir_interfaz()
                continue
            if eleccion == "2":
                archivo = _elegir_archivo(EJEMPLOS, "Programas de ejemplo")
                argumentos = [] if archivo is None else [str(archivo)]
            elif eleccion == "3":
                archivo = _elegir_archivo(EJEMPLOS, "Programas de ejemplo")
                argumentos = [] if archivo is None else [str(archivo), "--tokens"]
            elif eleccion == "4":
                archivo = _elegir_archivo(EJEMPLOS, "Programas de ejemplo")
                argumentos = [] if archivo is None else [str(archivo), "--sin-arbol", "--ejecutar"]
            elif eleccion == "5":
                archivo = _elegir_archivo(ERRORES, "Programas con errores")
                argumentos = [] if archivo is None else [str(archivo)]
            elif eleccion == "6":
                ruta = _pedir_ruta()
                argumentos = [] if ruta is None else [str(ruta)]
            elif eleccion == "7":
                _correr_pruebas()
                argumentos = None
            else:
                print("  Opción no válida.")
                continue

            if argumentos:
                print()
                main(argumentos)
            if argumentos is None or argumentos:
                input("\nPresiona Enter para volver al menú...")
        except (KeyboardInterrupt, EOFError):
            print("\n¡Hasta luego!")
            return 0


if __name__ == "__main__":
    sys.exit(main() if len(sys.argv) > 1 else menu())
