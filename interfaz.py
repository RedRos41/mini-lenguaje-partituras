"""
Interfaz gráfica del mini-lenguaje de partituras.

Un editor donde se escribe o se carga un programa y, con un botón:
  - Analizar (F5): tokens (Fase 1) y árbol de derivación o errores (Fase 2).
  - Ejecutar y escuchar (F6): corre el intérprete y reproduce el audio (extra).

Al hacer clic en un nodo del árbol se resalta en el editor el fragmento de
código que ese nodo deriva. Doble clic en un token o en un error lleva a su
posición en el código.

Usa solo tkinter, que viene incluido con Python. Cómo abrirla:
    python interfaz.py
    (o doble clic en iniciar.bat, o el botón ▶ de VS Code con este archivo abierto)
"""

import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    from tkinter import font as tkfont
except ImportError:          # algunas instalaciones de Linux no incluyen tkinter
    print("Esta instalación de Python no incluye tkinter, así que la interfaz "
          "gráfica no puede abrirse.")
    print("Usa el menú de consola en su lugar:  python main.py")
    sys.exit(1)

from lexico import tokenizar, RESERVADAS
from sintactico import analizar as analizar_programa, arbol_a_texto, arbol_a_dot
from interprete import Interprete, ErrorEjecucion

CARPETA = Path(__file__).resolve().parent
EJEMPLOS = CARPETA / "ejemplos"
ERRORES = CARPETA / "errores"
SALIDAS = CARPETA / "salidas"

PLANTILLA = """# Nuevo programa
tempo 120;
tocar do4 1/4; tocar mi4 1/4; tocar sol4 1/4;
tocar do5 1/2;
"""


def ruta_corta(ruta):
    """Ruta relativa a la carpeta del proyecto cuando es posible."""
    try:
        return str(ruta.resolve().relative_to(CARPETA))
    except ValueError:
        return str(ruta)


# ---------------------------------------------------------------------------
# Reproducción de audio sin librerías externas
# ---------------------------------------------------------------------------

