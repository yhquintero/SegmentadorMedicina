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
import math
import hashlib
import json
from dataclasses import asdict

from deteccion_pdf import OpcionesAnalisis, detectar, candidatos_indice, normalizar
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

import pymupdf as fitz

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
    fuente: str = "Manual"
    categoria: str = "Sección"

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

    diagnostico: list[dict] = field(default_factory=list)
    candidatos: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    reparado: bool = False

    @property
    def paginas_en_capitulos(self) -> int:
        return sum(c.paginas for c in self.capitulos)


def limpiar_nombre(titulo: str, max_len: int = 100, por_defecto: str = "Capitulo_Sin_Titulo") -> str:
    """Convierte un título en un nombre de archivo válido y seguro."""
    nombre = re.sub(r'[\\/*?:"<>|]', "", titulo)
    nombre = re.sub(r"[\r\n\t]+", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    nombre = nombre[:max_len].strip().rstrip(" .")
    if re.match(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", nombre, re.I):
        nombre = "_" + nombre
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

    if doc.page_count == 0:
        doc.close()
        raise ErrorSegmentador("El PDF no contiene páginas.")
    if doc.needs_pass:
        if not password:
            doc.close()
            raise ErrorSegmentador("El PDF está protegido con contraseña. Escríbela en Ajustes o junto al archivo.")
        try:
            autenticado = doc.authenticate(password)
        except Exception as exc:
            doc.close()
            raise ErrorSegmentador(f"No se pudo autenticar el PDF: {exc}") from exc
        if not autenticado:
            doc.close()
            raise ErrorSegmentador("Contraseña incorrecta.")
    return doc


def _convertir_limites(limites, total):
    return [Capitulo(c.titulo, c.pagina,
                     limites[i + 1].pagina - 1 if i + 1 < len(limites) else total,
                     c.fuente, c.categoria)
            for i, c in enumerate(limites)]


def capitulos_por_toc(doc: fitz.Document, nivel: int = 1) -> List[Capitulo]:
    resultado = detectar(doc, OpcionesAnalisis(estrategia="marcadores", nivel_toc=nivel))
    return _convertir_limites(resultado.limites, doc.page_count)


def capitulos_por_texto(doc: fitz.Document) -> List[Capitulo]:
    resultado = detectar(doc, OpcionesAnalisis(estrategia="texto"))
    return _convertir_limites(resultado.limites, doc.page_count)


def detectar_capitulos(doc: fitz.Document, opciones=None) -> Tuple[List[Capitulo], str]:
    resultado = detectar(doc, opciones)
    return _convertir_limites(resultado.limites, doc.page_count), resultado.metodo


def analizar_pdf(pdf_bytes: bytes, password: Optional[str] = None, nombre: str = "libro.pdf",
                 opciones: Optional[OpcionesAnalisis] = None, progreso=None) -> InformeLibro:
    doc = abrir_pdf_bytes(pdf_bytes, password)
    try:
        try:
            resultado = detectar(doc, opciones, progreso)
        except Exception as exc:
            raise ErrorSegmentador(f"No se pudo analizar el documento: {exc}") from exc
        caps = _convertir_limites(resultado.limites, doc.page_count)
        return InformeLibro(nombre, doc.page_count, bool(doc.needs_pass),
                            resultado.metodo if caps else "Sin capítulos", caps,
                            resultado.paginas, [asdict(c) for c in resultado.candidatos],
                            resultado.avisos, resultado.reparado)
    finally:
        doc.close()


def validar_segmentos(capitulos: Sequence[Capitulo], total: int) -> list[str]:
    """Falla antes de crear archivos: rangos enteros, sin solapamientos ni títulos vacíos."""
    if not capitulos:
        raise ErrorSegmentador("No hay segmentos seleccionados para generar.")
    anterior = 0
    huecos = []
    for cap in capitulos:
        try:
            valido = (isinstance(cap.inicio, (int, float)) and isinstance(cap.fin, (int, float))
                      and math.isfinite(cap.inicio) and math.isfinite(cap.fin)
                      and int(cap.inicio) == cap.inicio and int(cap.fin) == cap.fin
                      and 1 <= cap.inicio <= cap.fin <= total)
        except (TypeError, ValueError, OverflowError):
            valido = False
        if not valido:
            raise ErrorSegmentador(f"Rango inválido para «{cap.titulo}»: usa páginas físicas enteras entre 1 y {total}.")
        if not str(cap.titulo).strip():
            raise ErrorSegmentador("Todos los segmentos deben tener un título.")
        if cap.inicio <= anterior:
            raise ErrorSegmentador("Los segmentos deben estar ordenados y sin solapamientos. Revisa Desde / Hasta.")
        if cap.inicio > anterior + 1:
            huecos.append(f"{anterior + 1}–{int(cap.inicio) - 1}")
        anterior = int(cap.fin)
    if anterior < total:
        huecos.append(f"{anterior + 1}–{total}")
    return ["Páginas no incluidas: " + ", ".join(huecos)] if huecos else []


def segmentos_por_intervalo(total: int, intervalo: int) -> list[Capitulo]:
    if total < 1 or intervalo < 1:
        raise ErrorSegmentador("El intervalo y el número de páginas deben ser positivos.")
    return [Capitulo(f"Páginas {inicio}–{min(inicio + intervalo - 1, total)}", inicio,
                     min(inicio + intervalo - 1, total)) for inicio in range(1, total + 1, intervalo)]


def segmentos_desde_indice(pdf_bytes, texto, password=None, desfase=0):
    doc = abrir_pdf_bytes(pdf_bytes, password)
    try:
        candidatos, avisos = candidatos_indice(doc, texto, desfase, estricto=True)
        unicos = {}
        for candidato in candidatos:
            unicos.setdefault(candidato.pagina, candidato)
        return _convertir_limites(sorted(unicos.values(), key=lambda c: c.pagina), doc.page_count), avisos
    finally:
        doc.close()


def inspeccionar_pagina(pdf_bytes, numero, password=None, ocr=False, idioma="spa+eng", tessdata=""):
    """Vista acotada: una página rasterizada, texto y etiqueta. Nunca ofrece el PDF suelto."""
    doc = abrir_pdf_bytes(pdf_bytes, password)
    try:
        if not 1 <= numero <= doc.page_count:
            raise ErrorSegmentador("Página fuera del documento.")
        pagina = doc[numero - 1]
        tp = None
        if ocr:
            from deteccion_pdf import _ocr_pagina
            tp = _ocr_pagina(pagina, OpcionesAnalisis(idioma_ocr=idioma, tessdata=tessdata))
        escala = min(1.5, 1200 / max(pagina.rect.width, pagina.rect.height))
        imagen = pagina.get_pixmap(matrix=fitz.Matrix(escala, escala), alpha=False).tobytes("png")
        return {"imagen": imagen, "texto": pagina.get_text("text", textpage=tp, sort=True),
                "etiqueta": pagina.get_label(), "rotacion": pagina.rotation}
    except ErrorSegmentador:
        raise
    except Exception as exc:
        raise ErrorSegmentador(f"No se pudo inspeccionar la página: {exc}") from exc
    finally:
        doc.close()


def buscar_texto(pdf_bytes, consulta, password=None, limite=100):
    """Búsqueda literal normalizada, sin regex. No aplica OCR ni modifica páginas."""
    consulta = normalizar(consulta)
    if len(consulta) < 2:
        raise ErrorSegmentador("Escribe al menos dos caracteres para buscar.")
    resultados, errores = [], []
    doc = abrir_pdf_bytes(pdf_bytes, password)
    try:
        for idx in range(doc.page_count):
            try:
                texto = doc[idx].get_text("text", sort=True)
                lineas = [l for l in texto.splitlines() if consulta in normalizar(l)]
                if lineas:
                    resultados.append({"pagina": idx + 1, "etiqueta": doc[idx].get_label(),
                                       "coincidencias": len(lineas), "muestra": " | ".join(lineas)[:400]})
                if len(resultados) >= limite:
                    break
            except Exception:
                errores.append(idx + 1)
        return resultados, errores
    finally:
        doc.close()


def huella_pdf(datos):
    return hashlib.sha256(datos).hexdigest()


def extraer_capitulo(doc: fitz.Document, cap: Capitulo) -> bytes:
    """Extrae el rango de páginas de un capítulo como un PDF independiente (bytes)."""
    validar_segmentos([cap], doc.page_count)
    ini, fin = cap.inicio - 1, cap.fin - 1
    if ini < 0 or fin >= doc.page_count or ini > fin:
        raise ErrorSegmentador(f"Rango inválido para «{cap.titulo}» (pp. {cap.inicio}-{cap.fin}).")
    nuevo = fitz.open()
    try:
        nuevo.insert_pdf(doc, from_page=int(ini), to_page=int(fin))
        return nuevo.tobytes(garbage=3, deflate=True)
    except Exception as exc:
        raise ErrorSegmentador(f"No se pudo extraer «{cap.titulo}» (páginas {cap.inicio}–{cap.fin}): {exc}") from exc
    finally:
        nuevo.close()


def construir_zip(
    pdf_bytes: bytes,
    capitulos: Sequence[Capitulo],
    password: Optional[str] = None,
    formato_nombre: str = "num",
    progreso: Optional[Callable[[int, int], None]] = None,
    informe: Optional[dict] = None,
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
        validar_segmentos(capitulos, doc.page_count)
        usados = set()
        for i, cap in enumerate(capitulos, start=1):
            datos = extraer_capitulo(doc, cap)
            nombre = nombre_archivo(i, cap.titulo, formato_nombre)
            base = nombre[:-4]
            sufijo = 2
            while nombre.casefold() in usados:
                nombre = f"{base}_{sufijo}.pdf"
                sufijo += 1
            usados.add(nombre.casefold())
            archivos.append({
                "nombre": nombre,
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
        if informe is not None:
            zf.writestr("informe_segmentacion.json", json.dumps(informe, ensure_ascii=False, indent=2))
            zf.writestr("indice_segmentos.csv", indice_csv(capitulos, archivos))
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
