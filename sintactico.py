"""
Analizador sintáctico del mini-lenguaje de partituras.

Parser descendente recursivo LL(1) que implementa la gramática final de la
Fase 2 (sección 7). Regla de diseño: cada no terminal es UNA función con
el mismo nombre, y cada alternativa se elige con los conjuntos PRIMERO y
SIGUIENTE de la sección 8 de la Fase 2. Los comentarios "Regla N" remiten
a la numeración de la gramática final.

Salida: el árbol de derivación sintáctica, o la lista de errores.
"""

import sys

from lexico import tokenizar, NOMBRES_NOTA


# ---------------------------------------------------------------------------
# Conjuntos PRIMERO y SIGUIENTE (Fase 2, sección 8)
# ---------------------------------------------------------------------------

TIPOS = {"entero", "decimal", "texto", "booleano"}
RELS = {"==", "!=", "<", ">", "<=", ">="}

PRIMERO_INSTRUCCION = TIPOS | {"ID", "tocar", "silencio", "tempo",
                               "mostrar", "si", "mientras"}
SIGUIENTE_LISTA_INSTR = {"$", "|"}

PRIMERO_FACTOR = {"(", "-", "ID", "NUM_ENT", "NUM_DEC", "CADENA",
                  "verdadero", "falso", "leer"}
PRIMERO_EXPRESION = PRIMERO_FACTOR       # <expresion> ⇒ <expr_arit> ⇒ <termino> ⇒ <factor>

# Nombre legible de cada terminal para los mensajes de error
_LEGIBLE = {
    "ID": "un identificador",
    "NOTA": "una nota (do1 a si7)",
    "NUM_ENT": "un número entero",
    "NUM_DEC": "un número decimal",
    "CADENA": "una cadena entre comillas",
    "$": "el fin del archivo",
}


def legible(tipo):
    return _LEGIBLE.get(tipo, f"'{tipo}'")


# ---------------------------------------------------------------------------
# Árbol de derivación
# ---------------------------------------------------------------------------

class Nodo:
    """
    Nodo del árbol de derivación.
    - No terminal: etiqueta '<nombre>' y una lista de hijos.
    - Terminal: etiqueta = tipo del token y `token` con lexema y posición.
    - Producción vacía: un hijo con etiqueta 'ε'.
    """

    def __init__(self, etiqueta, token=None):
        self.etiqueta = etiqueta
        self.token = token
        self.hijos = []

    def agregar(self, hijo):
        self.hijos.append(hijo)
        return hijo

    def es_terminal(self):
        return self.token is not None

    def texto(self):
        """Cómo se imprime el nodo: los terminales variables muestran su lexema."""
        if self.token is not None and self.token.tipo != self.token.lexema:
            return f"{self.etiqueta} ({self.token.lexema})"
        return self.etiqueta


def vacio(etiqueta):
    """Nodo de un no terminal que eligió la producción ε."""
    nodo = Nodo(etiqueta)
    nodo.agregar(Nodo("ε"))
    return nodo


def arbol_a_texto(nodo, prefijo="", es_ultimo=True, es_raiz=True):
    """Dibuja el árbol con ramas ├── └── (formato de la Fase 2, sección 9.2)."""
    lineas = []
    if es_raiz:
        lineas.append(nodo.texto())
    else:
        lineas.append(prefijo + ("└── " if es_ultimo else "├── ") + nodo.texto())
    hijo_prefijo = "" if es_raiz else prefijo + ("    " if es_ultimo else "│   ")
    for k, hijo in enumerate(nodo.hijos):
        lineas.extend(arbol_a_texto(hijo, hijo_prefijo,
                                    k == len(nodo.hijos) - 1, False))
    return lineas


