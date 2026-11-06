"""Pruebas del intérprete (extra)."""

import tempfile
import unittest
import wave
from pathlib import Path

from sintactico import analizar
from interprete import Interprete, ErrorEjecucion, frecuencia, segundos

RAIZ = Path(__file__).resolve().parent.parent


def ejecutar(texto, entradas=()):
    arbol, _, lexicos, sintacticos = analizar(texto)
    assert not lexicos and not sintacticos, lexicos + sintacticos
    salida = []
    pendientes = list(entradas)
    interprete = Interprete(leer_entrada=lambda mensaje: pendientes.pop(0),
                            escribir=salida.append)
    interprete.ejecutar(arbol)
    return interprete, salida


def valor(interprete, nombre):
    return interprete.variables[nombre][1]


class Expresiones(unittest.TestCase):
    def test_precedencia(self):
        i, _ = ejecutar("entero vuelta = 4; decimal r = vuelta + 1 * 2;")
        self.assertEqual(valor(i, "r"), 6)          # no 10: Fase 2, sección 3.1

    def test_asociatividad_izquierda(self):
        i, _ = ejecutar("entero r = 8 - 4 - 2;")
        self.assertEqual(valor(i, "r"), 2)          # (8 - 4) - 2, Fase 2, sección 5.5

    def test_division_da_decimal(self):
        i, _ = ejecutar("decimal d = 1/4;")
        self.assertEqual(valor(i, "d"), 0.25)

    def test_parentesis_y_menos_unario(self):
        i, _ = ejecutar("entero x = -(3 + 2) * 2;")
        self.assertEqual(valor(i, "x"), -10)

    def test_concatenacion_de_textos(self):
        i, salida = ejecutar('texto a = "Hola, " + "mundo"; mostrar(a, "!", 3);')
        self.assertEqual(salida, ["Hola, mundo!3"])


class Ejemplos(unittest.TestCase):
    def test_tempo_acelera(self):
        texto = (RAIZ / "ejemplos" / "tempo_acelera.part").read_text(encoding="utf-8")
        i, salida = ejecutar(texto)
        self.assertEqual(valor(i, "vuelta"), 5)
        self.assertTrue(valor(i, "final"))
        self.assertEqual(salida[-1], "¡Fin!")
        notas = [e for e, _ in i.eventos if e.startswith("nota")]
        self.assertEqual(len(notas), 7)            # 3 vueltas × 2 notas + do5

    def test_estrellita_con_entrada(self):
        texto = (RAIZ / "ejemplos" / "estrellita.part").read_text(encoding="utf-8")
        i, _ = ejecutar(texto, ["2"])
        self.assertEqual(len(i.eventos), 14)       # 7 notas × 2 repeticiones

    def test_wav_generado(self):
        texto = (RAIZ / "ejemplos" / "escala.part").read_text(encoding="utf-8")
        i, _ = ejecutar(texto, ["120"])
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "escala.wav"
            duracion = i.guardar_wav(ruta)
            with wave.open(str(ruta)) as archivo:
                self.assertEqual(archivo.getnchannels(), 1)
            self.assertAlmostEqual(duracion, 4.5, places=1)   # 7 negras + 1 blanca a 120


class Musica(unittest.TestCase):
    def test_la4_es_440(self):
        self.assertAlmostEqual(frecuencia("la4"), 440.0)
        self.assertAlmostEqual(frecuencia("do4"), 261.63, places=2)

    def test_negra_a_120_dura_medio_segundo(self):
        self.assertAlmostEqual(segundos(1 / 4, 120), 0.5)


class ErroresDeEjecucion(unittest.TestCase):
    def comprobar(self, texto, fragmento):
        with self.assertRaises(ErrorEjecucion) as contexto:
            ejecutar(texto)
        self.assertIn(fragmento, str(contexto.exception))

    def test_variable_no_declarada(self):
        self.comprobar("x = 3;", "no ha sido declarada")

    def test_redeclaracion(self):
        self.comprobar("entero x = 1; entero x = 2;", "ya fue declarada")

    def test_tipo_incompatible(self):
        self.comprobar('entero x = "hola";', "no se puede guardar")
        self.comprobar("entero x = 1/2;", "no se puede guardar")

    def test_condicion_no_booleana(self):
        self.comprobar("entero x = 1; si x entonces | |", "debe ser booleana")

    def test_division_entre_cero(self):
        self.comprobar("decimal d = 1/0;", "división entre cero")

    def test_duracion_invalida(self):
        self.comprobar("tocar do4 0;", "mayor que 0")

    def test_ciclo_infinito(self):
        Interprete.MAX_ITERACIONES, original = 50, Interprete.MAX_ITERACIONES
        try:
            self.comprobar("mientras verdadero hacer | |", "ciclo infinito")
        finally:
            Interprete.MAX_ITERACIONES = original


if __name__ == "__main__":
    unittest.main()
