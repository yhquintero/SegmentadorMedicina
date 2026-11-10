"""
Segmentador de libros PDF de Medicina — Versión GUI (Tkinter).
Esta es la versión que se compila con PyInstaller para crear el .exe.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import fitz
import re
import os
import traceback
from typing import List, Tuple, Optional

CHAPTER_PATTERN = re.compile(
    r"^\s*(cap[ií]tulo|chapter|secci[oó]n|section|parte|part|unidad|unit|tema|topic)"
    r"\s+([\dIVXLCDM]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)",
    re.IGNORECASE
)


# ---------------- LÓGICA CORE (compartida) ----------------
def limpiar_nombre_archivo(titulo: str, max_len: int = 100) -> str:
    nombre = re.sub(r'[\\/*?:"<>|]', "", titulo)
    nombre = re.sub(r"[\r\n\t]+", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    nombre = nombre[:max_len].strip()
    return nombre or "Capitulo_Sin_Titulo"


def abrir_pdf(ruta: str, password: Optional[str] = None) -> fitz.Document:
    doc = fitz.open(ruta)
    if doc.needs_pass:
        if not password:
            doc.close()
            raise RuntimeError("PDF protegido. Introduce la contraseña.")
        if not doc.authenticate(password):
            doc.close()
            raise RuntimeError("Contraseña incorrecta.")
    return doc


def obtener_capitulos_por_toc(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    toc = doc.get_toc(simple=True)
    if not toc:
        return []
    entradas = [(t.strip(), p) for l, t, p in toc if l == 1]
    cap: List[Tuple[str, int, int]] = []
    for i, (titulo, inicio) in enumerate(entradas):
        fin = entradas[i + 1][1] - 1 if i + 1 < len(entradas) else doc.page_count
        if 1 <= inicio <= fin <= doc.page_count:
            cap.append((titulo, inicio, fin))
    return cap


def detectar_capitulos_por_texto(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    cand: List[Tuple[str, int]] = []
    for idx in range(doc.page_count):
        try:
            txt = doc[idx].get_text("text")
        except Exception:
            continue
        if not txt:
            continue
        primera = txt.strip().split("\n")[0].strip()
        if CHAPTER_PATTERN.match(primera):
            cand.append((primera[:100], idx + 1))
    cap: List[Tuple[str, int, int]] = []
    for i, (titulo, inicio) in enumerate(cand):
        fin = cand[i + 1][1] - 1 if i + 1 < len(cand) else doc.page_count
        if inicio <= fin:
            cap.append((titulo, inicio, fin))
    return cap


# ---------------- GUI ----------------
class SegmentadorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Segmentador de Libros Médicos — PDF")
        self.geometry("820x640")
        self.minsize(720, 560)

        self.cola = queue.Queue()
        self.ruta_pdf = tk.StringVar()
        self.ruta_salida = tk.StringVar()
        self.password = tk.StringVar()
        self.procesando = False

        self._construir_ui()
        self.after(100, self._procesar_cola)

    def _construir_ui(self):
        ttk.Label(
            self, text="Segmentador de Libros Médicos (PDF → Capítulos)",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(12, 4))

        ttk.Label(
            self, text="Divide automáticamente por marcadores o por detección de texto.",
            foreground="#555"
        ).pack(pady=(0, 12))

        marco = ttk.LabelFrame(self, text=" Archivos ")
        marco.pack(fill="x", padx=12, pady=6)

        fila1 = ttk.Frame(marco)
        fila1.pack(fill="x", padx=8, pady=6)
        ttk.Label(fila1, text="PDF de entrada:", width=16).pack(side="left")
        ttk.Entry(fila1, textvariable=self.ruta_pdf).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(fila1, text="Elegir…", command=self._elegir_pdf).pack(side="left")

        fila2 = ttk.Frame(marco)
        fila2.pack(fill="x", padx=8, pady=6)
        ttk.Label(fila2, text="Carpeta de salida:", width=16).pack(side="left")
        ttk.Entry(fila2, textvariable=self.ruta_salida).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(fila2, text="Elegir…", command=self._elegir_salida).pack(side="left")

        fila3 = ttk.Frame(marco)
        fila3.pack(fill="x", padx=8, pady=6)
        ttk.Label(fila3, text="Contraseña (opcional):", width=16).pack(side="left")
        ttk.Entry(fila3, textvariable=self.password, show="•").pack(side="left", fill="x", expand=True, padx=4)

        acciones = ttk.Frame(self)
        acciones.pack(fill="x", padx=12, pady=8)
        self.btn_procesar = ttk.Button(acciones, text="▶  Segmentar PDF", command=self._iniciar)
        self.btn_procesar.pack(side="left")
        self.btn_limpiar = ttk.Button(acciones, text="🧹  Limpiar log", command=self._limpiar_log)
        self.btn_limpiar.pack(side="left", padx=6)

        self.barra = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.barra.pack(fill="x", padx=12, pady=(4, 0))

        self.log = scrolledtext.ScrolledText(self, height=18, wrap="word", state="disabled",
                                             font=("Consolas", 10))
        self.log.pack(fill="both", expand=True, padx=12, pady=12)

        self.status = ttk.Label(self, text="Listo.", foreground="#333")
        self.status.pack(fill="x", padx=12, pady=(0, 10))

    # ---------- Helpers de UI ----------
    def _elegir_pdf(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona el PDF",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos", "*.*")]
        )
        if ruta:
            self.ruta_pdf.set(ruta)
            if not self.ruta_salida.get():
                base = os.path.splitext(os.path.basename(ruta))[0]
                self.ruta_salida.set(os.path.join(os.path.dirname(ruta), f"{base}_capitulos"))

    def _elegir_salida(self):
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta de salida")
        if carpeta:
            self.ruta_salida.set(carpeta)

    def _log(self, texto: str):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _limpiar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.status.configure(text="Listo.")

    def _iniciar(self):
        if self.procesando:
            return
        entrada = self.ruta_pdf.get().strip()
        salida = self.ruta_salida.get().strip()
        if not entrada or not os.path.isfile(entrada):
            messagebox.showerror("Error", "Selecciona un PDF válido.")
            return
        if not salida:
            messagebox.showerror("Error", "Selecciona una carpeta de salida.")
            return

        self.procesando = True
        self.btn_procesar.configure(state="disabled")
        self.barra["value"] = 0
        self._log("=" * 60)
        self._log(f"📖 Entrada: {entrada}")
        self._log(f"📁 Salida:  {salida}")
        self._log("=" * 60)

        hilo = threading.Thread(
            target=self._worker,
            args=(entrada, salida, self.password.get() or None),
            daemon=True,
        )
        hilo.start()

    # ---------- Worker (hilo aparte) ----------
    def _worker(self, entrada: str, salida: str, password: Optional[str]):
        try:
            os.makedirs(salida, exist_ok=True)
            doc = abrir_pdf(entrada, password)

            self.cola.put(("log", "🔎 Buscando capítulos por marcadores (TOC)…"))
            capitulos = obtener_capitulos_por_toc(doc)
            metodo = "Marcadores (TOC)"

            if not capitulos:
                self.cola.put(("log", "⚠️  Sin marcadores. Probando detección por texto…"))
                capitulos = detectar_capitulos_por_texto(doc)
                metodo = "Detección de texto"

            if not capitulos:
                self.cola.put(("log", "❌ No se detectaron capítulos."))
                self.cola.put(("error", "No se detectaron capítulos. ¿Es un PDF escaneado? Necesita OCR."))
                doc.close()
                return

            total = len(capitulos)
            self.cola.put(("log", f"✅ {total} capítulos detectados vía {metodo}."))
            self.cola.put(("progress", 0))

            for i, (titulo, inicio, fin) in enumerate(capitulos, start=1):
                s_idx, e_idx = inicio - 1, fin - 1
                if s_idx < 0 or e_idx >= doc.page_count or s_idx > e_idx:
                    self.cola.put(("log", f"  ⚠️  Rango inválido: {titulo}"))
                    continue
                nombre = f"{i:02d}_{limpiar_nombre_archivo(titulo)}.pdf"
                try:
                    nuevo = fitz.open()
                    nuevo.insert_pdf(doc, from_page=s_idx, to_page=e_idx)
                    nuevo.save(os.path.join(salida, nombre), garbage=3, deflate=True)
                    nuevo.close()
                    self.cola.put(("log", f"  💾 [{i:02d}/{total}] {nombre}  (pp. {inicio}-{fin})"))
                except Exception as e:
                    self.cola.put(("log", f"  ❌ Error en '{nombre}': {e}"))
                self.cola.put(("progress", int(i * 100 / total)))

            doc.close()
            self.cola.put(("log", "🎉 Proceso finalizado con éxito."))
            self.cola.put(("done", f"{total} capítulos generados en:\n{salida}"))
        except Exception as e:
            self.cola.put(("log", f"❌ Error fatal: {e}"))
            self.cola.put(("log", traceback.format_exc()))
            self.cola.put(("error", str(e)))

    # ---------- Bombeo de la cola al hilo UI ----------
    def _procesar_cola(self):
        try:
            while True:
                tipo, valor = self.cola.get_nowait()
                if tipo == "log":
                    self._log(valor)
                elif tipo == "progress":
                    self.barra["value"] = valor
                elif tipo == "done":
                    self.barra["value"] = 100
                    self.status.configure(text="✅ Completado.")
                    messagebox.showinfo("Éxito", valor)
                    self.procesando = False
                    self.btn_procesar.configure(state="normal")
                elif tipo == "error":
                    self.status.configure(text="❌ Error.")
                    messagebox.showerror("Error", valor)
                    self.procesando = False
                    self.btn_procesar.configure(state="normal")
        except queue.Empty:
            pass
        self.after(100, self._procesar_cola)


if __name__ == "__main__":
    app = SegmentadorApp()
    app.mainloop()