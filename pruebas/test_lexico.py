"""Pruebas del analizador léxico contra lo definido en la Fase 1."""

import unittest

from lexico import (LETRAS, DIGITOS, SIMBOLOS, BLANCOS, TRANSICIONES, ACEPTACION,
                    RESERVADAS, NOTAS, clase_de, clasificar, recorrido, tokenizar)


def tipos(texto):
    tokens, errores = tokenizar(texto)
    return [str(t) for t in tokens], [str(e) for e in errores]


class AlfabetoYAutomata(unittest.TestCase):
    def test_tamano_del_alfabeto(self):
        # Fase 1, sección 2: |L| = 66, |D| = 10, |S| = 21, |B| = 3, |Σ| = 100
        sigma = LETRAS | DIGITOS | SIMBOLOS | BLANCOS
        self.assertEqual(len(sigma), 100)

    def test_clases_son_particion_de_sigma(self):
        # Fase 1, sección 5.1: todo carácter de Σ tiene exactamente una clase
        sigma = LETRAS | DIGITOS | SIMBOLOS | BLANCOS
        self.assertTrue(all(clase_de(c) is not None for c in sigma))
        self.assertIsNone(clase_de("$"))
        self.assertIsNone(clase_de("@"))

    def test_matriz_completa(self):
        # Fase 1, sección 6: 19 estados × 15 clases = 285 celdas
        self.assertEqual(len(TRANSICIONES), 19)
        self.assertEqual(sum(len(f) for f in TRANSICIONES.values()), 285)
        self.assertEqual(len(ACEPTACION), 14)

    def test_sumidero(self):
        self.assertTrue(all(destino == "qE" for destino in TRANSICIONES["qE"].values()))


class TrazasDeLaFase1(unittest.TestCase):
    def test_traza_1_recorridos(self):
        self.assertEqual(recorrido("tocar"), ["q0", "q1", "q1", "q1", "q1", "q1"])
        self.assertEqual(recorrido("si4"), ["q0", "q1", "q1", "q1"])
        self.assertEqual(recorrido("/"), ["q0", "q16"])
        self.assertEqual(recorrido(";"), ["q0", "q17"])

    def test_traza_1_tokens(self):
        tokens, errores = tipos("tocar si4 1/4;")
        self.assertEqual(tokens, ["tocar", "NOTA(si4)", "NUM_ENT(1)", "/",
                                  "NUM_ENT(4)", ";", "$"])
        self.assertEqual(errores, [])

    def test_traza_2_coincidencia_mas_larga(self):
        self.assertEqual(recorrido("<="), ["q0", "q12", "q13"])
        tokens, _ = tipos("vuelta <= 4")
        self.assertEqual(tokens, ["ID(vuelta)", "<=", "NUM_ENT(4)", "$"])

    def test_traza_3_decimal(self):
        self.assertEqual(recorrido("1.25"), ["q0", "q2", "q3", "q4", "q4"])
        tokens, _ = tipos("velocidad * 1.25;")
        self.assertIn("NUM_DEC(1.25)", tokens)

    def test_traza_4_cadena_sin_cerrar(self):
        _, errores = tipos('texto t = "sin cerrar;\n')
        self.assertEqual(len(errores), 1)
        self.assertIn("cadena sin cerrar", errores[0])


class Clasificacion(unittest.TestCase):
    def test_conjuntos(self):
        self.assertEqual(len(RESERVADAS), 16)
        self.assertEqual(len(NOTAS), 49)

    def test_tabla_de_la_seccion_4(self):
        self.assertEqual(clasificar("si"), "si")          # reservada
        self.assertEqual(clasificar("si4"), "NOTA")
        self.assertEqual(clasificar("do9"), "ID")         # octava fuera de 1 a 7
        self.assertEqual(clasificar("dos"), "ID")
        self.assertEqual(clasificar("Tocar"), "ID")       # distingue mayúsculas

    def test_comentarios_y_blancos_se_descartan(self):
        tokens, _ = tipos("# un comentario con tildes: canción\n\t tempo 120; # otro")
        self.assertEqual(tokens, ["tempo", "NUM_ENT(120)", ";", "$"])

    def test_operadores_dobles(self):
        tokens, _ = tipos("== != <= >= = < > !=")
        self.assertEqual(tokens, ["==", "!=", "<=", ">=", "=", "<", ">", "!=", "$"])


class ErroresLexicos(unittest.TestCase):
    def test_simbolo_fuera_de_sigma(self):
        _, errores = tipos("tocar re4 1/4 $")
        self.assertEqual(len(errores), 1)
        self.assertIn("no pertenece al alfabeto", errores[0])

    def test_decimal_incompleto(self):
        _, errores = tipos("decimal d = 5. ;")
        self.assertIn("decimal incompleto", errores[0])

    def test_exclamacion_sola(self):
        _, errores = tipos("x ! 3")
        self.assertIn("'!='", errores[0])

    def test_simbolo_que_no_inicia_token(self):
        _, errores = tipos("_x = 1;")
        self.assertIn("no puede iniciar", errores[0])

    def test_posicion_del_error(self):
        tokens, errores = tokenizar("tempo 120;\n  @")
        self.assertEqual((errores[0].linea, errores[0].columna), (2, 3))

    def test_finales_de_linea_windows(self):
        tokens, errores = tipos("tempo 120;\r\ntocar do4 1/4;\r\n")
        self.assertEqual(errores, [])


if __name__ == "__main__":
    unittest.main()
