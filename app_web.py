"""
Versión Web del Segmentador — Streamlit.
Ejecuta con:  streamlit run app_web.py
"""

import streamlit as st
import fitz
import re
import io
import os
import zipfile
from typing import List, Tuple, Optional

CHAPTER_PATTERN = re.compile(
    r"^\s*(cap[ií]tulo|chapter|secci[oó]n|section|parte|part|unidad|unit|tema|topic)"
    r"\s+([\dIVXLCDM]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)",
    re.IGNORECASE
)

st.set_page_config(page_title="Segmentador Médico PDF", page_icon="📚", layout="wide")


def limpiar(t: str) -> str:
    t = re.sub(r'[\\/*?:"<>|]', "", t)
    t = re.sub(r"[\r\n\t]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()[:100]
    return t or "capitulo"


def cap_por_toc(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    toc = doc.get_toc(simple=True)
    if not toc:
        return []
    entradas = [(t.strip(), p) for l, t, p in toc if l == 1]
    cap = []
    for i, (titulo, ini) in enumerate(entradas):
        fin = entradas[i + 1][1] - 1 if i + 1 < len(entradas) else doc.page_count
        if 1 <= ini <= fin <= doc.page_count:
            cap.append((titulo, ini, fin))
    return cap


def cap_por_texto(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    cand = []
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
    cap = []
    for i, (titulo, ini) in enumerate(cand):
        fin = cand[i + 1][1] - 1 if i + 1 < len(cand) else doc.page_count
        if ini <= fin:
            cap.append((titulo, ini, fin))
    return cap


def segmentar(pdf_bytes: bytes, password: Optional[str]) -> Tuple[bytes, str, int]:
    """Devuelve (zip_bytes, método_usado, num_capitulos)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            doc.close()
            raise RuntimeError("PDF protegido o contraseña incorrecta.")

    cap = cap_por_toc(doc)
    metodo = "Marcadores (TOC)"
    if not cap:
        cap = cap_por_texto(doc)
        metodo = "Detección de texto"
    if not cap:
        doc.close()
        raise RuntimeError("No se detectaron capítulos (¿PDF escaneado? Necesita OCR).")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (titulo, ini, fin) in enumerate(cap, start=1):
            nuevo = fitz.open()
            nuevo.insert_pdf(doc, from_page=ini - 1, to_page=fin - 1)
            data = nuevo.tobytes(garbage=3, deflate=True)
            nuevo.close()
            zf.writestr(f"{i:02d}_{limpiar(titulo)}.pdf", data)

    doc.close()
    zip_buf.seek(0)
    return zip_buf.read(), metodo, len(cap)


# ---------------- INTERFAZ ----------------
st.title("📚 Segmentador de Libros Médicos PDF")
st.markdown("Sube un PDF y descarga los capítulos individuales empaquetados en un ZIP.")

with st.sidebar:
    st.header("⚙️ Opciones")
    password = st.text_input("Contraseña del PDF (si aplica)", type="password")
    st.markdown("---")
    st.markdown(
        "**Consejos**\n"
        "- Verifica que el PDF tenga texto seleccionable.\n"
        "- Archivos > 500 MB pueden tardar varios minutos.\n"
        "- El ZIP se genera en el servidor y se envía a tu navegador."
    )

uploaded = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded is not None:
    st.info(f"📄 **{uploaded.name}** — {uploaded.size / (1024*1024):.2f} MB")

    if st.button("🚀 Segmentar ahora", type="primary"):
        with st.spinner("Procesando PDF, por favor espera…"):
            try:
                pdf_bytes = uploaded.read()
                zip_data, metodo, n = segmentar(pdf_bytes, password or None)
                st.success(f"✅ {n} capítulos generados vía **{metodo}**.")
                st.download_button(
                    label="📥 Descargar capítulos (ZIP)",
                    data=zip_data,
                    file_name=f"{os.path.splitext(uploaded.name)[0]}_capitulos.zip",
                    mime="application/zip",
                )
            except RuntimeError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                st.error(f"❌ Error inesperado: {e}")

st.markdown("---")
st.caption("Hecho con PyMuPDF + Streamlit — Segmentación local, sin subir datos a terceros.")