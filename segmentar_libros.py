"""
Segmentador de libros PDF de Medicina por capítulos.
Versión CLI (línea de comandos).

Uso:
    python segmentar_libros.py <ruta_pdf> <carpeta_salida> [--password CONTRASEÑA]
"""

import pymupdf as fitz
import re
import os
import sys
import argparse
from typing import List, Tuple

# Patrón para detectar títulos de capítulo en el texto (plan B)
# Cubre: Capítulo 1, CAPÍTULO IV, Chapter 3, Sección 2.1, Unidad 5, Parte I, etc.
CHAPTER_PATTERN = re.compile(
    r"^\s*(cap[ií]tulo|chapter|secci[oó]n|section|parte|part|unidad|unit|tema|topic)"
    r"\s+([\dIVXLCDM]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)",
    re.IGNORECASE
)


def limpiar_nombre_archivo(titulo: str, max_len: int = 100) -> str:
    """Convierte un título en un nombre de archivo válido y seguro."""
    nombre = re.sub(r'[\\/*?:"<>|]', "", titulo)      # Quita caracteres prohibidos
    nombre = re.sub(r"[\r\n\t]+", " ", nombre)         # Quita saltos de línea
    nombre = re.sub(r"\s+", " ", nombre).strip()       # Colapsa espacios
    nombre = nombre[:max_len].strip()                  # Limita longitud
    return nombre or "Capitulo_Sin_Titulo"


def abrir_pdf(ruta: str, password: str = None) -> fitz.Document:
    """Abre un PDF, gestionando contraseñas si es necesario."""
    try:
        doc = fitz.open(ruta)
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF: {e}")

    if doc.needs_pass:
        if not password:
            doc.close()
            raise RuntimeError(
                "El PDF está protegido con contraseña. "
                "Pásala con --password o usa la versión GUI."
            )
        if not doc.authenticate(password):
            doc.close()
            raise RuntimeError("Contraseña incorrecta.")
    return doc


def obtener_capitulos_por_toc(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    """Extrae capítulos de la tabla de contenidos (método principal)."""
    toc = doc.get_toc(simple=True)
    if not toc:
        return []

    entradas_nivel_1 = [(title.strip(), page) for level, title, page in toc if level == 1]

    capitulos: List[Tuple[str, int, int]] = []
    for i, (titulo, inicio) in enumerate(entradas_nivel_1):
        fin = entradas_nivel_1[i + 1][1] - 1 if i + 1 < len(entradas_nivel_1) else doc.page_count
        if inicio <= fin and 1 <= inicio <= doc.page_count:
            capitulos.append((titulo, inicio, fin))
        else:
            print(f"  ⚠️  Rango inválido para '{titulo}' (páginas {inicio}-{fin}). Omitido.")

    return capitulos


def detectar_capitulos_por_texto(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    """Plan B: detecta títulos buscando patrones en la primera línea de cada página."""
    print("  🔍 No hay marcadores. Iniciando detección por texto...")
    candidatos: List[Tuple[str, int]] = []

    for idx in range(doc.page_count):
        try:
            texto = doc[idx].get_text("text")
        except Exception:
            continue
        if not texto:
            continue
        primera_linea = texto.strip().split("\n")[0].strip() if texto.strip() else ""
        if CHAPTER_PATTERN.match(primera_linea):
            candidatos.append((primera_linea[:100], idx + 1))  # 1-based

    # Asignar página final a cada capítulo
    capitulos: List[Tuple[str, int, int]] = []
    for i, (titulo, inicio) in enumerate(candidatos):
        fin = candidatos[i + 1][1] - 1 if i + 1 < len(candidatos) else doc.page_count
        if inicio <= fin:
            capitulos.append((titulo, inicio, fin))
    return capitulos


def segmentar_pdf(ruta_entrada: str, carpeta_salida: str, password: str = None) -> int:
    """Función principal. Devuelve el número de capítulos generados."""
    if not os.path.isfile(ruta_entrada):
        print(f"❌ No existe el archivo: {ruta_entrada}")
        return 0

    os.makedirs(carpeta_salida, exist_ok=True)
    print(f"📖 Procesando: {os.path.basename(ruta_entrada)}")
    print(f"📁 Salida:    {carpeta_salida}\n")

    try:
        doc = abrir_pdf(ruta_entrada, password)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 0

    try:
        # 1) Método principal: TOC
        capitulos = obtener_capitulos_por_toc(doc)
        metodo = "Marcadores (TOC)"

        # 2) Plan B: detección por texto
        if not capitulos:
            capitulos = detectar_capitulos_por_texto(doc)
            metodo = "Detección de texto"

        if not capitulos:
            print("❌ No se detectaron capítulos con ningún método.")
            print("   Verifica que el PDF tenga texto seleccionable (no escaneado).")
            return 0

        print(f"✅ {len(capitulos)} capítulos detectados usando: {metodo}\n")

        generados = 0
        for i, (titulo, inicio, fin) in enumerate(capitulos, start=1):
            start_idx = inicio - 1
            end_idx = fin - 1

            if start_idx < 0 or end_idx >= doc.page_count or start_idx > end_idx:
                print(f"  ⚠️  Rangos inválidos para '{titulo}'. Omitido.")
                continue

            nombre = f"{i:02d}_{limpiar_nombre_archivo(titulo)}.pdf"
            ruta_salida = os.path.join(carpeta_salida, nombre)

            try:
                nuevo = fitz.open()
                nuevo.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
                nuevo.save(ruta_salida, garbage=3, deflate=True)
                nuevo.close()
                generados += 1
                print(f"  💾 [{i:02d}/{len(capitulos)}] {nombre}  (pp. {inicio}-{fin})")
            except Exception as e:
                print(f"  ❌ Error al guardar '{nombre}': {e}")

        print(f"\n🎉 Proceso completado: {generados} archivos generados.")
        return generados
    finally:
        doc.close()


def main():
    parser = argparse.ArgumentParser(
        description="Segmenta un PDF de Medicina por capítulos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ejemplo:\n  python segmentar_libros.py libro.pdf salida/ --password 1234",
    )
    parser.add_argument("entrada", help="Ruta al PDF de entrada")
    parser.add_argument("salida", help="Carpeta de salida para los capítulos")
    parser.add_argument("--password", default=None, help="Contraseña del PDF (si aplica)")
    args = parser.parse_args()

    total = segmentar_pdf(args.entrada, args.salida, args.password)
    sys.exit(0 if total > 0 else 1)


if __name__ == "__main__":
    main()