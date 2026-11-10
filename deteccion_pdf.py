"""Detección explicable de límites de sección. No modifica el PDF de origen.

Las puntuaciones son prioridades heurísticas, NO probabilidades de acierto.
Las páginas siempre son posiciones físicas (base 1), no números impresos.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
from statistics import median
import unicodedata

import pymupdf as fitz


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())


# Vocabulario inicial ES / EN / PT / FR / DE / IT. No promete todos los idiomas.
SECCIONES = {
    "Portada": r"(?:portada|cubierta|cover|title page|frontispiece|folha de rosto|page de titre)",
    "Copyright": r"(?:copyright|derechos(?: de autor| reservados)?|all rights reserved|ficha catalografica|ficha tecnica|mentions legales)",
    "Presentación": r"(?:presentacion|presentation|apresentacao|vorwort)",
    "Prefacio": r"(?:prefacio|preface|foreword|prologo|avant-propos|premessa)",
    "Reconocimientos": r"(?:reconocimientos?|agradecimientos?|acknowledg(?:e)?ments?|agradecimentos|remerciements|danksagung|ringraziamenti)",
    "Colaboradores": r"(?:colaboradores|contributors|contributing authors|collaborateurs|collaboratori|autores|authors)",
    "Editores": r"(?:editores(?: de (?:la )?edici[oó]n(?: actual| previa| anterior|es previas)?)?|editors(?: of (?:the )?(?:current|previous) editions?)?|previous edition editors|editorial board|comite editorial|equipe editorial|herausgeber|curatori)",
    "Nota": r"(?:nota(?: de(?:l| los)? (?:editor|autor|traductor|editores))?|note(?: to (?:the )?reader)?|publisher.s note|advertencia|aviso|notice)",
    "Dedicatoria": r"(?:dedicatoria|dedication|dedicace|widmung)",
    "Índice": r"(?:indice(?: general| de (?:contenido|materias))?|contenido|contenidos|contents|table of contents|sommaire|sumario|inhaltsverzeichnis)",
    "Introducción": r"(?:introduccion|introduction|introducao|einleitung|introduzione)",
    "Bibliografía": r"(?:bibliografia|bibliography|references|referencias|literatur|bibliographie)",
    "Anexos": r"(?:anexos?|apendices?|appendi(?:x|ces)|annexes?|annexe|anhang|appendice)",
    "Glosario": r"(?:glosario|glossary|glossaire|glossar|glossario)",
}
PATRONES_SECCION = [(categoria, re.compile(r"^" + patron + r"(?:\b|$)", re.I))
                     for categoria, patron in SECCIONES.items()]
NUMERO = r"(?:\d+(?:[.\-]\d+)*|[ivxlcdm]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|one|two|three|four|five|six|seven|eight|nine|ten)"
CAPITULO = re.compile(
    r"^(?:capitulo|chapter|chapitre|kapitel|capitolo|seccion|section|secao|parte|part|partie|teil|unidad|unit|unite|tema|topic)\s+"
    + NUMERO + r"(?:\b|$)", re.I,
)
ENTRADA_INDICE = re.compile(r"^(.+?)(?:\s*\.{2,}\s*|\s{2,}|\t+)([0-9]+|[ivxlcdm]+)\s*$", re.I)


@dataclass
class OpcionesAnalisis:
    estrategia: str = "combinado"  # combinado, marcadores, texto, tipografia, indice, manual
    nivel_toc: int = 1
    incluir_preliminares: bool = True
    ocr: str = "ninguno"  # ninguno, automatico, forzado
    idioma_ocr: str = "spa+eng"
    tessdata: str = ""
    limite_ocr: int = 20
    umbral_titulo: float = 1.35
    desfase_indice: int = 0
    paginas_indice: int = 20

    def validar(self):
        if self.estrategia not in {"combinado", "marcadores", "texto", "tipografia", "indice", "manual"}:
            raise ValueError("Estrategia no reconocida.")
        if self.ocr not in {"ninguno", "automatico", "forzado"}:
            raise ValueError("Modo OCR no reconocido.")
        if not 1 <= self.nivel_toc <= 10 or not 0 <= self.limite_ocr <= 500:
            raise ValueError("Nivel TOC o límite OCR fuera de rango.")
        if not 1.05 <= self.umbral_titulo <= 3 or not 1 <= self.paginas_indice <= 200:
            raise ValueError("Umbral de título o páginas de índice fuera de rango.")
        if not re.fullmatch(r"[a-zA-Z0-9_]+(?:\+[a-zA-Z0-9_]+)*", self.idioma_ocr):
            raise ValueError("Idioma OCR inválido; usa códigos como spa+eng.")


@dataclass
class Candidato:
    titulo: str
    pagina: int
    fuente: str
    categoria: str
    prioridad: int
    detalle: str = ""
    elegido: bool = False


@dataclass
class ResultadoDeteccion:
    limites: list[Candidato] = field(default_factory=list)
    candidatos: list[Candidato] = field(default_factory=list)
    paginas: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    metodo: str = "Detección de texto"
    reparado: bool = False


def categoria_titulo(titulo: str) -> str:
    texto = normalizar(titulo).strip(" .:-–—")
    if CAPITULO.match(texto):
        return "Capítulo / parte"
    for categoria, patron in PATRONES_SECCION:
        if patron.match(texto):
            if categoria == "Índice" and not patron.fullmatch(texto):
                continue
            return categoria
    if texto.startswith(("©", "isbn")):
        return "Copyright"
    return "Sección"


def _lineas_pagina(pagina, textpage=None):
    """Sin imágenes embebidas: evita cargarlas al inspeccionar la tipografía."""
    datos = pagina.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES,
                            textpage=textpage, sort=True)
    lineas = []
    for bloque in datos["blocks"]:
        if bloque["type"] != 0:
            continue
        for linea in bloque["lines"]:
            spans = linea["spans"]
            texto = " ".join(s["text"] for s in spans).strip()
            if texto:
                lineas.append({"texto": texto, "y": linea["bbox"][1],
                               "tamano": max(s["size"] for s in spans)})
    return lineas


def _ocr_pagina(pagina, opciones):
    pixeles_estimados = pagina.rect.width * pagina.rect.height * (200 / 72) ** 2
    if pixeles_estimados > 25_000_000:
        raise ValueError("Página demasiado grande para OCR seguro a 200 dpi; reduce su tamaño antes de procesarla")
    return pagina.get_textpage_ocr(language=opciones.idioma_ocr, dpi=200, full=True,
                                   tessdata=opciones.tessdata or None)


def _resolver_numero(doc, token, desfase):
    # Las etiquetas PDF tienen prioridad: i, ii, 1… no son índices físicos.
    try:
        coincidencias = doc.get_page_numbers(token, only_one=False)
    except Exception:
        coincidencias = []
    if len(coincidencias) == 1:
        return coincidencias[0] + 1
    if len(coincidencias) > 1:
        return None
    if token.isdigit():
        return int(token) + desfase
    return None  # Nunca adivinar el desplazamiento de una numeración romana.


def candidatos_indice(doc, texto: str, desfase=0, estricto=False):
    candidatos, avisos = [], []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        entrada = ENTRADA_INDICE.match(linea)
        if not entrada:
            if estricto and categoria_titulo(linea) != "Índice":
                avisos.append(f"Formato de índice no reconocido: «{linea[:100]}». Usa Título ... página.")
            continue
        titulo, token = entrada.groups()
        pagina = _resolver_numero(doc, token, desfase)
        if pagina is None or not 1 <= pagina <= doc.page_count:
            avisos.append(f"Índice: no se pudo resolver «{linea[:120]}». Ajusta el desfase o usa rangos manuales.")
            continue
        candidatos.append(Candidato(titulo.strip(), pagina, "Índice impreso", categoria_titulo(titulo),
                                     75, f"Número impreso: {token}; desfase configurado: {desfase}"))
    return candidatos, avisos


def detectar(doc, opciones=None, progreso=None) -> ResultadoDeteccion:
    op = opciones or OpcionesAnalisis()
    op.validar()
    r = ResultadoDeteccion(reparado=bool(doc.is_repaired))
    if r.reparado:
        r.avisos.append("MuPDF ha reparado la estructura al abrir el documento. Revisa las páginas antes de extraer.")
    usar_toc = op.estrategia in {"combinado", "marcadores"}
    toc = []
    if usar_toc:
        try:
            toc = doc.get_toc(simple=True)
        except Exception as exc:
            r.avisos.append(f"No se pudieron leer los marcadores: {str(exc)[:160]}. Prueba texto o rangos manuales.")
    if usar_toc:
        for nivel, titulo, pagina in toc:
            if nivel <= op.nivel_toc:
                if 1 <= pagina <= doc.page_count and titulo.strip():
                    r.candidatos.append(Candidato(titulo.strip(), pagina, "Marcadores (TOC)",
                                                   categoria_titulo(titulo), 100 - nivel, f"Nivel {nivel}"))
                else:
                    r.avisos.append(f"Marcador sin destino válido: {titulo[:100]}")
    cuerpos = []
    textos_indice = []
    ocr_intentos = 0
    ocr_fallido = False
    lineas_por_pagina = []
    for idx in range(doc.page_count):
        try:
            pagina = doc[idx]
        except Exception as exc:
            r.paginas.append({"pagina": idx + 1, "etiqueta": "", "caracteres": 0, "ocr": False,
                              "rotacion": 0, "estado": f"No se pudo cargar: {str(exc)[:120]}", "muestra": ""})
            lineas_por_pagina.append(([], 1))
            r.avisos.append(f"No se pudo cargar la página {idx + 1}; revisa el original.")
            if progreso:
                progreso(idx + 1, doc.page_count)
            continue
        error = ""
        ocr_usado = False
        try:
            lineas = _lineas_pagina(pagina)
            texto = "\n".join(l["texto"] for l in lineas)
            sospechoso = len(re.sub(r"\s", "", texto)) < 30 or texto.count("\ufffd") > max(3, len(texto) // 10)
            necesita_ocr = op.ocr == "forzado" or (op.ocr == "automatico" and sospechoso)
            if necesita_ocr and ocr_intentos < op.limite_ocr and not ocr_fallido:
                ocr_intentos += 1
                try:
                    tp = _ocr_pagina(pagina, op)
                    lineas = _lineas_pagina(pagina, tp)
                    texto = "\n".join(l["texto"] for l in lineas)
                    ocr_usado = True
                except Exception as exc:
                    ocr_fallido = True
                    r.avisos.append(f"OCR no disponible o falló en página {idx + 1}: {str(exc)[:200]}. "
                                    "Comprueba Tesseract, tessdata e idiomas. Se conserva el texto nativo.")
            elif necesita_ocr and not ocr_fallido and ocr_intentos >= op.limite_ocr:
                error = "Límite OCR alcanzado"
        except Exception as exc:
            lineas, texto = [], ""
            error = f"Error de lectura: {str(exc)[:160]}"
        lineas_por_pagina.append((lineas, pagina.rect.height))
        cuerpos.extend(l["tamano"] for l in lineas if len(l["texto"]) > 40)
        r.paginas.append({"pagina": idx + 1, "etiqueta": pagina.get_label(),
                          "caracteres": len(texto), "ocr": ocr_usado, "rotacion": pagina.rotation,
                          "estado": error or ("Texto escaso / posible escaneo" if len(texto.strip()) < 30 else "Texto disponible"),
                          "muestra": texto[:300]})
        if op.estrategia == "indice" and idx < op.paginas_indice:
            # Conservar espacios para reconocer columnas y puntos guía del índice.
            try:
                textos_indice.append(pagina.get_text("text", sort=True) if not ocr_usado else texto)
            except Exception:
                textos_indice.append(texto)
        if progreso:
            progreso(idx + 1, doc.page_count)
    if any(p["estado"] == "Límite OCR alcanzado" for p in r.paginas):
        r.avisos.append("Se alcanzó el límite OCR. Aumenta el límite o procesa un PDF reducido; no se hizo OCR en todas las páginas.")
    escasas = sum(p["caracteres"] < 30 for p in r.paginas)
    if escasas:
        r.avisos.append(f"{escasas} páginas con texto escaso: pueden ser imágenes, páginas vacías o fuentes sin mapa Unicode. "
                        "Prueba OCR o define segmentos manuales.")
    tamano_base = median(cuerpos) if cuerpos else 11
    # Un mismo título en muchas páginas suele ser una cabecera, no un inicio.
    apariciones = Counter()
    tamanos_repetidos = defaultdict(list)
    for lineas, altura in lineas_por_pagina:
        apariciones.update({normalizar(l["texto"]) for l in lineas[:12] if l["y"] < altura * .45})
        for linea in lineas[:12]:
            if linea["y"] < altura * .45:
                tamanos_repetidos[normalizar(linea["texto"])].append(linea["tamano"])
    for idx, (lineas, altura) in enumerate(lineas_por_pagina):
        entradas = sum(bool(ENTRADA_INDICE.match(l["texto"])) for l in lineas)
        for pos, linea in enumerate(lineas[:30]):
            titulo = linea["texto"].strip()
            salto_numero = False
            if (re.fullmatch(r"capitulo|chapter|chapitre|kapitel|capitolo|parte|part|section|seccion", normalizar(titulo))
                    and pos + 1 < len(lineas) and lineas[pos + 1]["y"] - linea["y"] < 80
                    and re.match(r"^" + NUMERO + r"(?:\b|$)", normalizar(lineas[pos + 1]["texto"]))):
                titulo += " " + lineas[pos + 1]["texto"]
                salto_numero = True
            norm = normalizar(titulo)
            categoria = categoria_titulo(titulo)
            if not 2 <= len(titulo) <= 180 or ENTRADA_INDICE.match(titulo):
                continue
            repetido = (apariciones[norm] >= 3 and apariciones[norm] > doc.page_count * .25
                        and linea["tamano"] <= median(tamanos_repetidos[norm]) * 1.2)
            reconocido = categoria != "Sección"
            es_copyright = categoria == "Copyright"
            # Índices densos y cabeceras corridas no deben fragmentar el libro.
            if repetido or (entradas >= 2 and categoria != "Índice"):
                continue
            arriba = linea["y"] < altura * .45
            if reconocido and (arriba or es_copyright) and op.estrategia in {"combinado", "texto"}:
                if categoria == "Capítulo / parte" and not salto_numero and pos + 1 < len(lineas):
                    siguiente = lineas[pos + 1]
                    if (siguiente["tamano"] >= linea["tamano"] * .9 and siguiente["y"] - linea["y"] < 60
                            and len(siguiente["texto"]) <= 100 and categoria_titulo(siguiente["texto"]) == "Sección"):
                        titulo = (titulo + " · " + siguiente["texto"])[:180]
                r.candidatos.append(Candidato(titulo, idx + 1, "Texto multilingüe", categoria,
                                               75 if es_copyright and linea["tamano"] < tamano_base * 1.1 else 80,
                                               "Título reconocido; revisar límites"))
            if (arriba and pos < 12 and linea["tamano"] >= tamano_base * op.umbral_titulo
                    and op.estrategia in {"combinado", "tipografia"}
                    and not re.fullmatch(r"[\d\W]+", titulo)):
                r.candidatos.append(Candidato(titulo, idx + 1, "Tipografía", categoria, 55,
                                               f"Fuente {linea['tamano']:.1f} pt; cuerpo estimado {tamano_base:.1f} pt"))
    if op.estrategia == "indice":
        candidatos, avisos = candidatos_indice(doc, "\n".join(textos_indice), op.desfase_indice)
        r.candidatos.extend(candidatos)
        r.avisos.extend(avisos)
        r.avisos.append("Índice impreso: revisa el desfase y los destinos; las columnas o saltos de línea pueden requerir pegar el índice manualmente.")
    # Una sola frontera por página: PDF no permite separar dos secciones que comparten página sin recortar.
    elegidos = {}
    for candidato in sorted(r.candidatos, key=lambda c: -c.prioridad):
        if candidato.pagina not in elegidos:
            candidato.elegido = True
            elegidos[candidato.pagina] = candidato
    r.limites = sorted(elegidos.values(), key=lambda c: c.pagina)
    if op.incluir_preliminares and r.limites and r.limites[0].pagina > 1:
        primero = Candidato("Portada y preliminares (revisar)", 1, "Cobertura inicial", "Preliminares", 40,
                             "Páginas anteriores al primer límite detectado", True)
        r.limites.insert(0, primero)
        r.candidatos.insert(0, primero)
    fuentes = {c.fuente for c in r.limites if c.fuente != "Cobertura inicial"}
    if fuentes == {"Marcadores (TOC)"}:
        r.metodo = "Marcadores (TOC)"
    elif fuentes and fuentes <= {"Texto multilingüe"}:
        r.metodo = "Detección de texto"
    elif fuentes:
        r.metodo = " + ".join(sorted(fuentes))
    if not r.limites:
        r.avisos.append("Sin límites fiables. Puedes añadir filas manuales, importar un índice o dividir por intervalos.")
    return r
