"""
Intérprete del mini-lenguaje de partituras (extra, no lo exige la rúbrica).

Recorre el árbol de derivación que produce el parser, sin construir otra
estructura intermedia: hay un método por cada no terminal que tiene
significado al ejecutarse. Valida tipos, muestra en consola lo que se toca
y genera un archivo .wav usando solo la librería estándar de Python.
"""

import math
import struct
import wave



class ErrorEjecucion(Exception):
    def __init__(self, mensaje, token=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.token = token

    def __str__(self):
        if self.token is not None:
            return (f"Error de ejecución (línea {self.token.linea}, "
                    f"columna {self.token.columna}): {self.mensaje}")
        return f"Error de ejecución: {self.mensaje}"


# ---------------------------------------------------------------------------
# Tipos del lenguaje y su representación en Python
# ---------------------------------------------------------------------------

def tipo_de(valor):
    if isinstance(valor, bool):          # bool va primero: en Python bool es int
        return "booleano"
    if isinstance(valor, int):
        return "entero"
    if isinstance(valor, float):
        return "decimal"
    return "texto"


def compatible(tipo_variable, valor):
    """¿Se puede guardar `valor` en una variable de `tipo_variable`?"""
    t = tipo_de(valor)
    if tipo_variable == t:
        return True
    return tipo_variable == "decimal" and t == "entero"   # un entero cabe en un decimal


def a_texto(valor):
    if isinstance(valor, bool):
        return "verdadero" if valor else "falso"
    if isinstance(valor, float):
        return repr(round(valor, 6))
    return str(valor)


def es_numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


# ---------------------------------------------------------------------------
# Música: frecuencias y duraciones
# ---------------------------------------------------------------------------

SEMITONOS = {"do": 0, "re": 2, "mi": 4, "fa": 5, "sol": 7, "la": 9, "si": 11}
TASA_MUESTREO = 22050          # muestras por segundo
TEMPO_INICIAL = 120            # negras por minuto


def frecuencia(nota):
    """Frecuencia en Hz de una nota como 'la4' (la4 = 440 Hz)."""
    nombre, octava = nota[:-1], int(nota[-1])
    midi = 12 * (octava + 1) + SEMITONOS[nombre]
    return 440.0 * 2 ** ((midi - 69) / 12)


def segundos(duracion, tempo):
    """
    Duración en segundos. La duración del lenguaje se mide en redondas
    (1/4 = negra) y el tempo en negras por minuto: una negra dura 60/tempo s.
    """
    return duracion * 4 * 60.0 / tempo


def muestras_nota(freq, seg):
    """Onda senoidal con entrada y salida suaves para evitar chasquidos."""
    total = int(seg * TASA_MUESTREO)
    rampa = min(int(0.01 * TASA_MUESTREO), total // 2)
    datos = []
    for k in range(total):
        envolvente = 1.0
        if k < rampa:
            envolvente = k / rampa
        elif k >= total - rampa:
            envolvente = (total - k) / rampa
        datos.append(int(0.5 * 32767 * envolvente *
                         math.sin(2 * math.pi * freq * k / TASA_MUESTREO)))
    return datos


# ---------------------------------------------------------------------------
# El intérprete
# ---------------------------------------------------------------------------

class Interprete:
    MAX_ITERACIONES = 100_000     # protege contra ciclos 'mientras' infinitos

    def __init__(self, leer_entrada=input, escribir=print):
        self.variables = {}       # nombre -> (tipo, valor)
        self.tempo = TEMPO_INICIAL
        self.audio = []           # muestras de 16 bits
        self.eventos = []         # (descripción, segundos) para el resumen
        self.leer_entrada = leer_entrada
        self.escribir = escribir

    # --- utilidades sobre el árbol -------------------------------------

    @staticmethod
    def es_vacio(nodo):
        return len(nodo.hijos) == 1 and nodo.hijos[0].etiqueta == "ε"

    # --- programa e instrucciones --------------------------------------

    def ejecutar(self, arbol):
        # Regla 1: <programa> ::= <lista_instr> $
        self.lista_instr(arbol.hijos[0])

    def lista_instr(self, nodo):
        # Reglas 2-3: se recorre iterativamente para no agotar la pila
        while not self.es_vacio(nodo):
            self.instruccion(nodo.hijos[0])
            nodo = nodo.hijos[1]

    def instruccion(self, nodo):
        hijo = nodo.hijos[0]
        metodo = {
            "<declaracion>": self.declaracion,
            "<asignacion>": self.asignacion,
            "<tocar_instr>": self.tocar_instr,
            "<silencio_instr>": self.silencio_instr,
            "<tempo_instr>": self.tempo_instr,
            "<mostrar_instr>": self.mostrar_instr,
            "<condicional>": self.condicional,
            "<ciclo>": self.ciclo,
        }[hijo.etiqueta]
        metodo(hijo)

    def declaracion(self, nodo):
        # Regla 12: <tipo> ID <decl_resto>
        tipo = nodo.hijos[0].hijos[0].etiqueta
        id_token = nodo.hijos[1].token
        nombre = id_token.lexema
        if nombre in self.variables:
            raise ErrorEjecucion(f"la variable '{nombre}' ya fue declarada", id_token)
        resto = nodo.hijos[2]
        if self.es_vacio(resto):
            valor = {"entero": 0, "decimal": 0.0, "texto": "", "booleano": False}[tipo]
        else:
            valor = self.expresion(resto.hijos[1])     # "=" <expresion>
            if not compatible(tipo, valor):
                raise ErrorEjecucion(
                    f"no se puede guardar un valor {tipo_de(valor)} en la "
                    f"variable '{nombre}' de tipo {tipo}", id_token)
            if tipo == "decimal":
                valor = float(valor)
        self.variables[nombre] = (tipo, valor)

    def asignacion(self, nodo):
        # Regla 19: ID "=" <expresion>
        id_token = nodo.hijos[0].token
        nombre = id_token.lexema
        if nombre not in self.variables:
            raise ErrorEjecucion(f"la variable '{nombre}' no ha sido declarada", id_token)
        tipo, _ = self.variables[nombre]
        valor = self.expresion(nodo.hijos[2])
        if not compatible(tipo, valor):
            raise ErrorEjecucion(
                f"no se puede guardar un valor {tipo_de(valor)} en la "
                f"variable '{nombre}' de tipo {tipo}", id_token)
        if tipo == "decimal":
            valor = float(valor)
        self.variables[nombre] = (tipo, valor)

    def _duracion(self, nodo_expr, que):
        valor = self.expresion(nodo_expr)
        if not es_numero(valor) or valor <= 0:
            raise ErrorEjecucion(f"{que} debe ser un número mayor que 0, "
                                 f"pero vale {a_texto(valor)}", self._primer_token(nodo_expr))
        return valor

    def tocar_instr(self, nodo):
        # Regla 20: tocar NOTA <expresion>
        nota = nodo.hijos[1].token.lexema
        duracion = self._duracion(nodo.hijos[2], "la duración de la nota")
        seg = segundos(duracion, self.tempo)
        self.audio.extend(muestras_nota(frecuencia(nota), seg))
        self.eventos.append((f"nota {nota}", seg))
        self.escribir(f"  ♪ {nota:<5} duración {a_texto(duracion):<8} "
                      f"({seg:.2f} s, {frecuencia(nota):.1f} Hz)")

    def silencio_instr(self, nodo):
        # Regla 21: silencio <expresion>
        duracion = self._duracion(nodo.hijos[1], "la duración del silencio")
        seg = segundos(duracion, self.tempo)
        self.audio.extend([0] * int(seg * TASA_MUESTREO))
        self.eventos.append(("silencio", seg))
        self.escribir(f"  · silencio duración {a_texto(duracion):<8} ({seg:.2f} s)")

    def tempo_instr(self, nodo):
        # Regla 22: tempo <expresion>
        valor = self.expresion(nodo.hijos[1])
        if not es_numero(valor) or valor <= 0:
            raise ErrorEjecucion(f"el tempo debe ser un número mayor que 0, pero vale "
                                 f"{a_texto(valor)}", nodo.hijos[0].token)
        self.tempo = valor
        self.escribir(f"  tempo = {a_texto(valor)} negras por minuto")

    def mostrar_instr(self, nodo):
        # Regla 23: mostrar "(" <lista_args> ")"
        lista = nodo.hijos[2]
        valores = [self.expresion(lista.hijos[0])]
        resto = lista.hijos[1]
        while not self.es_vacio(resto):                # Reglas 25-26
            valores.append(self.expresion(resto.hijos[1]))
            resto = resto.hijos[2]
        self.escribir("".join(a_texto(v) for v in valores))

    def _condicion(self, nodo_expr, palabra):
        valor = self.expresion(nodo_expr)
        if not isinstance(valor, bool):
            raise ErrorEjecucion(f"la condición de '{palabra}' debe ser booleana, "
                                 f"pero es {tipo_de(valor)}", self._primer_token(nodo_expr))
        return valor

    def condicional(self, nodo):
        # Regla 27: si <expresion> entonces <bloque> <sino_parte>
        if self._condicion(nodo.hijos[1], "si"):
            self.bloque(nodo.hijos[3])
        else:
            sino = nodo.hijos[4]
            if not self.es_vacio(sino):               # Regla 28
                self.bloque(sino.hijos[1])

    def ciclo(self, nodo):
        # Regla 30: mientras <expresion> hacer <bloque>
        vueltas = 0
        while self._condicion(nodo.hijos[1], "mientras"):
            vueltas += 1
            if vueltas > self.MAX_ITERACIONES:
                raise ErrorEjecucion("el ciclo 'mientras' superó 100000 vueltas: "
                                     "posible ciclo infinito", nodo.hijos[0].token)
            self.bloque(nodo.hijos[3])

    def bloque(self, nodo):
        # Regla 31: "|" <lista_instr> "|"
        self.lista_instr(nodo.hijos[1])

    # --- expresiones ---------------------------------------------------

    def _primer_token(self, nodo):
        while not nodo.es_terminal():
            nodo = nodo.hijos[0]
        return nodo.token

    def expresion(self, nodo):
        # Regla 32: <expr_arit> <rel_resto>
        izquierdo = self.expr_arit(nodo.hijos[0])
        resto = nodo.hijos[1]
        if self.es_vacio(resto):
            return izquierdo
        op_token = resto.hijos[0].hijos[0].token          # <op_rel>
        derecho = self.expr_arit(resto.hijos[1])
        return self._relacional(op_token, izquierdo, derecho)

    def _relacional(self, op_token, a, b):
        op = op_token.tipo
        if op in ("==", "!="):
            mismo = (es_numero(a) and es_numero(b)) or tipo_de(a) == tipo_de(b)
            if not mismo:
                raise ErrorEjecucion(f"no se puede comparar {tipo_de(a)} con "
                                     f"{tipo_de(b)}", op_token)
            return (a == b) if op == "==" else (a != b)
        if not (es_numero(a) and es_numero(b)):
            raise ErrorEjecucion(f"'{op}' solo compara números, no {tipo_de(a)} "
                                 f"con {tipo_de(b)}", op_token)
        return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]

    def expr_arit(self, nodo):
        # Regla 41: <termino> <expr_arit'>
        # <expr_arit'> se recorre como un ciclo que acumula de izquierda a
        # derecha: así se conserva la asociatividad izquierda (Fase 2, 5.5).
        valor = self.termino(nodo.hijos[0])
        resto = nodo.hijos[1]
        while not self.es_vacio(resto):                    # Reglas 42-44
            op_token = resto.hijos[0].token
            derecho = self.termino(resto.hijos[1])
            valor = self._aritmetica(op_token, valor, derecho)
            resto = resto.hijos[2]
        return valor

    def termino(self, nodo):
        # Regla 45: <factor> <termino'>
        valor = self.factor(nodo.hijos[0])
        resto = nodo.hijos[1]
        while not self.es_vacio(resto):                    # Reglas 46-48
            op_token = resto.hijos[0].token
            derecho = self.factor(resto.hijos[1])
            valor = self._aritmetica(op_token, valor, derecho)
            resto = resto.hijos[2]
        return valor

    def _aritmetica(self, op_token, a, b):
        op = op_token.tipo
        if op == "+" and isinstance(a, str) and isinstance(b, str):
            return a + b                                   # concatenación de textos
        if not (es_numero(a) and es_numero(b)):
            raise ErrorEjecucion(f"'{op}' no se puede aplicar a {tipo_de(a)} y "
                                 f"{tipo_de(b)}", op_token)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b == 0:
            raise ErrorEjecucion("división entre cero", op_token)
        return a / b                       # la división siempre da decimal: 1/4 = 0.25

    def factor(self, nodo):
        primero = nodo.hijos[0]
        t = primero.etiqueta
        if t == "(":                                       # Regla 49
            return self.expresion(nodo.hijos[1])
        if t == "-":                                       # Regla 50
            valor = self.factor(nodo.hijos[1])
            if not es_numero(valor):
                raise ErrorEjecucion(f"no se puede negar un valor {tipo_de(valor)}",
                                     primero.token)
            return -valor
        if t == "ID":                                      # Regla 51
            nombre = primero.token.lexema
            if nombre not in self.variables:
                raise ErrorEjecucion(f"la variable '{nombre}' no ha sido declarada",
                                     primero.token)
            return self.variables[nombre][1]
        if t == "NUM_ENT":                                 # Regla 52
            return int(primero.token.lexema)
        if t == "NUM_DEC":                                 # Regla 53
            return float(primero.token.lexema)
        if t == "CADENA":                                  # Regla 54
            return primero.token.lexema[1:-1]              # sin las comillas
        if t == "verdadero":                               # Regla 55
            return True
        if t == "falso":                                   # Regla 56
            return False
        if t == "leer":                                    # Regla 57
            mensaje = nodo.hijos[2].token.lexema[1:-1]
            try:
                texto = self.leer_entrada(mensaje)
            except EOFError:
                raise ErrorEjecucion("leer(...) no recibió ningún dato", primero.token)
            return self._convertir_entrada(texto.strip())
        raise ErrorEjecucion(f"factor desconocido {t}", primero.token)

    @staticmethod
    def _convertir_entrada(texto):
        """El dato leído se interpreta como entero, decimal, booleano o texto."""
        try:
            return int(texto)
        except ValueError:
            pass
        try:
            return float(texto)
        except ValueError:
            pass
        if texto in ("verdadero", "falso"):
            return texto == "verdadero"
        return texto

    # --- salida de audio -----------------------------------------------

    def guardar_wav(self, ruta):
        with wave.open(str(ruta), "wb") as archivo:
            archivo.setnchannels(1)
            archivo.setsampwidth(2)              # 16 bits
            archivo.setframerate(TASA_MUESTREO)
            archivo.writeframes(struct.pack(f"<{len(self.audio)}h", *self.audio))
        return len(self.audio) / TASA_MUESTREO
