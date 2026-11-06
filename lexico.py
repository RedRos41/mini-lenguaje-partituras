"""
Analizador léxico del mini-lenguaje de partituras.

Implementa EXACTAMENTE el AFD de la Fase 1:
  M = (Q, Σ, δ, q0, F)
  - Q: 19 estados (q0 ... q17 y qE)
  - Σ: 100 caracteres agrupados en 15 clases (sección 5.1 de la Fase 1)
  - δ: la matriz de transiciones (sección 6 de la Fase 1)
  - F: 14 estados de aceptación

El lexer NO usa expresiones regulares de Python: recorre la tabla de
transiciones carácter por carácter y aplica la regla de la coincidencia
más larga (sección 5.3 de la Fase 1).
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 1. Alfabeto Σ = L ∪ D ∪ S ∪ B   (Fase 1, sección 2)
# ---------------------------------------------------------------------------

LETRAS = set("abcdefghijklmnopqrstuvwxyz"
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
             "áéíóúÁÉÍÓÚñÑüÜ")                      # |L| = 66
DIGITOS = set("0123456789")                          # |D| = 10
SIMBOLOS = set("+-*/=<>!(),;|\".#_:¿?¡")             # |S| = 21
BLANCOS = {" ", "\t", "\n"}                          # |B| = 3

assert len(LETRAS) == 66 and len(DIGITOS) == 10
assert len(SIMBOLOS) == 21 and len(BLANCOS) == 3


# ---------------------------------------------------------------------------
# 2. Clases de caracteres (Fase 1, sección 5.1)
#    Dos caracteres están en la misma clase si producen la misma
#    transición en todos los estados.
# ---------------------------------------------------------------------------

def clase_de(c):
    """Devuelve la clase del carácter c, o None si c no pertenece a Σ."""
    if c in LETRAS:
        return "L"
    if c in DIGITOS:
        return "D"
    if c == "_":
        return "_"
    if c == ".":
        return "."
    if c == '"':
        return '"'
    if c == "#":
        return "#"
    if c == "=":
        return "="
    if c == "!":
        return "!"
    if c == "<":
        return "<"
    if c == ">":
        return ">"
    if c in "+-*/":
        return "AR"
    if c in "(),;|":
        return "DL"
    if c in " \t":
        return "ES"
    if c == "\n":
        return "SL"
    if c in ":¿?¡":
        return "OT"
    return None          # carácter fuera de Σ: siempre lleva a qE


CLASES = ["L", "D", "_", ".", '"', "#", "=", "!", "<", ">",
          "AR", "DL", "ES", "SL", "OT"]


# ---------------------------------------------------------------------------
# 3. Matriz de transiciones δ (Fase 1, sección 6)
#    Cada fila es un estado; cada columna una clase, en el orden de CLASES.
#    "qE" es el estado sumidero.
# ---------------------------------------------------------------------------

E = "qE"
_FILAS = {
    #        L     D     _     .     "     #     =     !     <      >      AR     DL     ES    SL    OT
    "q0":  ["q1", "q2", E,    E,    "q5", "q7", "q8", "q10", "q12", "q14", "q16", "q17", "q0", "q0", E],
    "q1":  ["q1", "q1", "q1", E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q2":  [E,    "q2", E,    "q3", E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q3":  [E,    "q4", E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q4":  [E,    "q4", E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q5":  ["q5", "q5", "q5", "q5", "q6", "q5", "q5", "q5",  "q5",  "q5",  "q5",  "q5",  "q5", E,    "q5"],
    "q6":  [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q7":  ["q7", "q7", "q7", "q7", "q7", "q7", "q7", "q7",  "q7",  "q7",  "q7",  "q7",  "q7", E,    "q7"],
    "q8":  [E,    E,    E,    E,    E,    E,    "q9", E,     E,     E,     E,     E,     E,    E,    E],
    "q9":  [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q10": [E,    E,    E,    E,    E,    E,    "q11", E,    E,     E,     E,     E,     E,    E,    E],
    "q11": [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q12": [E,    E,    E,    E,    E,    E,    "q13", E,    E,     E,     E,     E,     E,    E,    E],
    "q13": [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q14": [E,    E,    E,    E,    E,    E,    "q15", E,    E,     E,     E,     E,     E,    E,    E],
    "q15": [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q16": [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "q17": [E,    E,    E,    E,    E,    E,    E,    E,     E,     E,     E,     E,     E,    E,    E],
    "qE":  [E] * 15,
}

# δ como diccionario: TRANSICIONES[estado][clase] -> estado
TRANSICIONES = {estado: dict(zip(CLASES, fila)) for estado, fila in _FILAS.items()}

assert len(TRANSICIONES) == 19                       # |Q| = 19
assert all(len(f) == 15 for f in TRANSICIONES.values())   # 19 × 15 = 285 celdas


def delta(estado, caracter):
    """Función de transición δ: Q × Σ → Q (total)."""
    clase = clase_de(caracter)
    if clase is None:
        return E
    return TRANSICIONES[estado][clase]


# ---------------------------------------------------------------------------
# 4. Estados de aceptación F y el token que emite cada uno
#    (Fase 1, sección 5.2). None = se reconoce pero se descarta.
# ---------------------------------------------------------------------------

ACEPTACION = {
    "q1":  "PALABRA",      # se clasifica después: reservada, NOTA o ID
    "q2":  "NUM_ENT",
    "q4":  "NUM_DEC",
    "q6":  "CADENA",
    "q7":  None,           # comentario: se descarta
    "q8":  "=",
    "q9":  "==",
    "q11": "!=",
    "q12": "<",
    "q13": "<=",
    "q14": ">",
    "q15": ">=",
    "q16": "OPERADOR",     # + - * /  (el tipo es el propio lexema)
    "q17": "DELIMITADOR",  # ( ) , ; | (el tipo es el propio lexema)
}
assert len(ACEPTACION) == 14                         # |F| = 14


# ---------------------------------------------------------------------------
# 5. Clasificación de palabras (Fase 1, sección 4)
#    clase(w) = RESERVADA si w ∈ R; NOTA si w ∈ N; ID en otro caso
# ---------------------------------------------------------------------------

RESERVADAS = {                                       # |R| = 16
    "entero", "decimal", "texto", "booleano",
    "si", "entonces", "sino", "mientras", "hacer",
    "tocar", "silencio", "tempo", "mostrar", "leer",
    "verdadero", "falso",
}
NOMBRES_NOTA = ["do", "re", "mi", "fa", "sol", "la", "si"]
NOTAS = {n + str(o) for n in NOMBRES_NOTA for o in range(1, 8)}   # |N| = 49

assert len(RESERVADAS) == 16 and len(NOTAS) == 49
assert RESERVADAS.isdisjoint(NOTAS)


def clasificar(palabra):
    """Decide la categoría de un lexema aceptado en q1."""
    if palabra in RESERVADAS:
        return palabra          # el tipo de una reservada es la propia palabra
    if palabra in NOTAS:
        return "NOTA"
    return "ID"


# ---------------------------------------------------------------------------
# 6. Tokens y errores
# ---------------------------------------------------------------------------

@dataclass
class Token:
    tipo: str        # terminal de la gramática: 'tocar', 'NOTA', 'ID', ';', '$', ...
    lexema: str
    linea: int
    columna: int

    def __str__(self):
        if self.tipo == self.lexema:
            return f"{self.tipo}"
        return f"{self.tipo}({self.lexema})"


@dataclass
class ErrorLexico:
    mensaje: str
    linea: int
    columna: int

    def __str__(self):
        return f"Error léxico (línea {self.linea}, columna {self.columna}): {self.mensaje}"


# Mensajes para los estados de rechazo (Fase 1, sección 7)
_MENSAJE_RECHAZO = {
    "q3": "número decimal incompleto: se esperaba al menos un dígito después del punto",
    "q5": "cadena sin cerrar: falta la comilla de cierre antes del fin de línea",
    "q10": "el símbolo '!' solo es válido como parte del operador '!='",
}


# ---------------------------------------------------------------------------
# 7. El lexer: recorre δ con coincidencia más larga (Fase 1, sección 5.3)
# ---------------------------------------------------------------------------

class Lexer:
    def __init__(self, texto):
        # Los archivos creados en Windows terminan las líneas con "\r\n".
        # '\r' no pertenece a Σ, así que se normaliza antes de analizar.
        self.texto = texto.replace("\r\n", "\n").replace("\r", "\n")
        self.tokens = []
        self.errores = []

    def _posicion(self, indice):
        """Convierte un índice del texto en (línea, columna), ambas desde 1."""
        linea = self.texto.count("\n", 0, indice) + 1
        inicio_linea = self.texto.rfind("\n", 0, indice) + 1
        return linea, indice - inicio_linea + 1

    def tokenizar(self):
        texto = self.texto
        i = 0
        n = len(texto)

        while i < n:
            # Paso 1: desde q0, saltar blancos (bucle de q0 sobre ES y SL)
            if delta("q0", texto[i]) == "q0":
                i += 1
                continue

            # Paso 2: aplicar δ recordando el último estado de aceptación
            estado = "q0"
            j = i
            ultimo_aceptado = None      # (estado, índice final exclusivo)
            while j < n:
                siguiente = delta(estado, texto[j])
                if siguiente == E:
                    break
                estado = siguiente
                j += 1
                if estado in ACEPTACION:
                    ultimo_aceptado = (estado, j)

            linea, columna = self._posicion(i)

            # Caso q3: se leyó "dígitos." y el AFD se detuvo sin ver otro
            # dígito. Aunque q2 aceptó antes, "5." es un decimal incompleto
            # (Fase 1, sección 7), así que se reporta y se descarta completo.
            if estado == "q3":
                self.errores.append(ErrorLexico(_MENSAJE_RECHAZO["q3"], linea, columna))
                i = j
                continue

            # Paso 4: ningún estado de aceptación visitado -> error léxico
            if ultimo_aceptado is None:
                caracter = texto[i]
                if estado in _MENSAJE_RECHAZO:
                    mensaje = _MENSAJE_RECHAZO[estado]
                elif clase_de(caracter) is None:
                    mensaje = f"el carácter {caracter!r} no pertenece al alfabeto Σ"
                else:
                    mensaje = f"el carácter {caracter!r} no puede iniciar ningún token"
                self.errores.append(ErrorLexico(mensaje, linea, columna))
                # Recuperación: una cadena sin cerrar se descarta hasta el fin
                # de línea; en los demás casos se salta un solo carácter.
                if estado == "q5":
                    fin = texto.find("\n", i)
                    i = n if fin == -1 else fin
                else:
                    i += 1
                continue

            # Paso 3: emitir el token del último estado de aceptación
            estado_final, fin = ultimo_aceptado
            lexema = texto[i:fin]
            tipo = ACEPTACION[estado_final]
            if tipo is not None:                        # q7 (comentario) se descarta
                if tipo == "PALABRA":
                    tipo = clasificar(lexema)
                elif tipo in ("OPERADOR", "DELIMITADOR"):
                    tipo = lexema
                self.tokens.append(Token(tipo, lexema, linea, columna))

            # Reiniciar en q0 justo después del lexema emitido
            i = fin

        linea, columna = self._posicion(n)
        self.tokens.append(Token("$", "$", linea, columna))   # fin de archivo
        return self.tokens, self.errores


def tokenizar(texto):
    """Atajo: devuelve (tokens, errores) del texto dado."""
    return Lexer(texto).tokenizar()


def recorrido(lexema):
    """
    Devuelve la secuencia de estados que visita el AFD al leer `lexema`
    desde q0. Sirve para comprobar a mano las trazas de la Fase 1.
    Ejemplo: recorrido("si4") -> ['q0', 'q1', 'q1', 'q1']
    """
    estados = ["q0"]
    estado = "q0"
    for c in lexema:
        estado = delta(estado, c)
        estados.append(estado)
    return estados