def arbol_a_dot(raiz):
    """Exporta el árbol en formato Graphviz DOT (opcional, para verlo como imagen)."""
    lineas = ["digraph Arbol {", '  node [fontname="Helvetica", fontsize=10];']
    contador = [0]

    def visitar(nodo):
        mi_id = f"n{contador[0]}"
        contador[0] += 1
        etiqueta = nodo.texto().replace("\\", "\\\\").replace('"', '\\"')
        forma = "box" if nodo.es_terminal() or nodo.etiqueta == "ε" else "ellipse"
        lineas.append(f'  {mi_id} [label="{etiqueta}", shape={forma}];')
        for hijo in nodo.hijos:
            hijo_id = visitar(hijo)
            lineas.append(f"  {mi_id} -> {hijo_id};")
        return mi_id

    visitar(raiz)
    lineas.append("}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Errores sintácticos
# ---------------------------------------------------------------------------

class ErrorSintactico(Exception):
    def __init__(self, mensaje, token):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.token = token

    def __str__(self):
        return (f"Error sintáctico (línea {self.token.linea}, "
                f"columna {self.token.columna}): {self.mensaje}")


# ---------------------------------------------------------------------------
# El parser
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errores = []

    # --- utilidades -------------------------------------------------------

    @property
    def actual(self):
        return self.tokens[self.pos]

    def avanzar(self):
        token = self.actual
        if token.tipo != "$":
            self.pos += 1
        return token

    def coincidir(self, tipo, mensaje=None):
        """Consume un terminal del tipo esperado y devuelve su nodo hoja."""
        if self.actual.tipo == tipo:
            token = self.avanzar()
            return Nodo(tipo, token)
        if mensaje is None:
            mensaje = (f"se esperaba {legible(tipo)}, "
                       f"pero se encontró {self._describir(self.actual)}")
        raise ErrorSintactico(mensaje, self.actual)

    @staticmethod
    def _describir(token):
        if token.tipo == "$":
            return "el fin del archivo"
        return f"'{token.lexema}'"

    # Tokens donde la recuperación puede reanudar el análisis con seguridad.
    # ID no está: suele aparecer en mitad de una instrucción dañada
    # (por ejemplo 'do9' o una variable dentro de una expresión).
    _PUNTOS_SEGUROS = (PRIMERO_INSTRUCCION - {"ID"}) | SIGUIENTE_LISTA_INSTR

    def sincronizar(self):
        """
        Recuperación en modo pánico: tras un error se descartan tokens hasta
        un punto seguro (un ';' que se consume, una palabra que inicia otra
        instrucción, un '|' o el fin del archivo). Permite reportar varios
        errores independientes en una sola ejecución sin errores en cascada.
        """
        while self.actual.tipo not in self._PUNTOS_SEGUROS:
            if self.actual.tipo == ";":
                self.avanzar()
                return
            self.avanzar()

    def esperar_palabra(self, palabra):
        """
        Consume 'entonces' o 'hacer'. Si falta, registra el error y se salta
        lo que sobre hasta encontrar la palabra o el '|' que abre el bloque,
        para seguir analizando el bloque en lugar de producir errores en
        cascada por sus barras.
        """
        if self.actual.tipo == palabra:
            return self.coincidir(palabra)
        self.errores.append(ErrorSintactico(self._falta_palabra(palabra), self.actual))
        while self.actual.tipo not in (palabra, "|", ";", "$"):
            self.avanzar()
        if self.actual.tipo == palabra:
            return self.coincidir(palabra)
        if self.actual.tipo == "|":
            return Nodo("ERROR")
        raise ErrorSintactico("no se encontró el bloque después de la condición",
                              self.actual)

    # --- Programa e instrucciones ----------------------------------------

    def programa(self):
        # Regla 1: <programa> ::= <lista_instr> $
        nodo = Nodo("<programa>")
        nodo.agregar(self.lista_instr())
        # Un '|' sobrante deja <lista_instr> en ε sin llegar al fin del archivo.
        while self.actual.tipo != "$":
            self.errores.append(ErrorSintactico(
                "barra '|' de cierre sin un bloque abierto"
                if self.actual.tipo == "|" else
                f"se esperaba el fin del archivo, pero se encontró "
                f"{self._describir(self.actual)}", self.actual))
            self.avanzar()
            self.lista_instr()
        nodo.agregar(self.coincidir("$"))
        return nodo

    def lista_instr(self):
        # Regla 2: <lista_instr> ::= <instruccion> <lista_instr>
        # Regla 3:                 | ε
        if self.actual.tipo in PRIMERO_INSTRUCCION:
            nodo = Nodo("<lista_instr>")
            try:
                nodo.agregar(self.instruccion())
            except ErrorSintactico as error:
                self.errores.append(error)
                self.sincronizar()
                nodo.agregar(Nodo("ERROR"))
            nodo.agregar(self.lista_instr())
            return nodo

        if self.actual.tipo in SIGUIENTE_LISTA_INSTR:
            return vacio("<lista_instr>")

        # El token no inicia una instrucción ni cierra la lista.
        self.errores.append(ErrorSintactico(
            f"{self._describir(self.actual)} no puede iniciar una instrucción",
            self.actual))
        self.avanzar()
        self.sincronizar()
        return self.lista_instr()

    def instruccion(self):
        nodo = Nodo("<instruccion>")
        t = self.actual.tipo
        if t in TIPOS:
            # Regla 4: <declaracion> ";"
            nodo.agregar(self.declaracion())
            nodo.agregar(self.coincidir(";", self._falta_punto_coma("la declaración")))
        elif t == "ID":
            # Regla 5: <asignacion> ";"
            nodo.agregar(self.asignacion())
            nodo.agregar(self.coincidir(";", self._falta_punto_coma("la asignación")))
        elif t == "tocar":
            # Regla 6: <tocar_instr> ";"
            nodo.agregar(self.tocar_instr())
            nodo.agregar(self.coincidir(";", self._falta_punto_coma("la instrucción tocar")))
        elif t == "silencio":
            # Regla 7: <silencio_instr> ";"
            nodo.agregar(self.silencio_instr())
            nodo.agregar(self.coincidir(";", self._falta_punto_coma("la instrucción silencio")))
        elif t == "tempo":
            # Regla 8: <tempo_instr> ";"
            nodo.agregar(self.tempo_instr())
            nodo.agregar(self.coincidir(";", self._falta_punto_coma("la instrucción tempo")))
        elif t == "mostrar":
            # Regla 9: <mostrar_instr> ";"
            nodo.agregar(self.mostrar_instr())
            nodo.agregar(self.coincidir(";", self._falta_punto_coma("la instrucción mostrar")))
        elif t == "si":
            # Regla 10: <condicional>
            nodo.agregar(self.condicional())
        elif t == "mientras":
            # Regla 11: <ciclo>
            nodo.agregar(self.ciclo())
        else:
            raise ErrorSintactico(
                f"{self._describir(self.actual)} no puede iniciar una instrucción",
                self.actual)
        return nodo

    def _falta_punto_coma(self, donde):
        return (f"se esperaba ';' al final de {donde}, "
                f"pero se encontró {self._describir(self.actual)}")

    # --- Declaración y asignación ----------------------------------------

    def declaracion(self):
        # Regla 12: <declaracion> ::= <tipo> ID <decl_resto>
        nodo = Nodo("<declaracion>")
        nodo.agregar(self.tipo())
        nodo.agregar(self.coincidir("ID"))
        nodo.agregar(self.decl_resto())
        return nodo

    def decl_resto(self):
        # Regla 13: <decl_resto> ::= "=" <expresion>
        # Regla 14:                | ε
        if self.actual.tipo == "=":
            nodo = Nodo("<decl_resto>")
            nodo.agregar(self.coincidir("="))
            nodo.agregar(self.expresion())
            return nodo
        return vacio("<decl_resto>")

    def tipo(self):
        # Reglas 15 a 18: <tipo> ::= entero | decimal | texto | booleano
        nodo = Nodo("<tipo>")
        if self.actual.tipo in TIPOS:
            nodo.agregar(self.coincidir(self.actual.tipo))
            return nodo
        raise ErrorSintactico("se esperaba un tipo (entero, decimal, texto o booleano)",
                              self.actual)

    def asignacion(self):
        # Regla 19: <asignacion> ::= ID "=" <expresion>
        nodo = Nodo("<asignacion>")
        nodo.agregar(self.coincidir("ID"))
        nodo.agregar(self.coincidir("=", f"se esperaba '=' después de "
                                         f"'{self.tokens[self.pos - 1].lexema}' "
                                         f"para asignarle un valor"))
        nodo.agregar(self.expresion())
        return nodo

    # --- Instrucciones musicales y de salida -----------------------------

    def tocar_instr(self):
        # Regla 20: <tocar_instr> ::= tocar NOTA <expresion>
        nodo = Nodo("<tocar_instr>")
        nodo.agregar(self.coincidir("tocar"))
        nodo.agregar(self.coincidir("NOTA", self._mensaje_nota()))
        nodo.agregar(self.expresion_requerida("la duración de la nota"))
        return nodo

    def _mensaje_nota(self):
        token = self.actual
        palabra = token.lexema
        for nombre in NOMBRES_NOTA:
            if token.tipo == "ID" and palabra.startswith(nombre) and palabra[len(nombre):].isdigit():
                return (f"'{palabra}' no es una nota válida: la octava debe "
                        f"estar entre 1 y 7 (por ejemplo {nombre}4)")
        return (f"se esperaba una nota (do1 a si7) después de 'tocar', "
                f"pero se encontró {self._describir(token)}")

    def silencio_instr(self):
        # Regla 21: <silencio_instr> ::= silencio <expresion>
        nodo = Nodo("<silencio_instr>")
        nodo.agregar(self.coincidir("silencio"))
        nodo.agregar(self.expresion_requerida("la duración del silencio"))
        return nodo

    def tempo_instr(self):
        # Regla 22: <tempo_instr> ::= tempo <expresion>
        nodo = Nodo("<tempo_instr>")
        nodo.agregar(self.coincidir("tempo"))
        nodo.agregar(self.expresion_requerida("el valor del tempo"))
        return nodo

    def mostrar_instr(self):
        # Regla 23: <mostrar_instr> ::= mostrar "(" <lista_args> ")"
        nodo = Nodo("<mostrar_instr>")
        nodo.agregar(self.coincidir("mostrar"))
        nodo.agregar(self.coincidir("("))
        nodo.agregar(self.lista_args())
        nodo.agregar(self.coincidir(")"))
        return nodo

    def lista_args(self):
        # Regla 24: <lista_args> ::= <expresion> <args_resto>
        nodo = Nodo("<lista_args>")
        nodo.agregar(self.expresion_requerida("lo que se va a mostrar"))
        nodo.agregar(self.args_resto())
        return nodo

    def args_resto(self):
        # Regla 25: <args_resto> ::= "," <expresion> <args_resto>
        # Regla 26:                | ε
        if self.actual.tipo == ",":
            nodo = Nodo("<args_resto>")
            nodo.agregar(self.coincidir(","))
            nodo.agregar(self.expresion())
            nodo.agregar(self.args_resto())
            return nodo
        return vacio("<args_resto>")

    # --- Control de flujo -------------------------------------------------

    def condicional(self):
        # Regla 27: <condicional> ::= si <expresion> entonces <bloque> <sino_parte>
        nodo = Nodo("<condicional>")
        nodo.agregar(self.coincidir("si"))
        nodo.agregar(self.expresion_requerida("la condición"))
        nodo.agregar(self.esperar_palabra("entonces"))
        nodo.agregar(self.bloque())
        nodo.agregar(self.sino_parte())
        return nodo

    def sino_parte(self):
        # Regla 28: <sino_parte> ::= sino <bloque>
        # Regla 29:                | ε
        if self.actual.tipo == "sino":
            nodo = Nodo("<sino_parte>")
            nodo.agregar(self.coincidir("sino"))
            nodo.agregar(self.bloque())
            return nodo
        return vacio("<sino_parte>")

    def ciclo(self):
        # Regla 30: <ciclo> ::= mientras <expresion> hacer <bloque>
        nodo = Nodo("<ciclo>")
        nodo.agregar(self.coincidir("mientras"))
        nodo.agregar(self.expresion_requerida("la condición"))
        nodo.agregar(self.esperar_palabra("hacer"))
        nodo.agregar(self.bloque())
        return nodo

    def _falta_palabra(self, palabra):
        mensaje = (f"se esperaba '{palabra}' después de la condición, "
                   f"pero se encontró {self._describir(self.actual)}")
        if self.actual.tipo in RELS:
            mensaje += " (los operadores relacionales no se pueden encadenar)"
        return mensaje

    def bloque(self):
        # Regla 31: <bloque> ::= "|" <lista_instr> "|"
        nodo = Nodo("<bloque>")
        abre = self.coincidir("|", f"se esperaba '|' para abrir el bloque, "
                                   f"pero se encontró {self._describir(self.actual)}")
        nodo.agregar(abre)
        nodo.agregar(self.lista_instr())
        nodo.agregar(self.coincidir(
            "|", f"falta la barra '|' que cierra el bloque abierto en la "
                 f"línea {abre.token.linea}"))
        return nodo

    # --- Expresiones ------------------------------------------------------

    def expresion_requerida(self, que):
        """<expresion> cuando el token actual ni siquiera puede iniciarla."""
        if self.actual.tipo not in PRIMERO_EXPRESION:
            raise ErrorSintactico(
                f"falta {que}: se encontró {self._describir(self.actual)}",
                self.actual)
        return self.expresion()

    def expresion(self):
        # Regla 32: <expresion> ::= <expr_arit> <rel_resto>
        nodo = Nodo("<expresion>")
        nodo.agregar(self.expr_arit())
        nodo.agregar(self.rel_resto())
        return nodo

    def rel_resto(self):
        # Regla 33: <rel_resto> ::= <op_rel> <expr_arit>
        # Regla 34:               | ε
        if self.actual.tipo in RELS:
            nodo = Nodo("<rel_resto>")
            nodo.agregar(self.op_rel())
            nodo.agregar(self.expr_arit())
            return nodo
        return vacio("<rel_resto>")

    def op_rel(self):
        # Reglas 35 a 40: <op_rel> ::= "==" | "!=" | "<" | ">" | "<=" | ">="
        nodo = Nodo("<op_rel>")
        nodo.agregar(self.coincidir(self.actual.tipo))
        return nodo

    def expr_arit(self):
        # Regla 41: <expr_arit> ::= <termino> <expr_arit'>
        nodo = Nodo("<expr_arit>")
        nodo.agregar(self.termino())
        nodo.agregar(self.expr_arit_prima())
        return nodo

    def expr_arit_prima(self):
        # Regla 42: <expr_arit'> ::= "+" <termino> <expr_arit'>
        # Regla 43:                | "-" <termino> <expr_arit'>
        # Regla 44:                | ε
        if self.actual.tipo in ("+", "-"):
            nodo = Nodo("<expr_arit'>")
            nodo.agregar(self.coincidir(self.actual.tipo))
            nodo.agregar(self.termino())
            nodo.agregar(self.expr_arit_prima())
            return nodo
        return vacio("<expr_arit'>")

    def termino(self):
        # Regla 45: <termino> ::= <factor> <termino'>
        nodo = Nodo("<termino>")
        nodo.agregar(self.factor())
        nodo.agregar(self.termino_prima())
        return nodo

    def termino_prima(self):
        # Regla 46: <termino'> ::= "*" <factor> <termino'>
        # Regla 47:              | "/" <factor> <termino'>
        # Regla 48:              | ε
        if self.actual.tipo in ("*", "/"):
            nodo = Nodo("<termino'>")
            nodo.agregar(self.coincidir(self.actual.tipo))
            nodo.agregar(self.factor())
            nodo.agregar(self.termino_prima())
            return nodo
        return vacio("<termino'>")

    def factor(self):
        nodo = Nodo("<factor>")
        t = self.actual.tipo
        if t == "(":
            # Regla 49: "(" <expresion> ")"
            nodo.agregar(self.coincidir("("))
            nodo.agregar(self.expresion())
            nodo.agregar(self.coincidir(")"))
        elif t == "-":
            # Regla 50: "-" <factor>
            nodo.agregar(self.coincidir("-"))
            nodo.agregar(self.factor())
        elif t in ("ID", "NUM_ENT", "NUM_DEC", "CADENA", "verdadero", "falso"):
            # Reglas 51 a 56
            nodo.agregar(self.coincidir(t))
        elif t == "leer":
            # Regla 57: leer "(" CADENA ")"
            nodo.agregar(self.coincidir("leer"))
            nodo.agregar(self.coincidir("("))
            nodo.agregar(self.coincidir("CADENA", "leer(...) recibe un mensaje entre comillas"))
            nodo.agregar(self.coincidir(")"))
        else:
            raise ErrorSintactico(
                f"se esperaba un valor (número, texto, variable, verdadero, "
                f"falso, leer o '('), pero se encontró {self._describir(self.actual)}",
                self.actual)
        return nodo


# ---------------------------------------------------------------------------
# Función de alto nivel
# ---------------------------------------------------------------------------

def analizar(texto):
    """
    Ejecuta lexer + parser sobre el texto.
    Devuelve (arbol, tokens, errores_lexicos, errores_sintacticos).
    Si hay errores léxicos no se ejecuta el parser: los tokens estarían incompletos.
    """
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
    tokens, errores_lexicos = tokenizar(texto)
    if errores_lexicos:
        return None, tokens, errores_lexicos, []
    parser = Parser(tokens)
    arbol = parser.programa()
    return arbol, tokens, [], parser.errores
