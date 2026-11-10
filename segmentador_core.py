"""
Núcleo compartido de segmentación de libros PDF por capítulos.

Contiene la lógica pura (detección de capítulos, extracción y empaquetado)
usada por la vista Web (`app_web.py`) y por las pruebas automáticas.
Las versiones CLI (`segmentar_libros.py`) y GUI (`segmentar_libros_gui.py`)
mantienen su propia copia para poder empaquetarse de forma independiente.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF

# Patrón para detectar títulos de capítulo en el texto (plan B).
# Cubre: Capítulo 1, CAPÍTULO IV, Chapter 3, Sección 2.1, Unidad 5, Parte I…
PATRON_CAPITULO = re.compile(
    r"^\s*(cap[ií]tulo|chapter|secci[oó]n|section|parte|part|unidad|unit|tema|topic)"
    r"\s+([\dIVXLCDM]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)",
    re.IGNORECASE,
)

# Métodos de detección, con su nombre para la interfaz.
METODO_TOC = "Marcadores (TOC)"
METODO_TEXTO = "Detección de texto"

# Formatos de nombre de archivo admitidos: {n} = número, {t} = título limpio.
FORMATOS_NOMBRE = {
    "num": "{n:02d}_{t}",
    "cap": "Cap{n:02d}_{t}",
    "punto": "{n:02d}. {t}",
    "titulo": "{t}",
}


class ErrorSegmentador(RuntimeError):
    """Error controlado de segmentación (mensaje apto para mostrar al usuario)."""


@dataclass
class Capitulo:
    """Un capítulo detectado: título y rango de páginas (1-based, ambos incluidos)."""

    titulo: str
    inicio: int
    fin: int

    @property
    def paginas(self) -> int:
        return self.fin - self.inicio + 1


@dataclass
class InformeLibro:
    """Resultado del análisis de un PDF: metadatos y capítulos detectados."""

    nombre: str
    paginas: int
    protegido: bool
    metodo: str
    capitulos: List[Capitulo] = field(default_factory=list)

    @property
    def paginas_en_capitulos(self) -> int:
        return sum(c.paginas for c in self.capitulos)


def limpiar_nombre(titulo: str, max_len: int = 100, por_defecto: str = "Capitulo_Sin_Titulo") -> str:
    """Convierte un título en un nombre de archivo válido y seguro."""
    nombre = re.sub(r'[\\/*?:"<>|]', "", titulo)
    nombre = re.sub(r"[\r\n\t]+", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    nombre = nombre[:max_len].strip()
    return nombre or por_defecto


def nombre_archivo(indice: int, titulo: str, formato: str = "num") -> str:
    """Nombre final del PDF de un capítulo según el formato elegido."""
    plantilla = FORMATOS_NOMBRE.get(formato, FORMATOS_NOMBRE["num"])
    return f"{plantilla.format(n=indice, t=limpiar_nombre(titulo))}.pdf"


def abrir_pdf_bytes(pdf_bytes: bytes, password: Optional[str] = None) -> fitz.Document:
    """Abre un PDF desde bytes, gestionando contraseñas si es necesario."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ErrorSegmentador(f"No se pudo abrir el PDF: {e}")

    if doc.needs_pass:
        if not password:
            doc.close()
            raise ErrorSegmentador("El PDF está protegido con contraseña. Escríbela en Ajustes o junto al archivo.")
        if not doc.authenticate(password):
            doc.close()
            raise ErrorSegmentador("Contraseña incorrecta.")
    return doc


def capitulos_por_toc(doc: fitz.Document) -> List[Capitulo]:
    """Extrae capítulos de la tabla de contenidos (método principal)."""
    toc = doc.get_toc(simple=True)
    if not toc:
        return []

    entradas = [(titulo.strip(), pagina) for nivel, titulo, pagina in toc if nivel == 1]
    capitulos: List[Capitulo] = []
    for i, (titulo, inicio) in enumerate(entradas):
        fin = entradas[i + 1][1] - 1 if i + 1 < len(entradas) else doc.page_count
        if 1 <= inicio <= fin <= doc.page_count:
            capitulos.append(Capitulo(titulo, inicio, fin))
    return capitulos


