# Mini-lenguaje de partituras

Proyecto de Teoría de Lenguajes Formales. Diseñamos un pequeño lenguaje para escribir música, lo formalizamos (alfabeto, AFD y gramática) y construimos en Python su analizador léxico, su analizador sintáctico y un intérprete que convierte el programa en audio.

**Equipo:** Derek Rodríguez, Sara Vergara y María José.

## Cómo ejecutarlo

Solo se necesita Python 3.8 o superior. No hay que instalar nada más.

- **Interfaz gráfica:** doble clic en `iniciar.bat` (Windows) o `python interfaz.py`.
- **Menú en la terminal:** `python main.py`.
- **Un archivo directamente:** `python main.py ejemplos/escala.part`.
- **Pruebas:** `python -m unittest discover -s pruebas -t .`

En VS Code basta con abrir `interfaz.py` y darle al botón ▶.

## Un ejemplo del lenguaje

```
entero vuelta = 1;
tempo 100;
mientras vuelta <= 4 hacer |
  tocar do4 1/4;
  tocar sol4 1/4;
  vuelta = vuelta + 1;
|
```

## Qué hay en el repositorio

- `lexico.py`: el analizador léxico, construido sobre la matriz del AFD de la Fase 1.
- `sintactico.py`: el parser, con una función por cada regla de la gramática de la Fase 2.
- `interprete.py`: ejecuta el programa y genera el audio `.wav`.
- `interfaz.py` y `main.py`: la interfaz gráfica y el menú de consola.
- `ejemplos/` y `errores/`: programas de prueba, válidos y con errores.
- `docs/`: los documentos de las Fases 1 y 2.
