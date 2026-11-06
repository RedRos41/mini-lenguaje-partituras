"""Pruebas del analizador sintáctico contra lo definido en la Fase 2."""

import unittest
from pathlib import Path

from sintactico import analizar, arbol_a_texto

RAIZ = Path(__file__).resolve().parent.parent


def errores_de(texto):
    _, _, lexicos, sintacticos = analizar(texto)
    return [str(e) for e in lexicos + sintacticos]


def hojas(nodo):
    """Terminales del árbol leídos de izquierda a derecha (sin ε)."""
    if nodo.es_terminal():
        return [nodo.token.lexema]
    resultado = []
    for hijo in nodo.hijos:
        resultado.extend(hojas(hijo))
    return resultado


ARBOL_TOCAR = """\
<programa>
├── <lista_instr>
│   ├── <instruccion>
│   │   ├── <tocar_instr>
│   │   │   ├── tocar
│   │   │   ├── NOTA (si4)
│   │   │   └── <expresion>
│   │   │       ├── <expr_arit>
│   │   │       │   ├── <termino>
│   │   │       │   │   ├── <factor>
│   │   │       │   │   │   └── NUM_ENT (1)
│   │   │       │   │   └── <termino'>
│   │   │       │   │       ├── /
│   │   │       │   │       ├── <factor>
│   │   │       │   │       │   └── NUM_ENT (4)
│   │   │       │   │       └── <termino'>
│   │   │       │   │           └── ε
│   │   │       │   └── <expr_arit'>
│   │   │       │       └── ε
│   │   │       └── <rel_resto>
│   │   │           └── ε
│   │   └── ;
│   └── <lista_instr>
│       └── ε
└── $"""


class ProgramasValidos(unittest.TestCase):
    def test_ejemplos_sin_errores(self):
        for archivo in sorted((RAIZ / "ejemplos").glob("*.part")):
            with self.subTest(archivo=archivo.name):
                self.assertEqual(errores_de(archivo.read_text(encoding="utf-8")), [])

    def test_arbol_de_la_fase_2_seccion_9_2(self):
        arbol, *_ = analizar("tocar si4 1/4;")
        self.assertEqual("\n".join(arbol_a_texto(arbol)), ARBOL_TOCAR)

    def test_las_hojas_reconstruyen_la_entrada(self):
        arbol, *_ = analizar("vuelta = vuelta + 1;")
        self.assertEqual(hojas(arbol), ["vuelta", "=", "vuelta", "+", "1", ";", "$"])

    def test_declaracion_sin_valor(self):
        self.assertEqual(errores_de("entero x;"), [])

    def test_si_sin_sino_y_anidado(self):
        programa = ("booleano a = verdadero; booleano b = falso;\n"
                    "si a entonces | si b entonces | tocar do4 1/4; | | "
                    "sino | silencio 1/4; |")
        self.assertEqual(errores_de(programa), [])

    def test_bloque_vacio(self):
        self.assertEqual(errores_de("booleano a = falso; mientras a hacer | |"), [])

    def test_menos_unario_y_parentesis(self):
        self.assertEqual(errores_de("entero x = -(3 + 2) * -1;"), [])

    def test_programa_vacio(self):
        self.assertEqual(errores_de("# solo un comentario\n"), [])


class Precedencia(unittest.TestCase):
    def test_multiplicacion_queda_debajo_de_la_suma(self):
        # vuelta + 1 * 2: el '*' debe quedar dentro del <termino> derecho del '+'
        arbol, *_ = analizar("x = a + 1 * 2;")
        texto = "\n".join(arbol_a_texto(arbol))
        posicion_suma = texto.index("── +")
        posicion_mult = texto.index("── *")
        self.assertLess(posicion_suma, posicion_mult)


class ErroresSintacticos(unittest.TestCase):
    CASOS = {
        "01_falta_punto_y_coma.part": "se esperaba ';' al final de la declaración",
        "04_nota_invalida.part": "'do9' no es una nota válida",
        "05_barra_sin_bloque.part": "barra '|' de cierre sin un bloque abierto",
        "06_relacionales_encadenados.part": "no se pueden encadenar",
        "07_falta_hacer.part": "se esperaba 'hacer'",
        "08_falta_duracion.part": "falta la duración de la nota",
        "09_bloque_sin_cerrar.part": "falta la barra '|' que cierra el bloque",
    }

    def test_cada_error_produce_un_solo_mensaje(self):
        for nombre, esperado in self.CASOS.items():
            with self.subTest(archivo=nombre):
                texto = (RAIZ / "errores" / nombre).read_text(encoding="utf-8")
                errores = errores_de(texto)
                self.assertEqual(len(errores), 1, errores)
                self.assertIn(esperado, errores[0])

    def test_varios_errores_independientes(self):
        texto = (RAIZ / "errores" / "11_varios_errores.part").read_text(encoding="utf-8")
        self.assertEqual(len(errores_de(texto)), 4)

    def test_errores_lexicos_detienen_el_parser(self):
        for nombre in ("02_cadena_sin_cerrar.part", "03_simbolo_fuera_de_sigma.part",
                       "10_decimal_incompleto.part"):
            with self.subTest(archivo=nombre):
                texto = (RAIZ / "errores" / nombre).read_text(encoding="utf-8")
                arbol, _, lexicos, sintacticos = analizar(texto)
                self.assertIsNone(arbol)
                self.assertEqual(len(lexicos), 1)

    def test_linea_y_columna(self):
        errores = errores_de("tempo 120;\ntocar re4 ;")
        self.assertIn("línea 2, columna 11", errores[0])

    def test_leer_exige_cadena(self):
        self.assertIn("leer(...) recibe un mensaje", errores_de("entero x = leer(5);")[0])


if __name__ == "__main__":
    unittest.main()
