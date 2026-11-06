# Mini-lenguaje de partituras · Fase 3

Analizador léxico, analizador sintáctico e intérprete del mini-lenguaje de
partituras, en Python 3.8 o superior, **sin librerías externas**.

El programa lee un archivo de texto con código del mini-lenguaje y genera el
**árbol de derivación sintáctica** o el **listado de errores** léxicos y
sintácticos con su línea y columna. Como extra, puede ejecutar el programa y
generar un archivo `.wav` con la música.

## Cómo ejecutarlo

Solo se necesita **Python 3.8 o superior** (de python.org). No hay que instalar nada más.

### Opción 1: la interfaz gráfica (la más cómoda)

- **Windows:** doble clic en `iniciar.bat`.
- **VS Code:** abre la carpeta `proyecto_dsl`, abre `interfaz.py` y presiona el botón **▶** (Run Python File) de la esquina superior derecha.
- **Terminal:** `python interfaz.py` (en macOS o Linux también `sh iniciar.sh`).

En la ventana:

| Botón o atajo | Qué hace |
| --- | --- |
| **▶ Analizar** (F5) | Muestra los tokens y el árbol de derivación, o los errores con su línea |
| **♪ Ejecutar y escuchar** (F6) | Corre el programa con el intérprete y reproduce la música |
| Menú **Ejemplos** | Carga cualquiera de los programas válidos o con errores |
| Clic en un nodo del árbol | Resalta en el editor el código que ese nodo deriva |
| Doble clic en un token o un error | Lleva el cursor a esa posición del código |

El editor colorea el código con el propio lexer del proyecto, y el audio queda en la carpeta `salidas/`.

### Opción 2: el menú en la terminal

```
python main.py
```

Sin argumentos muestra un menú numerado: ver el árbol o los tokens de un ejemplo,
ejecutarlo con audio, probar los programas con errores, analizar un archivo propio
o correr las pruebas. También es lo que aparece al darle **▶** a `main.py` en VS Code.

### Opción 3: VS Code con F5

La carpeta `.vscode` trae configuraciones listas. En la pestaña **Ejecutar y depurar**
(Ctrl+Shift+D) se elige una en la lista y se presiona F5:

1. Interfaz gráfica
2. Menú en la terminal
3. Analizar el archivo `.part` abierto (abre primero un `.part` en el editor)
4. Ejecutar el archivo `.part` abierto, con audio
5. Pruebas automáticas

Las pruebas también aparecen en el panel **Testing** (ícono de matraz) de VS Code.

### Opción 4: línea de comandos directa

```
python main.py ejemplos/tempo_acelera.part
python main.py ejemplos/tempo_acelera.part --tokens
python main.py ejemplos/escala.part --ejecutar
python main.py errores/11_varios_errores.part
```

| Opción | Qué hace |
| --- | --- |
| `--tokens` | Muestra la secuencia de tokens que produce el lexer |
| `--dot arbol.dot` | Guarda el árbol en formato Graphviz (se puede ver en graphviz.online) |
| `--ejecutar` | Ejecuta el programa con el intérprete y genera el `.wav` en `salidas/` |
| `--wav salida.wav` | Cambia la ruta del audio generado |
| `--sin-arbol` | No imprime el árbol (útil junto con `--ejecutar`) |

Pruebas automáticas (50 casos), desde la carpeta del proyecto:

```
python -m unittest discover -s pruebas -t .
```

> En Windows, si `python` no se reconoce, usa `py` en su lugar (por ejemplo `py main.py`).

## Estructura

```
proyecto_dsl/
├── lexico.py          Fase 1: alfabeto, clases, matriz δ del AFD y lexer
├── sintactico.py      Fase 2: parser descendente recursivo LL(1) y árbol
├── interprete.py      Extra: ejecución y audio .wav
├── interfaz.py        Interfaz gráfica (tkinter, incluido en Python)
├── main.py            Menú en la terminal y línea de comandos
├── iniciar.bat        Doble clic para abrir la interfaz en Windows
├── iniciar.sh         Lo mismo en macOS / Linux
├── .vscode/           Configuraciones de VS Code (F5 y pruebas)
├── ejemplos/          Programas válidos (los tres de la Fase 1)
├── errores/           Un programa por cada caso de error
├── pruebas/           Pruebas unittest del lexer, el parser y el intérprete
└── salidas/           Audios y árboles generados (se crea al ejecutar)
```

## Cómo se conecta el código con las Fases 1 y 2

### `lexico.py` ↔ Fase 1