class Reproductor:
    """Reproduce un .wav con lo que ofrezca el sistema operativo."""

    def __init__(self):
        self.proceso = None

    def reproducir(self, ruta):
        self.detener()
        if sys.platform.startswith("win"):
            import winsound
            winsound.PlaySound(str(ruta), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        if sys.platform == "darwin":
            candidatos = [["afplay"]]
        else:
            candidatos = [["paplay"], ["aplay", "-q"],
                          ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]]
        for comando in candidatos:
            if shutil.which(comando[0]):
                self.proceso = subprocess.Popen(comando + [str(ruta)],
                                                stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL)
                return True
        return False

    def detener(self):
        if sys.platform.startswith("win"):
            import winsound
            winsound.PlaySound(None, 0)
        if self.proceso is not None and self.proceso.poll() is None:
            self.proceso.terminate()
        self.proceso = None


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class Aplicacion:
    def __init__(self, raiz, archivo_inicial=None):
        self.raiz = raiz
        self.ruta = None              # archivo abierto (None = programa nuevo)
        self.guardado = ""            # texto tal como está en disco
        self.arbol = None             # último árbol válido
        self.ultimo_wav = None
        self.reproductor = Reproductor()
        self._pendiente = None        # refresco del editor programado
        self._rango_de_item = {}      # nodo del árbol -> (primer token, último token)
        self._lineas_mostradas = 0

        raiz.geometry("1280x780")
        raiz.minsize(920, 560)
        self._crear_fuentes()
        self._crear_estilos()
        self._crear_menu()
        self._crear_barra()
        self._crear_estado()          # antes que los paneles, para que no quede oculta
        self._crear_paneles()
        self._crear_atajos()
        raiz.protocol("WM_DELETE_WINDOW", self.salir)

        inicial = Path(archivo_inicial) if archivo_inicial else EJEMPLOS / "tempo_acelera.part"
        if inicial.exists():
            self.abrir(inicial, preguntar=False)
        else:
            self.nuevo(preguntar=False)
        self.editor.focus_set()

    # --- construcción -------------------------------------------------------

    def _crear_fuentes(self):
        disponibles = set(tkfont.families(self.raiz))
        familia = next((f for f in ("Consolas", "Cascadia Mono", "Menlo", "SF Mono",
                                    "DejaVu Sans Mono", "Liberation Mono")
                        if f in disponibles),
                       tkfont.nametofont("TkFixedFont").actual("family"))
        self.mono = tkfont.Font(self.raiz, family=familia, size=11)
        self.mono_negrita = tkfont.Font(self.raiz, family=familia, size=11, weight="bold")
        self.mono_cursiva = tkfont.Font(self.raiz, family=familia, size=11, slant="italic")
        base = tkfont.nametofont("TkDefaultFont").actual()
        self.titulo = tkfont.Font(self.raiz, family=base["family"], size=10, weight="bold")

    def _crear_estilos(self):
        estilo = ttk.Style(self.raiz)
        if estilo.theme_use() == "default" and "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=22)
        estilo.configure("Principal.TButton", padding=(10, 4))

    def _crear_menu(self):
        barra = tk.Menu(self.raiz)

        archivo = tk.Menu(barra, tearoff=False)
        archivo.add_command(label="Nuevo", accelerator="Ctrl+N", command=self.nuevo)
        archivo.add_command(label="Abrir…", accelerator="Ctrl+O", command=self.abrir)
        archivo.add_command(label="Guardar", accelerator="Ctrl+S", command=self.guardar)
        archivo.add_command(label="Guardar como…", command=self.guardar_como)
        archivo.add_separator()
        archivo.add_command(label="Exportar árbol a Graphviz (.dot)…", command=self.exportar_dot)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.salir)
        barra.add_cascade(label="Archivo", menu=archivo)

        ejemplos = tk.Menu(barra, tearoff=False)
        for titulo, carpeta in (("Programas válidos", EJEMPLOS),
                                ("Programas con errores", ERRORES)):
            submenu = tk.Menu(ejemplos, tearoff=False)
            for ruta in sorted(carpeta.glob("*.part")):
                submenu.add_command(label=self._titulo_ejemplo(ruta),
                                    command=lambda r=ruta: self.abrir(r))
            ejemplos.add_cascade(label=titulo, menu=submenu)
        barra.add_cascade(label="Ejemplos", menu=ejemplos)

        programa = tk.Menu(barra, tearoff=False)
        programa.add_command(label="Analizar", accelerator="F5", command=self.analizar)
        programa.add_command(label="Ejecutar y escuchar", accelerator="F6", command=self.ejecutar)
        programa.add_command(label="Repetir audio", command=self.reproducir)
        programa.add_command(label="Detener audio", command=self.reproductor.detener)
        barra.add_cascade(label="Programa", menu=programa)

        ayuda = tk.Menu(barra, tearoff=False)
        ayuda.add_command(label="Cómo usar la interfaz", command=self.mostrar_ayuda)
        barra.add_cascade(label="Ayuda", menu=ayuda)

        self.raiz.config(menu=barra)

    @staticmethod
    def _titulo_ejemplo(ruta):
        partes = ruta.stem.split("_")
        if partes[0].isdigit():
            return f"{partes[0]} · " + " ".join(partes[1:]).capitalize()
        return " ".join(partes).capitalize()

    def _crear_barra(self):
        barra = ttk.Frame(self.raiz, padding=(8, 6))
        barra.pack(side="top", fill="x")
        ttk.Button(barra, text="▶  Analizar  (F5)", style="Principal.TButton",
                   command=self.analizar).pack(side="left")
        ttk.Button(barra, text="♪  Ejecutar y escuchar  (F6)", style="Principal.TButton",
                   command=self.ejecutar).pack(side="left", padx=(6, 0))
        self.boton_repetir = ttk.Button(barra, text="⟳  Repetir audio",
                                        command=self.reproducir, state="disabled")
        self.boton_repetir.pack(side="left", padx=(6, 0))
        ttk.Button(barra, text="■  Detener",
                   command=self.reproductor.detener).pack(side="left", padx=(6, 0))
        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(barra, text="Abrir…", command=self.abrir).pack(side="left")
        ttk.Button(barra, text="Guardar", command=self.guardar).pack(side="left", padx=(6, 0))
        self.etiqueta_archivo = ttk.Label(barra, text="", foreground="#555555")
        self.etiqueta_archivo.pack(side="right")

    def _crear_estado(self):
        barra = ttk.Frame(self.raiz, padding=(10, 3))
        barra.pack(side="bottom", fill="x")
        self.estado = ttk.Label(barra, text="Listo")
        self.estado.pack(side="left")
        self.posicion = ttk.Label(barra, text="Línea 1, columna 1", foreground="#555555")
        self.posicion.pack(side="right")

    def _crear_paneles(self):
        panel = ttk.Panedwindow(self.raiz, orient="horizontal")
        panel.pack(fill="both", expand=True, padx=8, pady=(0, 2))
        panel.add(self._crear_editor(panel), weight=1)
        panel.add(self._crear_resultados(panel), weight=1)

    def _crear_editor(self, padre):
        marco = ttk.Frame(padre)
        ttk.Label(marco, text="Programa", font=self.titulo).pack(anchor="w", pady=(0, 4))
        area = ttk.Frame(marco, borderwidth=1, relief="solid")
        area.pack(fill="both", expand=True)

        self.numeros = tk.Text(area, width=4, padx=6, pady=6, takefocus=0, borderwidth=0,
                               highlightthickness=0, font=self.mono, cursor="arrow",
                               background="#f3f4f6", foreground="#9ca3af", state="disabled")
        self.numeros.tag_configure("derecha", justify="right")
        self.editor = tk.Text(area, wrap="none", undo=True, maxundo=-1, font=self.mono,
                              borderwidth=0, highlightthickness=0, padx=8, pady=6,
                              background="#ffffff", foreground="#111827",
                              insertbackground="#111827", selectbackground="#bfdbfe",
                              inactiveselectbackground="#dbeafe")
        self.editor.configure(tabs=(self.mono.measure("    "),))
        vertical = ttk.Scrollbar(area, orient="vertical", command=self._desplazar)
        horizontal = ttk.Scrollbar(area, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=lambda a, b: self._sincronizar(vertical, a, b),
                              xscrollcommand=horizontal.set)

        self.numeros.grid(row=0, column=0, sticky="ns")
        self.editor.grid(row=0, column=1, sticky="nsew")
        vertical.grid(row=0, column=2, sticky="ns")
        horizontal.grid(row=1, column=1, sticky="ew")
        area.rowconfigure(0, weight=1)
        area.columnconfigure(1, weight=1)
        for evento in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.numeros.bind(evento, lambda e: "break")

        e = self.editor
        e.tag_configure("reservada", foreground="#1d4ed8", font=self.mono_negrita)
        e.tag_configure("nota", foreground="#7c3aed", font=self.mono_negrita)
        e.tag_configure("numero", foreground="#b45309")
        e.tag_configure("cadena", foreground="#047857")
        e.tag_configure("comentario", foreground="#6b7280", font=self.mono_cursiva)
        e.tag_configure("bloque", foreground="#be123c", font=self.mono_negrita)
        e.tag_configure("seleccion_arbol", background="#fef08a")
        e.tag_configure("linea_error", background="#fde2e2")
        e.tag_configure("pos_error", underline=True, foreground="#b91c1c")
        e.tag_raise("sel")
        return marco

    def _crear_resultados(self, padre):
        marco = ttk.Frame(padre)
        ttk.Label(marco, text="Resultados", font=self.titulo).pack(anchor="w", pady=(0, 4))
        self.pestanas = ttk.Notebook(marco)
        self.pestanas.pack(fill="both", expand=True)

        # Árbol desplegable
        self.pestana_arbol = ttk.Frame(self.pestanas, padding=4)
        botones = ttk.Frame(self.pestana_arbol)
        botones.pack(fill="x", pady=(0, 4))
        ttk.Button(botones, text="Expandir todo",
                   command=lambda: self._abrir_todo(True)).pack(side="left")
        ttk.Button(botones, text="Contraer todo",
                   command=lambda: self._abrir_todo(False)).pack(side="left", padx=(6, 0))
        ttk.Label(botones, text="Clic en un nodo: resalta su código",
                  foreground="#6b7280").pack(side="right")
        self.vista_arbol = self._con_barras(self.pestana_arbol, ttk.Treeview,
                                            show="tree", selectmode="browse")
        self.vista_arbol.tag_configure("noterminal", foreground="#1f2937")
        self.vista_arbol.tag_configure("terminal", foreground="#1d4ed8", font=self.mono_negrita)
        self.vista_arbol.tag_configure("epsilon", foreground="#9ca3af", font=self.mono_cursiva)
        self.vista_arbol.tag_configure("aviso", foreground="#b91c1c")
        self.vista_arbol.bind("<<TreeviewSelect>>", self._al_seleccionar_nodo)
        self.pestanas.add(self.pestana_arbol, text="Árbol")

        # Árbol en texto (el mismo formato que imprime main.py)
        self.pestana_texto = ttk.Frame(self.pestanas, padding=4)
        botones = ttk.Frame(self.pestana_texto)
        botones.pack(fill="x", pady=(0, 4))
        ttk.Button(botones, text="Copiar al portapapeles",
                   command=self._copiar_arbol).pack(side="left")
        self.texto_arbol = self._con_barras(self.pestana_texto, tk.Text, wrap="none",
                                            font=self.mono, state="disabled",
                                            borderwidth=0, padx=6, pady=4)
        self.pestanas.add(self.pestana_texto, text="Árbol en texto")

        # Tokens
        self.pestana_tokens = ttk.Frame(self.pestanas, padding=4)
        ttk.Label(self.pestana_tokens, text="Secuencia de tokens del AFD (Fase 1). "
                  "Doble clic: ir al código.", foreground="#6b7280").pack(anchor="w", pady=(0, 4))
        self.tabla_tokens = self._tabla(self.pestana_tokens,
                                        [("n", "#", 50), ("tipo", "Tipo (terminal)", 140),
                                         ("lexema", "Lexema", 180), ("linea", "Línea", 60),
                                         ("columna", "Columna", 70)])
        self.tabla_tokens.bind("<Double-1>", lambda e: self._ir_a_fila(self.tabla_tokens, 3, 4))
        self.pestanas.add(self.pestana_tokens, text="Tokens")

        # Errores
        self.pestana_errores = ttk.Frame(self.pestanas, padding=4)
        ttk.Label(self.pestana_errores, text="Errores léxicos, sintácticos y de ejecución. "
                  "Doble clic: ir al código.", foreground="#6b7280").pack(anchor="w", pady=(0, 4))
        self.tabla_errores = self._tabla(self.pestana_errores,
                                         [("tipo", "Tipo", 90), ("linea", "Línea", 60),
                                          ("columna", "Columna", 80), ("mensaje", "Mensaje", 520)])
        self.tabla_errores.tag_configure("error", foreground="#b91c1c")
        self.tabla_errores.bind("<Double-1>", lambda e: self._ir_a_fila(self.tabla_errores, 1, 2))
        self.tabla_errores.bind("<<TreeviewSelect>>", self._al_seleccionar_error)
        self.detalle_error = ttk.Label(self.pestana_errores, text="", foreground="#b91c1c",
                                       wraplength=560, justify="left", padding=(2, 6))
        self.detalle_error.pack(fill="x", side="bottom")
        self.pestana_errores.bind(
            "<Configure>", lambda e: self.detalle_error.configure(wraplength=max(e.width - 20, 200)))
        self.pestanas.add(self.pestana_errores, text="Errores")

        # Ejecución
        self.pestana_ejecucion = ttk.Frame(self.pestanas, padding=4)
        self.texto_salida = self._con_barras(self.pestana_ejecucion, tk.Text, wrap="word",
                                             font=self.mono, state="disabled",
                                             borderwidth=0, padx=6, pady=4)
        self.texto_salida.tag_configure("titulo", font=self.mono_negrita)
        self.texto_salida.tag_configure("entrada", foreground="#1d4ed8")
        self.texto_salida.tag_configure("ok", foreground="#047857", font=self.mono_negrita)
        self.texto_salida.tag_configure("error", foreground="#b91c1c", font=self.mono_negrita)
        self.pestanas.add(self.pestana_ejecucion, text="Ejecución")
        return marco

    def _con_barras(self, padre, clase, **opciones):
        """Crea un widget con barras de desplazamiento vertical y horizontal."""
        contenedor = ttk.Frame(padre)
        contenedor.pack(fill="both", expand=True)
        widget = clase(contenedor, **opciones)
        vertical = ttk.Scrollbar(contenedor, orient="vertical", command=widget.yview)
        horizontal = ttk.Scrollbar(contenedor, orient="horizontal", command=widget.xview)
        widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        widget.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        contenedor.rowconfigure(0, weight=1)
        contenedor.columnconfigure(0, weight=1)
        return widget

    def _tabla(self, padre, columnas):
        tabla = self._con_barras(padre, ttk.Treeview, show="headings",
                                 columns=[c[0] for c in columnas], selectmode="browse")
        for clave, titulo, ancho in columnas:
            tabla.heading(clave, text=titulo, anchor="w")
            tabla.column(clave, width=ancho, minwidth=40, anchor="w",
                         stretch=(clave in ("mensaje", "lexema")))
        return tabla

    def _crear_atajos(self):
        self._atajo("<F5>", self.analizar)
        self._atajo("<F6>", self.ejecutar)
        self._atajo("<Control-s>", self.guardar)
        self._atajo("<Control-o>", self.abrir)
        self._atajo("<Control-n>", self.nuevo)
        if sys.platform == "darwin":
            self._atajo("<Command-s>", self.guardar)
            self._atajo("<Command-o>", self.abrir)
            self._atajo("<Command-n>", self.nuevo)
        self.editor.bind("<<Modified>>", self._al_modificar)
        self.editor.bind("<KeyRelease>", self._actualizar_posicion)
        self.editor.bind("<ButtonRelease-1>", self._actualizar_posicion)

    def _atajo(self, secuencia, accion):
        def manejador(_evento):
            accion()
            return "break"           # evita, por ejemplo, que Ctrl+O inserte una línea
        self.raiz.bind(secuencia, manejador)
        self.editor.bind(secuencia, manejador)

    # --- editor ---------------------------------------------------------------

    def _desplazar(self, *argumentos):
        self.editor.yview(*argumentos)
        self.numeros.yview(*argumentos)

    def _sincronizar(self, barra, inicio, fin):
        barra.set(inicio, fin)
        self.numeros.yview_moveto(inicio)

    def _texto(self):
        return self.editor.get("1.0", "end-1c")

    def _hay_cambios(self):
        return self._texto() != self.guardado

    def _al_modificar(self, _evento=None):
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        self._actualizar_numeros()
        self._limpiar_marcas()
        if self._pendiente is not None:
            self.raiz.after_cancel(self._pendiente)
        self._pendiente = self.raiz.after(250, self._refrescar_editor)

    def _refrescar_editor(self):
        self._pendiente = None
        self._resaltar()
        self._actualizar_titulo()

    def _actualizar_numeros(self):
        lineas = int(self.editor.index("end-1c").split(".")[0])
        if lineas == self._lineas_mostradas:
            return
        self._lineas_mostradas = lineas
        self.numeros.configure(state="normal", width=max(3, len(str(lineas))) + 1)
        self.numeros.delete("1.0", "end")
        self.numeros.insert("1.0", "\n".join(str(i) for i in range(1, lineas + 1)), "derecha")
        self.numeros.configure(state="disabled")
        self.numeros.yview_moveto(self.editor.yview()[0])

    def _resaltar(self):
        """Colorea el código usando el propio lexer del proyecto."""
        texto = self._texto()
        for etiqueta in ("reservada", "nota", "numero", "cadena", "comentario", "bloque"):
            self.editor.tag_remove(etiqueta, "1.0", "end")
        tokens, _ = tokenizar(texto)
        for token in tokens:
            if token.tipo in RESERVADAS:
                etiqueta = "reservada"
            elif token.tipo == "NOTA":
                etiqueta = "nota"
            elif token.tipo in ("NUM_ENT", "NUM_DEC"):
                etiqueta = "numero"
            elif token.tipo == "CADENA":
                etiqueta = "cadena"
            elif token.tipo == "|":
                etiqueta = "bloque"
            else:
                continue
            inicio = f"{token.linea}.{token.columna - 1}"
            self.editor.tag_add(etiqueta, inicio, f"{inicio}+{len(token.lexema)}c")
        # El lexer descarta los comentarios (estado q7), así que se ubican aparte:
        # un '#' que no esté dentro de una cadena inicia un comentario.
        for numero, linea in enumerate(texto.split("\n"), 1):
            dentro_de_cadena = False
            for k, caracter in enumerate(linea):
                if caracter == '"':
                    dentro_de_cadena = not dentro_de_cadena
                elif caracter == "#" and not dentro_de_cadena:
                    self.editor.tag_add("comentario", f"{numero}.{k}", f"{numero}.end")
                    break

    def _limpiar_marcas(self):
        for etiqueta in ("linea_error", "pos_error", "seleccion_arbol"):
            self.editor.tag_remove(etiqueta, "1.0", "end")

    def _actualizar_posicion(self, _evento=None):
        linea, columna = self.editor.index("insert").split(".")
        self.posicion.configure(text=f"Línea {linea}, columna {int(columna) + 1}")

    def _actualizar_titulo(self):
        nombre = self.ruta.name if self.ruta else "Sin título"
        marca = "● " if self._hay_cambios() else ""
        self.raiz.title(f"{marca}{nombre} — Mini-lenguaje de partituras")
        self.etiqueta_archivo.configure(
            text=ruta_corta(self.ruta) if self.ruta else "Programa nuevo (sin guardar)")

    def _ir_a(self, linea, columna):
        indice = f"{linea}.{max(int(columna) - 1, 0)}"
        self.editor.mark_set("insert", indice)
        self.editor.see(indice)
        self.editor.focus_set()
        self._actualizar_posicion()

    def _ir_a_fila(self, tabla, col_linea, col_columna):
        fila = tabla.focus()
        if not fila:
            return
        valores = tabla.item(fila, "values")
        try:
            self._ir_a(int(valores[col_linea]), int(valores[col_columna]))
        except (ValueError, IndexError):
            pass

    def _mensaje(self, texto, error=False):
        self.estado.configure(text=texto, foreground="#b91c1c" if error else "#166534")

    # --- archivos -------------------------------------------------------------

    def _confirmar_descartar(self):
        """True si se puede reemplazar el contenido del editor."""
        if not self._hay_cambios():
            return True
        nombre = self.ruta.name if self.ruta else "el programa nuevo"
        respuesta = messagebox.askyesnocancel(
            "Cambios sin guardar", f"¿Quieres guardar los cambios en {nombre}?",
            parent=self.raiz)
        if respuesta is None:
            return False
        if respuesta:
            return self.guardar()
        return True

    def _cargar(self, texto, ruta):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", texto)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.ruta = ruta
        self.guardado = self._texto()
        self._limpiar_resultados()
        self._actualizar_numeros()
        self._resaltar()
        self._actualizar_titulo()
        self.editor.mark_set("insert", "1.0")
        self.editor.see("1.0")
        self._actualizar_posicion()

    def nuevo(self, preguntar=True):
        if preguntar and not self._confirmar_descartar():
            return
        self._cargar(PLANTILLA, None)
        self._mensaje("Programa nuevo: escribe tu código y presiona F5 para analizarlo")

    def abrir(self, ruta=None, preguntar=True):
        if preguntar and not self._confirmar_descartar():
            return
        if ruta is None:
            nombre = filedialog.askopenfilename(
                parent=self.raiz, title="Abrir programa", initialdir=str(EJEMPLOS),
                filetypes=[("Programas del mini-lenguaje", "*.part"),
                           ("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")])
            if not nombre:
                return
            ruta = Path(nombre)
        try:
            texto = Path(ruta).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            messagebox.showerror("No se pudo abrir",
                                 f"{ruta} no está guardado en UTF-8.", parent=self.raiz)
            return
        except OSError as error:
            messagebox.showerror("No se pudo abrir", str(error), parent=self.raiz)
            return
        self._cargar(texto.replace("\r\n", "\n"), Path(ruta))
        self.analizar()

    def guardar(self):
        if self.ruta is None:
            return self.guardar_como()
        return self._escribir_archivo(self.ruta)

    def guardar_como(self):
        nombre = filedialog.asksaveasfilename(
            parent=self.raiz, title="Guardar programa", defaultextension=".part",
            initialdir=str(self.ruta.parent if self.ruta else EJEMPLOS),
            initialfile=self.ruta.name if self.ruta else "mi_programa.part",
            filetypes=[("Programas del mini-lenguaje", "*.part"), ("Todos los archivos", "*.*")])
        if not nombre:
            return False
        return self._escribir_archivo(Path(nombre))

    def _escribir_archivo(self, ruta):
        texto = self._texto()
        try:
            ruta.write_text(texto, encoding="utf-8")
        except OSError as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.raiz)
            return False
        self.ruta = ruta
        self.guardado = texto
        self._actualizar_titulo()
        self._mensaje(f"Guardado en {ruta_corta(ruta)}")
        return True

    def exportar_dot(self):
        if self.arbol is None and not self.analizar():
            messagebox.showinfo("Sin árbol", "Corrige los errores antes de exportar el árbol.",
                                parent=self.raiz)
            return
        SALIDAS.mkdir(exist_ok=True)
        nombre = filedialog.asksaveasfilename(
            parent=self.raiz, title="Exportar árbol", defaultextension=".dot",
            initialdir=str(SALIDAS),
            initialfile=(self.ruta.stem if self.ruta else "programa") + ".dot",
            filetypes=[("Graphviz", "*.dot")])
        if nombre:
            Path(nombre).write_text(arbol_a_dot(self.arbol), encoding="utf-8")
            self._mensaje(f"Árbol exportado a {ruta_corta(Path(nombre))} "
                          f"(se puede ver en graphviz.online)")

    def salir(self):
        if self._confirmar_descartar():
            self.reproductor.detener()
            self.raiz.destroy()

    # --- análisis ---------------------------------------------------------------

    def _limpiar_resultados(self):
        self.arbol = None
        self._rango_de_item = {}
        for tabla in (self.vista_arbol, self.tabla_tokens, self.tabla_errores):
            tabla.delete(*tabla.get_children())
        for texto in (self.texto_arbol, self.texto_salida):
            texto.configure(state="normal")
            texto.delete("1.0", "end")
            texto.configure(state="disabled")
        self.pestanas.tab(self.pestana_tokens, text="Tokens")
        self.pestanas.tab(self.pestana_errores, text="Errores")
        self.detalle_error.configure(text="")
        self._limpiar_marcas()

    def analizar(self):
        """Lexer + parser sobre el texto del editor. Devuelve True si no hay errores."""
        self._limpiar_resultados()
        arbol, tokens, errores_lexicos, errores_sintacticos = analizar_programa(self._texto())

        for k, token in enumerate(tokens, 1):
            self.tabla_tokens.insert("", "end", values=(k, token.tipo, token.lexema,
                                                        token.linea, token.columna))
        self.pestanas.tab(self.pestana_tokens, text=f"Tokens ({len(tokens) - 1})")

        errores = [("Léxico", e.linea, e.columna, e.mensaje) for e in errores_lexicos]
        errores += [("Sintáctico", e.token.linea, e.token.columna, e.mensaje)
                    for e in errores_sintacticos]
        if errores:
            self._agregar_errores(errores)
            self._mostrar_arbol(None)
            self.pestanas.select(self.pestana_errores)
            fase = "léxico" if errores_lexicos else "sintáctico"
            self._mensaje(f"✗ {len(errores)} error(es) en el análisis {fase}. "
                          f"Doble clic en un error para ir a la línea.", error=True)
            self._ir_a(errores[0][1], errores[0][2])
            return False

        self.arbol = arbol
        total = self._mostrar_arbol(arbol)
        self.pestanas.select(self.pestana_arbol)
        self._mensaje(f"✓ Programa válido · {len(tokens) - 1} tokens · "
                      f"árbol de derivación de {total} nodos")
        return True

    def _agregar_errores(self, errores):
        for tipo, linea, columna, mensaje in errores:
            self.tabla_errores.insert("", "end", values=(tipo, linea, columna, mensaje),
                                      tags=("error",))
            if linea:
                inicio = f"{linea}.{max(int(columna) - 1, 0)}"
                fin = self.editor.index(f"{inicio} wordend")
                if self.editor.compare(fin, "<=", inicio):
                    fin = f"{inicio}+1c"
                self.editor.tag_add("linea_error", f"{linea}.0", f"{linea}.0 lineend+1c")
                self.editor.tag_add("pos_error", inicio, fin)
        filas = self.tabla_errores.get_children()
        self.pestanas.tab(self.pestana_errores, text=f"Errores ({len(filas)})")
        if filas:
            self.tabla_errores.selection_set(filas[0])
            self.tabla_errores.focus(filas[0])

    def _al_seleccionar_error(self, _evento=None):
        seleccion = self.tabla_errores.selection()
        if not seleccion:
            self.detalle_error.configure(text="")
            return
        tipo, linea, columna, mensaje = self.tabla_errores.item(seleccion[0], "values")
        donde = f" (línea {linea}, columna {columna})" if linea else ""
        self.detalle_error.configure(text=f"Error {tipo.lower()}{donde}: {mensaje}")

    def _mostrar_arbol(self, arbol):
        """Llena las dos pestañas del árbol. Devuelve el número de nodos."""
        self.texto_arbol.configure(state="normal")
        if arbol is None:
            aviso = "(No hay árbol: el programa tiene errores. Revisa la pestaña Errores.)"
            self.vista_arbol.insert("", "end", text=aviso, tags=("aviso",))
            self.texto_arbol.insert("1.0", aviso)
            self.texto_arbol.configure(state="disabled")
            return 0

        contador = [0]
        profundidad_maxima = [0]

        def agregar(padre, nodo, profundidad=0):
            contador[0] += 1
            profundidad_maxima[0] = max(profundidad_maxima[0], profundidad)
            if nodo.etiqueta == "ε":
                etiqueta = "epsilon"
            elif nodo.es_terminal():
                etiqueta = "terminal"
            else:
                etiqueta = "noterminal"
            item = self.vista_arbol.insert(padre, "end", text=nodo.texto(),
                                           open=True, tags=(etiqueta,))
            primero = ultimo = None
            if nodo.es_terminal() and nodo.token.tipo != "$":
                primero = ultimo = nodo.token
            for hijo in nodo.hijos:
                p, u = agregar(item, hijo, profundidad + 1)
                if p is not None:
                    primero = primero or p
                    ultimo = u
            if primero is not None:
                self._rango_de_item[item] = (primero, ultimo)
            return primero, ultimo

        agregar("", arbol)
        # Ancho suficiente para el nodo más profundo: así aparece la barra horizontal
        self.vista_arbol.column("#0", minwidth=profundidad_maxima[0] * 20 + 260, stretch=True)
        self.texto_arbol.insert("1.0", "\n".join(arbol_a_texto(arbol)))
        self.texto_arbol.configure(state="disabled")
        return contador[0]

    def _abrir_todo(self, abrir):
        pendientes = list(self.vista_arbol.get_children())
        while pendientes:
            item = pendientes.pop()
            self.vista_arbol.item(item, open=abrir)
            pendientes.extend(self.vista_arbol.get_children(item))

    def _al_seleccionar_nodo(self, _evento=None):
        self.editor.tag_remove("seleccion_arbol", "1.0", "end")
        seleccion = self.vista_arbol.selection()
        if not seleccion or seleccion[0] not in self._rango_de_item:
            return
        primero, ultimo = self._rango_de_item[seleccion[0]]
        inicio = f"{primero.linea}.{primero.columna - 1}"
        fin = f"{ultimo.linea}.{ultimo.columna - 1 + len(ultimo.lexema)}"
        self.editor.tag_add("seleccion_arbol", inicio, fin)
        self.editor.see(inicio)

    def _copiar_arbol(self):
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(self.texto_arbol.get("1.0", "end-1c"))
        self._mensaje("Árbol copiado al portapapeles")

    # --- ejecución ----------------------------------------------------------------

    def _escribir_salida(self, texto, etiqueta=None):
        self.texto_salida.configure(state="normal")
        self.texto_salida.insert("end", texto, etiqueta or ())
        self.texto_salida.see("end")
        self.texto_salida.configure(state="disabled")
        self.texto_salida.update_idletasks()

    def _leer(self, mensaje):
        """Lo que el intérprete usa para leer(...): una ventanita de entrada."""
        respuesta = simpledialog.askstring("leer(...)", mensaje, parent=self.raiz)
        if respuesta is None:
            raise EOFError
        self._escribir_salida(f"{mensaje}{respuesta}\n", "entrada")
        return respuesta

    def ejecutar(self):
        if not self.analizar():
            return
        self.reproductor.detener()
        self.pestanas.select(self.pestana_ejecucion)
        self._escribir_salida("=== Ejecución ===\n", "titulo")
        interprete = Interprete(leer_entrada=self._leer,
                                escribir=lambda texto: self._escribir_salida(texto + "\n"))
        self.raiz.configure(cursor="watch")
        try:
            interprete.ejecutar(self.arbol)
        except ErrorEjecucion as error:
            self._escribir_salida(f"\n✗ {error}\n", "error")
            token = error.token
            self._agregar_errores([("Ejecución", token.linea if token else "",
                                    token.columna if token else "", error.mensaje)])
            if token:
                self._ir_a(token.linea, token.columna)
            self._mensaje(f"✗ Error de ejecución: {error.mensaje}", error=True)
            return
        finally:
            self.raiz.configure(cursor="")

        if not interprete.audio:
            self._escribir_salida("\n(El programa no tocó ninguna nota: no se generó audio.)\n")
            self._mensaje("✓ Ejecución terminada (sin audio)")
            return
        SALIDAS.mkdir(exist_ok=True)
        destino = SALIDAS / ((self.ruta.stem if self.ruta else "programa") + ".wav")
        try:
            segundos = interprete.guardar_wav(destino)
        except OSError as error:
            messagebox.showerror("No se pudo guardar el audio", str(error), parent=self.raiz)
            return
        self.ultimo_wav = destino
        self.boton_repetir.configure(state="normal")
        self._escribir_salida(f"\nAudio generado: {ruta_corta(destino)} ({segundos:.1f} s)\n", "ok")
        if self.reproductor.reproducir(destino):
            self._mensaje(f"♪ Reproduciendo {destino.name} ({segundos:.1f} s) · "
                          f"■ Detener para pararlo")
        else:
            self._escribir_salida("(No se encontró un reproductor de audio: abre el .wav "
                                  "de la carpeta salidas manualmente.)\n")
            self._mensaje(f"✓ Audio guardado en {ruta_corta(destino)}")

    def reproducir(self):
        if self.ultimo_wav and self.ultimo_wav.exists():
            self.reproductor.reproducir(self.ultimo_wav)

    # --- ayuda ----------------------------------------------------------------------

    def mostrar_ayuda(self):
        messagebox.showinfo("Cómo usar la interfaz", (
            "1. Escribe un programa o abre uno del menú Ejemplos.\n"
            "2. ▶ Analizar (F5): muestra los tokens y el árbol de derivación, "
            "o los errores con su línea.\n"
            "3. ♪ Ejecutar y escuchar (F6): corre el programa y reproduce la música. "
            "El audio queda en la carpeta salidas.\n\n"
            "• Clic en un nodo del árbol: resalta en el editor el código que deriva.\n"
            "• Doble clic en un token o en un error: lleva a su posición.\n\n"
            "Atajos: F5 analizar · F6 ejecutar · Ctrl+S guardar · "
            "Ctrl+O abrir · Ctrl+N nuevo"), parent=self.raiz)


def iniciar(archivo=None):
    if sys.platform.startswith("win"):
        try:                      # texto nítido en pantallas con escala de Windows
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    raiz = tk.Tk()
    Aplicacion(raiz, archivo)
    raiz.mainloop()


if __name__ == "__main__":
    iniciar(sys.argv[1] if len(sys.argv) > 1 else None)