def capitulos_por_texto(doc: fitz.Document) -> List[Capitulo]:
    """Plan B: detecta títulos buscando patrones en la primera línea de cada página."""
    candidatos: List[Tuple[str, int]] = []
    for idx in range(doc.page_count):
        try:
            texto = doc[idx].get_text("text")
        except Exception:
            continue
        if not texto:
            continue
        primera = texto.strip().split("\n")[0].strip()
        if PATRON_CAPITULO.match(primera):
            candidatos.append((primera[:100], idx + 1))

    capitulos: List[Capitulo] = []
    for i, (titulo, inicio) in enumerate(candidatos):
        fin = candidatos[i + 1][1] - 1 if i + 1 < len(candidatos) else doc.page_count
        if inicio <= fin:
            capitulos.append(Capitulo(titulo, inicio, fin))
    return capitulos


def detectar_capitulos(doc: fitz.Document) -> Tuple[List[Capitulo], str]:
    """Devuelve (capítulos, método_usado). Método = TOC o detección de texto."""
    capitulos = capitulos_por_toc(doc)
    if capitulos:
        return capitulos, METODO_TOC
    capitulos = capitulos_por_texto(doc)
    return capitulos, METODO_TEXTO


def analizar_pdf(pdf_bytes: bytes, password: Optional[str] = None, nombre: str = "libro.pdf") -> InformeLibro:
    """Analiza un PDF y devuelve el informe con los capítulos detectados."""
    doc = abrir_pdf_bytes(pdf_bytes, password)
    try:
        capitulos, metodo = detectar_capitulos(doc)
        return InformeLibro(
            nombre=nombre,
            paginas=doc.page_count,
            protegido=bool(doc.needs_pass),
            metodo=metodo if capitulos else "Sin capítulos",
            capitulos=capitulos,
        )
    finally:
        doc.close()


def extraer_capitulo(doc: fitz.Document, cap: Capitulo) -> bytes:
    """Extrae el rango de páginas de un capítulo como un PDF independiente (bytes)."""
    ini, fin = cap.inicio - 1, cap.fin - 1
    if ini < 0 or fin >= doc.page_count or ini > fin:
        raise ErrorSegmentador(f"Rango inválido para «{cap.titulo}» (pp. {cap.inicio}-{cap.fin}).")
    nuevo = fitz.open()
    try:
        nuevo.insert_pdf(doc, from_page=ini, to_page=fin)
        return nuevo.tobytes(garbage=3, deflate=True)
    finally:
        nuevo.close()


def construir_zip(
    pdf_bytes: bytes,
    capitulos: Sequence[Capitulo],
    password: Optional[str] = None,
    formato_nombre: str = "num",
    progreso: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bytes, List[dict]]:
    """
    Genera un ZIP con un PDF por capítulo.

    Devuelve (zip_bytes, archivos) donde archivos = [{"nombre", "bytes", "paginas"}].
    `progreso` se llama como progreso(hechos, total) tras cada capítulo.
    """
    if not capitulos:
        raise ErrorSegmentador("No hay capítulos seleccionados para generar.")

    doc = abrir_pdf_bytes(pdf_bytes, password)
    archivos: List[dict] = []
    try:
        for i, cap in enumerate(capitulos, start=1):
            datos = extraer_capitulo(doc, cap)
            archivos.append({
                "nombre": nombre_archivo(i, cap.titulo, formato_nombre),
                "bytes": datos,
                "paginas": cap.paginas,
            })
            if progreso:
                progreso(i, len(capitulos))
    finally:
        doc.close()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for archivo in archivos:
            zf.writestr(archivo["nombre"], archivo["bytes"])
    zip_buf.seek(0)
    return zip_buf.read(), archivos


def indice_csv(capitulos: Sequence[Capitulo], archivos: Sequence[dict]) -> str:
    """Índice de los capítulos generados en CSV (título, páginas y nombre del archivo)."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["numero", "titulo", "pagina_inicio", "pagina_fin", "paginas", "archivo"])
    for i, (cap, archivo) in enumerate(zip(capitulos, archivos), start=1):
        escritor.writerow([i, cap.titulo, cap.inicio, cap.fin, cap.paginas, archivo["nombre"]])
    return salida.getvalue()