| Elemento de la Fase 1 | En el código |
| --- | --- |
| Alfabeto Σ = L ∪ D ∪ S ∪ B (sección 2) | `LETRAS`, `DIGITOS`, `SIMBOLOS`, `BLANCOS` |
| 15 clases de caracteres (sección 5.1) | `clase_de()` y `CLASES` |
| Matriz de transiciones δ (sección 6) | `_FILAS` / `TRANSICIONES` y `delta()` |
| 14 estados de aceptación (sección 5.2) | `ACEPTACION` |
| Clasificación R / N / ID (sección 4) | `RESERVADAS`, `NOTAS`, `clasificar()` |
| Coincidencia más larga (sección 5.3) | ciclo de `Lexer.tokenizar()` con `ultimo_aceptado` |
| Estados de rechazo q3, q5, q10 (sección 7) | `_MENSAJE_RECHAZO` |
| Trazas paso a paso (sección 8) | `recorrido("si4")` → `['q0', 'q1', 'q1', 'q1']` |

El lexer **no usa expresiones regulares de Python**: recorre la tabla carácter
por carácter, igual que el AFD dibujado en la Fase 1. Si se cambia una celda
de `_FILAS`, cambia el comportamiento del lexer.

### `sintactico.py` ↔ Fase 2

Cada no terminal de la gramática final es una función con el mismo nombre, y
cada alternativa se elige con los conjuntos PRIMERO y SIGUIENTE (sección 8).

| No terminal | Función | Reglas |
| --- | --- | --- |
| `<programa>` | `programa()` | 1 |
| `<lista_instr>` | `lista_instr()` | 2, 3 |
| `<instruccion>` | `instruccion()` | 4 a 11 |
| `<declaracion>` | `declaracion()` | 12 |
| `<decl_resto>` | `decl_resto()` | 13, 14 |
| `<tipo>` | `tipo()` | 15 a 18 |
| `<asignacion>` | `asignacion()` | 19 |
| `<tocar_instr>` | `tocar_instr()` | 20 |
| `<silencio_instr>` | `silencio_instr()` | 21 |
| `<tempo_instr>` | `tempo_instr()` | 22 |
| `<mostrar_instr>` | `mostrar_instr()` | 23 |
| `<lista_args>` | `lista_args()` | 24 |
| `<args_resto>` | `args_resto()` | 25, 26 |
| `<condicional>` | `condicional()` | 27 |
| `<sino_parte>` | `sino_parte()` | 28, 29 |
| `<ciclo>` | `ciclo()` | 30 |
| `<bloque>` | `bloque()` | 31 |
| `<expresion>` | `expresion()` | 32 |
| `<rel_resto>` | `rel_resto()` | 33, 34 |
| `<op_rel>` | `op_rel()` | 35 a 40 |
| `<expr_arit>` | `expr_arit()` | 41 |
| `<expr_arit'>` | `expr_arit_prima()` | 42 a 44 |
| `<termino>` | `termino()` | 45 |
| `<termino'>` | `termino_prima()` | 46 a 48 |
| `<factor>` | `factor()` | 49 a 57 |

Ejemplo de cómo una regla se vuelve código:

```
Regla 28: <sino_parte> ::= sino <bloque>
Regla 29:                | ε
```

```python
def sino_parte(self):
    if self.actual.tipo == "sino":          # PRIMERO(sino <bloque>) = {sino}
        nodo = Nodo("<sino_parte>")
        nodo.agregar(self.coincidir("sino"))
        nodo.agregar(self.bloque())
        return nodo
    return vacio("<sino_parte>")            # ε
```

### Manejo de errores

- **Léxicos:** los detecta el AFD (carácter fuera de Σ, cadena sin cerrar,
  decimal incompleto, `!` suelto). Si hay errores léxicos, el parser no se ejecuta.
- **Sintácticos:** el parser compara el token actual con lo que exige la regla
  (Fase 2, sección 10). Tras un error usa **recuperación en modo pánico**: salta
  tokens hasta un punto seguro (`;`, una palabra que inicia instrucción, `|` o el
  fin del archivo) para poder reportar varios errores en una sola ejecución.
- **De ejecución (intérprete):** variable no declarada, tipos incompatibles,
  condición no booleana, división entre cero, duración no positiva.

## El intérprete (extra)

- Una duración se mide en redondas: `1/4` es una negra.
- `tempo` fija las negras por minuto (inicial: 120).
- `la4` = 440 Hz; las demás notas se calculan en escala temperada.
- `/` siempre produce un decimal (`1/4` = 0.25), así que no se puede guardar en una variable `entero`.
- Las condiciones de `si` y `mientras` deben ser booleanas.
- El audio se genera con los módulos estándar `wave`, `struct` y `math`.
