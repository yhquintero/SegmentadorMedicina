"""
Vista Web del Segmentador — Streamlit.

Interfaz inspirada en el sistema NovaGest (github.com/yhquintero/inventario):
rail lateral oscuro, panel con héroe y KPIs, vista previa antes de generar,
modo claro/oscuro/automático y tablas con el mismo lenguaje visual.

Ejecuta con:  streamlit run app_web.py

Cambios aplicados:
- Importación moderna: `import pymupdf as fitz` (elimina el FutureWarning).
- Compatible con archivos grandes (>250 MB) si configuras
  `.streamlit/config.toml` con `server.maxUploadSize`.
"""

<<<<<<< HEAD
import streamlit as st
import pymupdf as fitz  # ⬅️ Importación moderna (sin FutureWarning)
import re
=======
import base64
import datetime
import html
>>>>>>> 50c34f1e001b8563ee77a464db68ba9b771e2898
import io
import os

<<<<<<< HEAD
# Patrón para detectar títulos de capítulo en el texto (plan B)
CHAPTER_PATTERN = re.compile(
    r"^\s*(cap[ií]tulo|chapter|secci[oó]n|section|parte|part|unidad|unit|tema|topic)"
    r"\s+([\dIVXLCDM]+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)",
    re.IGNORECASE
=======
import pandas as pd
import streamlit as st

import segmentador_core as core

_RUTA_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_ICONO = os.path.join(_RUTA_BASE, "assets", "segmentador-icon.png")

st.set_page_config(
    page_title="SegmentadorMedicina · Libros PDF por capítulos",
    page_icon=RUTA_ICONO,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "SegmentadorMedicina · Divide libros PDF de Medicina por capítulos. "
                 "Interfaz inspirada en NovaGest (github.com/yhquintero/inventario).",
    },
>>>>>>> 50c34f1e001b8563ee77a464db68ba9b771e2898
)

__version__ = "2.0"

# ---------------------------------------------------------------------------
# Temas — tokens tomados del sistema de diseño de NovaGest
# ---------------------------------------------------------------------------

TEMAS = {
    "auto": {"label": "Automático", "icono": "◐"},
    "claro": {"label": "Claro", "icono": "☀"},
    "oscuro": {"label": "Oscuro", "icono": "☾"},
}
ORDEN_TEMAS = ["auto", "claro", "oscuro"]

PALETA_CLARO = {
    "--bg": "#f4f6ff", "--surface": "#ffffff", "--surface-2": "#eef0fc",
    "--ink": "#141a3d", "--muted": "#4e5878", "--line": "#e2e5f6",
    "--primary": "#574be0", "--primary-2": "#7c6cff", "--primary-soft": "#e9e8ff",
    "--neon-cyan": "#06b6d4", "--emerald": "#059669", "--emerald-2": "#34d399",
    "--navy": "#171039", "--gold": "#b45309", "--gold-soft": "#fef3c7",
    "--blue": "#0284c7", "--blue-soft": "#e0f2fe",
    "--danger": "#dc2626", "--danger-soft": "#fee2e2",
    "--ok": "#059669", "--ok-soft": "#d1fae5",
    "--shadow": "0 1px 2px rgba(23,23,64,.05), 0 8px 24px rgba(23,23,64,.07)",
    "--radius": "14px",
    "--font": '"Segoe UI", system-ui, -apple-system, sans-serif',
    "--serif": 'Georgia, "Times New Roman", serif',
}
PALETA_OSCURO = {
    "--bg": "#070a1a", "--surface": "#0e1330", "--surface-2": "#161d40",
    "--ink": "#e9ecfb", "--muted": "#a6afd8", "--line": "#232b52",
    "--primary": "#8f86ff", "--primary-2": "#a5a0ff", "--primary-soft": "#221f4e",
    "--neon-cyan": "#22d3ee", "--emerald": "#059669", "--emerald-2": "#34d399",
    "--navy": "#171039", "--gold": "#b45309", "--gold-soft": "#3a2e12",
    "--blue": "#0284c7", "--blue-soft": "#10273f",
    "--danger": "#dc2626", "--danger-soft": "#3b1618",
    "--ok": "#059669", "--ok-soft": "#0c3a2a",
    "--shadow": "0 8px 24px rgba(0,0,0,.45)",
    "--radius": "14px",
    "--font": '"Segoe UI", system-ui, -apple-system, sans-serif',
    "--serif": 'Georgia, "Times New Roman", serif',
}


<<<<<<< HEAD
# ---------------- LÓGICA CORE ----------------
def limpiar(t: str) -> str:
    """Convierte un título en un nombre de archivo válido."""
    t = re.sub(r'[\\/*?:"<>|]', "", t)
    t = re.sub(r"[\r\n\t]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()[:100]
    return t or "capitulo"


def cap_por_toc(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    """Extrae capítulos desde la tabla de contenidos (TOC)."""
    toc = doc.get_toc(simple=True)
    if not toc:
        return []
    entradas = [(t.strip(), p) for l, t, p in toc if l == 1]
    cap: List[Tuple[str, int, int]] = []
    for i, (titulo, ini) in enumerate(entradas):
        fin = entradas[i + 1][1] - 1 if i + 1 < len(entradas) else doc.page_count
        if 1 <= ini <= fin <= doc.page_count:
            cap.append((titulo, ini, fin))
    return cap


def cap_por_texto(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    """Plan B: detecta títulos buscando patrones en la primera línea de cada página."""
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
=======
def _vars_css(paleta: dict) -> str:
    return " ".join(f"{k}: {v};" for k, v in paleta.items())


CSS_ESTRUCTURA = """
* { box-sizing: border-box; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--ink); }
.main .block-container { max-width: 1240px; padding: 1.4rem 2.2rem 5rem; }
h1, h2, h3 { font-family: var(--serif); color: var(--ink); letter-spacing: -.01em; }
a { color: var(--primary); }
header[data-testid="stHeader"] { background: transparent; height: 0.4rem; }
[data-testid="stDecoration"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* ---------- Rail lateral (siempre navy, como NovaGest) ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #171039, #101c40 78%, #0b2b45);
  border-right: 0;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown span,
[data-testid="stSidebar"] .stMarkdown strong,
[data-testid="stSidebar"] .stMarkdown li { color: #d6dbf2; }
.nav-group {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .12em;
  color: #7481c0; font-weight: 700; padding: 16px 10px 6px;
}
.logo { display: flex; gap: 10px; align-items: center; padding: 4px 8px 16px; border-bottom: 1px solid rgba(255,255,255,.08); }
.logo img { width: 42px; height: 42px; border-radius: 11px; box-shadow: 0 4px 14px rgba(79,70,229,.45); }
.logo strong { display: block; color: #fff; font-family: var(--serif); font-size: 17px; line-height: 1.15; }
.logo .hint { color: #9aa6d8; font-size: 11.5px; }
.who {
  display: flex; align-items: center; gap: 10px; margin-top: 18px;
  padding: 12px 6px 0; border-top: 1px solid rgba(255,255,255,.08);
}
.avatar {
  width: 34px; height: 34px; border-radius: 50%; flex: 0 0 auto;
  background: linear-gradient(135deg, #6366f1, #34d399); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 13px;
  box-shadow: 0 3px 10px rgba(79,70,229,.4);
}
.who strong { display: block; color: #fff; font-size: 13px; }
.who .hint { color: #9aa6d8; font-size: 11px; }

/* Botones del rail (navegación) */
[data-testid="stSidebar"] .stButton button {
  width: 100%; justify-content: flex-start; gap: 10px; background: transparent;
  color: #c3cbec; border: 0; padding: 9px 12px; border-radius: 10px;
  font-weight: 500; box-shadow: none; transition: background .15s, color .15s;
}
[data-testid="stSidebar"] .stButton button:hover {
  background: rgba(255,255,255,.07); color: #fff; transform: none;
}
[data-testid="stSidebar"] .stButton button[kind="primary"],
[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
  background: linear-gradient(90deg, rgba(99,102,241,.38), rgba(99,102,241,.10));
  color: #fff; box-shadow: inset 3px 0 0 #34d399;
}

/* ---------- Barra superior ---------- */
.topbar {
  display: flex; align-items: center; gap: 14px; margin-bottom: 16px;
  padding-bottom: 12px; border-bottom: 1px solid var(--line);
}
.topbar h2 { margin: 0; font-family: var(--serif); font-weight: 600; font-size: 23px; }
.topbar .hint { color: var(--muted); font-size: 12px; margin-top: 2px; }
.topbar .right { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }

/* ---------- Héroe ---------- */
.hero {
  position: relative; overflow: hidden; border-radius: 22px;
  padding: 30px 32px; margin-bottom: 16px; color: #fff;
  background:
    linear-gradient(145deg, rgba(17,24,39,.94), rgba(30,27,75,.90) 55%, rgba(5,150,105,.88)),
    url("app/static/hero.jpg") center right / cover no-repeat;
}
.hero h1 {
  color: #fff; font-family: var(--font); font-size: clamp(25px, 2.6vw, 33px);
  font-weight: 750; line-height: 1.14; letter-spacing: -.03em; margin: 8px 0;
}
.hero .eyebrow {
  font-size: 10.5px; font-weight: 750; letter-spacing: .12em;
  text-transform: uppercase; color: #6ee7b7;
}
.hero p { color: #d8defc; max-width: 560px; font-size: 14px; line-height: 1.6; margin: 0 0 14px; }
.hero .chips { display: flex; gap: 6px; flex-wrap: wrap; }

/* ---------- Chips y etiquetas ---------- */
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  display: inline-block; border: 1px solid var(--line); background: var(--surface);
  padding: 5px 12px; border-radius: 999px; font-weight: 600; font-size: 12px;
  color: var(--muted);
}
.hero .chip { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.22); color: #eef2ff; }
.tag {
  display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 8px;
  border-radius: 6px; letter-spacing: .02em;
}
.tag.ok { background: var(--ok-soft); color: var(--ok); }
.tag.warn { background: var(--gold-soft); color: var(--gold); }
.tag.err { background: var(--danger-soft); color: var(--danger); }
.tag.info { background: var(--primary-soft); color: var(--primary); }
.tag.blue { background: var(--blue-soft); color: var(--blue); }

/* ---------- Tarjetas y KPIs ---------- */
.card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow);
  margin-bottom: 16px;
}
.card-h {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; margin-bottom: 12px;
}
.fs {
  font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--primary); font-weight: 700; margin: 18px 0 8px;
  border-bottom: 1px solid var(--line); padding-bottom: 4px;
}
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.kpi {
  position: relative; overflow: hidden; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--radius);
  padding: 16px 18px; box-shadow: var(--shadow);
}
.kpi::before {
  content: ""; position: absolute; inset: 0 auto 0 0; width: 4px;
  background: linear-gradient(180deg, var(--primary), var(--neon-cyan));
}
.kpi.blue::before { background: var(--blue); }
.kpi.gold::before { background: var(--gold); }
.kpi.green::before { background: var(--ok); }
.kpi.green .v { color: var(--ok); }
.kpi.red::before { background: var(--danger); }
.kpi.red .v { color: var(--danger); }
.kpi .k {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .09em;
  color: var(--muted); font-weight: 700;
}
.kpi .v {
  font-family: var(--serif); font-size: 25px; font-weight: 700;
  margin: 6px 0 2px; font-variant-numeric: tabular-nums;
}
.kpi .s { color: var(--muted); font-size: 11.5px; line-height: 1.45; }

/* ---------- Accesos rápidos ---------- */
.quick-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 16px; }
.qcard {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 16px 18px; box-shadow: var(--shadow); position: relative;
}
.qcard .qicon {
  width: 40px; height: 40px; border-radius: 11px; display: grid; place-items: center;
  font-size: 19px; margin-bottom: 10px;
}
.qcard b { display: block; font-size: 14px; margin-bottom: 3px; }
.qcard span { color: var(--muted); font-size: 12px; line-height: 1.45; }
.qcard .arrow {
  position: absolute; top: 14px; right: 16px; color: var(--primary); font-weight: 700;
}

/* ---------- Bandas y avisos ---------- */
.banner {
  background: var(--gold-soft); color: var(--ink);
  border: 1px solid color-mix(in srgb, var(--gold) 35%, transparent);
  padding: 11px 16px; border-radius: 12px; margin-bottom: 14px; font-size: 13.5px;
}
.banner.info {
  background: var(--primary-soft); color: var(--ink);
  border-color: color-mix(in srgb, var(--primary) 35%, transparent);
}
.banner.ok {
  background: var(--ok-soft); color: var(--ink);
  border-color: color-mix(in srgb, var(--ok) 35%, transparent);
}
.banner.err {
  background: var(--danger-soft); color: var(--ink);
  border-color: color-mix(in srgb, var(--danger) 35%, transparent);
}
.summary {
  display: flex; gap: 18px; flex-wrap: wrap; align-items: center;
  padding: 10px 14px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 12px; margin-bottom: 12px; font-size: 13px; color: var(--muted);
}
.summary b { color: var(--ink); font-variant-numeric: tabular-nums; }

/* ---------- Tablas HTML ---------- */
.tabla { width: 100%; border-collapse: collapse; }
.tabla th {
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); font-weight: 700; padding: 10px 12px;
  background: var(--surface-2); border-bottom: 1px solid var(--line); white-space: nowrap;
}
.tabla td { padding: 9px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.tabla tbody tr:hover { background: color-mix(in srgb, var(--primary) 5%, transparent); }
.tabla .r { text-align: right; font-variant-numeric: tabular-nums; }
.dotted td { border-bottom: 1px dashed var(--line); }

/* ---------- Botones e inputs ---------- */
.stButton button, .stDownloadButton button {
  border-radius: 10px; font-weight: 600; padding: 9px 16px;
  border: 1px solid transparent; transition: .15s; white-space: nowrap;
}
.stButton button:hover, .stDownloadButton button:hover { transform: translateY(-1px); filter: brightness(1.06); }
[data-testid="baseButton-primary"], button[kind="primary"] {
  background: var(--primary); color: #fff; border-color: transparent;
}
[data-testid="baseButton-secondary"], button[kind="secondary"] {
  background: var(--surface); color: var(--ink); border-color: var(--line);
}
.stDownloadButton button { width: 100%; justify-content: center; }
.stTextInput input, .stNumberInput input, .stTextArea textarea {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; color: var(--ink);
}
.stTextInput input:focus, .stNumberInput input:focus {
  border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft);
}
[data-baseweb="select"] > div {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; color: var(--ink);
}
[data-baseweb="select"]:focus-within > div {
  border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft);
}
[data-testid="stFileUploadDropzone"], [data-testid="stFileUploaderDropZone"] {
  border: 1.5px dashed var(--line); background: var(--surface-2); border-radius: 14px;
}

/* ---------- Tablas de datos (data_editor / dataframe) ---------- */
[data-testid="stDataFrame"] {
  border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
}

/* ---------- Pestañas ---------- */
[data-baseweb="tab-list"] { gap: 8px; background: transparent; }
button[data-baseweb="tab"] {
  background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
  color: var(--muted); font-weight: 600; padding: 7px 16px;
}
button[data-baseweb="tab"][aria-selected="true"] {
  background: var(--primary); color: #fff; border-color: var(--primary);
}

/* ---------- Progreso ---------- */
[data-testid="stProgress"] > div { background: var(--surface-2); border-radius: 999px; }
[data-testid="stProgress"] > div > div > div { background: linear-gradient(90deg, var(--primary), var(--neon-cyan)); }

/* ---------- Expanders y pie ---------- */
[data-testid="stExpander"] {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
}
.pie {
  margin-top: 26px; padding-top: 12px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 12px; text-align: center;
}
.hint { color: var(--muted); font-size: 12px; }
kbd {
  background: var(--surface-2); border: 1px solid var(--line); border-bottom-width: 2px;
  border-radius: 6px; padding: 1px 6px; font-size: 11px; color: var(--ink);
}

@media (max-width: 1100px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .quick-grid { grid-template-columns: 1fr; }
}
"""


def css_tema(modo: str) -> str:
    """CSS completo según el tema elegido (auto usa prefers-color-scheme)."""
    if modo == "oscuro":
        raiz = f":root {{ {_vars_css(PALETA_OSCURO)} }}"
    elif modo == "auto":
        raiz = (
            f":root {{ {_vars_css(PALETA_CLARO)} }} "
            f"@media (prefers-color-scheme: dark) {{ :root {{ {_vars_css(PALETA_OSCURO)} }} }}"
        )
    else:
        raiz = f":root {{ {_vars_css(PALETA_CLARO)} }}"
    return f"<style>{raiz}\n{CSS_ESTRUCTURA}</style>"


# ---------------------------------------------------------------------------
# Bloques HTML reutilizables (lenguaje visual NovaGest)
# ---------------------------------------------------------------------------

def e(texto) -> str:
    return html.escape(str(texto))
>>>>>>> 50c34f1e001b8563ee77a464db68ba9b771e2898


@st.cache_resource
def logo_b64() -> str:
    """Icono del proyecto reducido a 112 px y embebido en base64."""
    from PIL import Image
    im = Image.open(RUTA_ICONO).convert("RGB").resize((112, 112), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def topbar(titulo: str, meta: str) -> str:
    return f"""
    <div class="topbar">
      <div>
        <h2>{e(titulo)}</h2>
        <div class="hint">{e(meta)}</div>
      </div>
      <div class="right">
        <span class="chip">📄 PDF → 📚 Capítulos</span>
        <span class="chip">🔒 100 % local</span>
      </div>
    </div>"""


def banner(texto: str, tipo: str = "") -> str:
    return f'<div class="banner {tipo}" role="status">{texto}</div>'


def etiqueta(texto: str, tipo: str = "info") -> str:
    return f'<span class="tag {tipo}">{e(texto)}</span>'


def kpi(label: str, valor: str, sub: str, color: str = "") -> str:
    return f"""
    <div class="kpi {color}">
      <div class="k">{e(label)}</div>
      <div class="v">{e(valor)}</div>
      <div class="s">{sub}</div>
    </div>"""


def fila_kpis(items) -> str:
    return '<div class="kpis">' + "".join(kpi(*it) for it in items) + "</div>"


def resumen(pares) -> str:
    trozos = "".join(f"<span>{e(l)} <b>{e(v)}</b></span>" for l, v in pares)
    return f'<div class="summary">{trozos}</div>'


def seccion(texto: str) -> str:
    return f'<div class="fs">{e(texto)}</div>'


def tarjeta_acceso(icono: str, color: str, titulo: str, sub: str) -> str:
    return f"""
    <div class="qcard">
      <div class="qicon" style="background:{color}1c; color:{color}">{icono}</div>
      <div class="arrow">→</div>
      <b>{e(titulo)}</b><span>{e(sub)}</span>
    </div>"""


def mb(n_bytes: float) -> str:
    return f"{n_bytes / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Estado de la sesión
# ---------------------------------------------------------------------------

def init_estado() -> None:
    st.session_state.setdefault("vista", "panel")
    st.session_state.setdefault("tema", "auto")
    st.session_state.setdefault("password", "")
    st.session_state.setdefault("formato", "num")
    st.session_state.setdefault("trabajos", [])
    st.session_state.setdefault("historial", [])


def _ir_a(vista: str) -> None:
    st.session_state["vista"] = vista


def siguiente_tema() -> None:
    actual = st.session_state.get("tema", "auto")
    i = ORDEN_TEMAS.index(actual) if actual in ORDEN_TEMAS else 0
    st.session_state["tema"] = ORDEN_TEMAS[(i + 1) % len(ORDEN_TEMAS)]


def _fingerprint(archivo) -> str:
    return f"{archivo.name}|{archivo.size}"


def _limpiar_todo() -> None:
    """Vacía la sesión (como callback, antes de instanciar los widgets).

    Las claves de widgets son de solo lectura en Streamlit: para vaciar el
    `file_uploader` se cambia su clave y el widget nuevo arranca vacío.
    """
    st.session_state["trabajos"] = []
    for clave in [k for k in st.session_state if str(k).startswith(("ed_", "gen_", "zip_", "csv_", "cap_"))]:
        del st.session_state[clave]
    st.session_state["n_limpieza"] = st.session_state.get("n_limpieza", 0) + 1


# ---------------------------------------------------------------------------
# Rail lateral
# ---------------------------------------------------------------------------

def barra_lateral() -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="logo">
              <img src="data:image/png;base64,{logo_b64()}" alt="SegmentadorMedicina" />
              <div>
                <strong>SegmentadorMedicina</strong>
                <div class="hint">Libros PDF por capítulos</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown('<div class="nav-group">Operación</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.button("🏠 Panel", key="nav_panel",
                      type="primary" if st.session_state["vista"] == "panel" else "secondary",
                      on_click=_ir_a, args=("panel",))
        with c2:
            st.button("📊 Historial", key="nav_hist",
                      type="primary" if st.session_state["vista"] == "historial" else "secondary",
                      on_click=_ir_a, args=("historial",))

        st.markdown('<div class="nav-group">Sistema</div>', unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            st.button("⚙️ Ajustes", key="nav_aju",
                      type="primary" if st.session_state["vista"] == "ajustes" else "secondary",
                      on_click=_ir_a, args=("ajustes",))
        with c4:
            st.button("❓ Ayuda", key="nav_ayu",
                      type="primary" if st.session_state["vista"] == "ayuda" else "secondary",
                      on_click=_ir_a, args=("ayuda",))

        st.markdown(
            f"""
            <div class="who">
              <div class="avatar">SM</div>
              <div>
                <strong>SegmentadorMedicina</strong>
                <div class="hint">v{__version__} · Procesamiento local</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.button(
            f"{TEMAS[st.session_state['tema']]['icono']} Tema: {TEMAS[st.session_state['tema']]['label']}",
            key="btn_tema", on_click=siguiente_tema,
        )


# ---------------------------------------------------------------------------
# Vista: Panel (segmentación)
# ---------------------------------------------------------------------------

def _dibujar_trabajo(job: dict, editados: dict) -> None:
    """Pinta un libro: estado, vista previa editable y resultados generados."""
    estado = job["estado"]
    nombre = job["nombre"]

    st.markdown(resumen([
        ("Archivo", nombre),
        ("Páginas", str(job["paginas"])),
        ("Método", job["metodo"]),
        ("Estado", estado.capitalize()),
    ]), unsafe_allow_html=True)

    if estado == "error":
        st.markdown(banner(f"❌ <b>{e(nombre)}</b> — {e(job['error'])}", "err"), unsafe_allow_html=True)
        return

    caps = job["capitulos"]
    if not caps:
        st.markdown(
            banner(
                f"⚠️ <b>{e(nombre)}</b> — no se detectaron capítulos. "
                "Verifica que el PDF tenga texto seleccionable (¿escaneado? necesita OCR previo).",
            ),
            unsafe_allow_html=True,
        )
        return

    # ---- Vista previa con confirmación (como en NovaGest: nada se genera sin revisar) ----
    st.markdown(seccion("Vista previa · confirma antes de generar"), unsafe_allow_html=True)
    df = pd.DataFrame([
        {"incluir": True, "num": i, "titulo": c.titulo,
         "inicio": c.inicio, "fin": c.fin, "paginas": c.paginas}
        for i, c in enumerate(caps, start=1)
    ])
    editado = st.data_editor(
        df,
        key=f"ed_{job['id']}",
        hide_index=True,
        num_rows="fixed",
        disabled=["num", "inicio", "fin", "paginas"],
        column_config={
            "incluir": st.column_config.CheckboxColumn(
                "✓", help="Desmarca un capítulo para excluirlo de la generación", width="small"),
            "num": st.column_config.NumberColumn("#", width="small"),
            "titulo": st.column_config.TextColumn("Capítulo (editable)", width="large"),
            "inicio": st.column_config.NumberColumn("Desde", width="small"),
            "fin": st.column_config.NumberColumn("Hasta", width="small"),
            "paginas": st.column_config.NumberColumn("Págs.", width="small"),
        },
    )
    editados[job["id"]] = editado

    seleccion = editado[editado["incluir"]]
    st.markdown(resumen([
        ("Seleccionados", f"{len(seleccion)} de {len(caps)}"),
        ("Páginas a extraer", str(int(seleccion["paginas"].sum())) if len(seleccion) else "0"),
        ("Formato de nombre", FORMATOS_LABEL.get(st.session_state["formato"], st.session_state["formato"])),
    ]), unsafe_allow_html=True)

    generados = job.get("generado")
    if not generados:
        if st.button(f"🚀 Generar capítulos de «{nombre[:48]}»", key=f"gen_{job['id']}", type="primary"):
            if seleccion.empty:
                st.markdown(banner("⚠️ No hay capítulos seleccionados. Marca al menos uno en la vista previa."), unsafe_allow_html=True)
            else:
                caps_sel = [
                    core.Capitulo(str(fila["titulo"]), int(fila["inicio"]), int(fila["fin"]))
                    for _, fila in seleccion.iterrows()
                ]
                progreso = st.progress(0, text="Preparando la extracción…")
                try:
                    zip_bytes, archivos = core.construir_zip(
                        job["bytes"], caps_sel,
                        password=st.session_state["password"] or None,
                        formato_nombre=st.session_state["formato"],
                        progreso=lambda hecho, total: progreso.progress(
                            hecho / total, text=f"Extrayendo capítulo {hecho} de {total}…"),
                    )
                    progreso.progress(1.0, text="¡Capítulos generados!")
                    generados = {
                        "zip": zip_bytes,
                        "archivos": archivos,
                        "caps": caps_sel,
                        "csv": core.indice_csv(caps_sel, archivos),
                    }
                    job["generado"] = generados
                    st.session_state["historial"].append({
                        "hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "archivo": nombre,
                        "metodo": job["metodo"],
                        "capitulos": len(caps_sel),
                        "paginas": int(seleccion["paginas"].sum()),
                        "tamano": mb(len(zip_bytes)),
                        "estado": "Generado",
                    })
                except core.ErrorSegmentador as err:
                    st.markdown(banner(f"❌ {e(err)}", "err"), unsafe_allow_html=True)

    # ---- Resultados ----
    if generados:
        archivos = generados["archivos"]
        total_zip = len(generados["zip"])
        st.markdown(banner(
            f"✅ <b>{len(archivos)} capítulos</b> generados vía <b>{e(job['metodo'])}</b> · ZIP {mb(total_zip)}",
            "ok",
        ), unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 Descargar todos los capítulos (ZIP)",
                data=generados["zip"],
                file_name=f"{os.path.splitext(nombre)[0]}_capitulos.zip",
                mime="application/zip",
                type="primary",
                key=f"zip_{job['id']}",
            )
        with c2:
            st.download_button(
                "📄 Descargar índice (CSV)",
                data=generados["csv"],
                file_name=f"{os.path.splitext(nombre)[0]}_indice.csv",
                mime="text/csv",
                key=f"csv_{job['id']}",
            )

        st.markdown(seccion("Descargas individuales"), unsafe_allow_html=True)
        st.markdown(resumen([
            (a["nombre"][:52], f"{a['paginas']} pág. · {mb(len(a['bytes']))}") for a in archivos[:8]
        ]), unsafe_allow_html=True)
        if len(archivos) > 8:
            st.markdown(f'<div class="hint">…y {len(archivos) - 8} archivos más en el ZIP.</div>', unsafe_allow_html=True)

        columnas = st.columns(4)
        for i, archivo in enumerate(archivos):
            with columnas[i % 4]:
                etiqueta_corta = archivo["nombre"].replace(".pdf", "")
                if len(etiqueta_corta) > 26:
                    etiqueta_corta = etiqueta_corta[:25] + "…"
                st.download_button(
                    f"📥 {etiqueta_corta}",
                    data=archivo["bytes"],
                    file_name=archivo["nombre"],
                    mime="application/pdf",
                    key=f"cap_{job['id']}_{i}",
                )


def vista_panel() -> None:
    hoy = datetime.datetime.now().strftime("%d/%m/%Y")
    st.markdown(topbar("Panel", f"{hoy} · Divide libros PDF por capítulos · v{__version__}"), unsafe_allow_html=True)

    st.markdown(f"""
    <div class="hero">
      <div class="eyebrow">{e(hoy)} · SegmentadorMedicina</div>
      <h1>Libros médicos,<br/>un capítulo por archivo.</h1>
      <p>Sube uno o varios PDF, revisa la <b>vista previa de capítulos</b> y descarga cada
      capítulo como un PDF independiente, con su índice en CSV. Todo se procesa en tu equipo.</p>
      <div class="chips">
        <span class="chip">Marcadores (TOC)</span>
        <span class="chip">Detección de texto</span>
        <span class="chip">ZIP + CSV</span>
        <span class="chip">Sin nube</span>
      </div>
    </div>""", unsafe_allow_html=True)

    trabajos = st.session_state["trabajos"]
    st.markdown(
<<<<<<< HEAD
        "**Consejos**\n"
        "- Verifica que el PDF tenga texto seleccionable.\n"
        "- Archivos > 250 MB pueden tardar varios minutos.\n"
        "- El ZIP se genera en el servidor y se envía a tu navegador.\n"
        "- Si falla con archivos enormes, sube `server.maxUploadSize` en `.streamlit/config.toml`."
=======
        banner(
            "💡 <b>Antes de generar nada</b> verás la lista de capítulos detectados: "
            "edita títulos, excluye los que no quieras y confirma. "
            "Tus PDF nunca salen de tu equipo.",
            "info",
        ),
        unsafe_allow_html=True,
>>>>>>> 50c34f1e001b8563ee77a464db68ba9b771e2898
    )

    n_libros = len(trabajos)
    n_caps = sum(len(j["capitulos"]) for j in trabajos)
    n_pags = sum(j["paginas"] for j in trabajos)
    n_gen = sum(1 for j in trabajos if j.get("generado"))
    metodo = next((j["metodo"] for j in trabajos if j["estado"] != "error"), "—")
    st.markdown(fila_kpis([
        ("Libros en sesión", str(n_libros), "subidos en esta sesión", ""),
        ("Páginas analizadas", str(n_pags), "en total", "blue"),
        ("Capítulos detectados", str(n_caps), "listos para revisar", "green"),
        ("Libros generados", f"{n_gen}/{n_libros}" if n_libros else "0", f"método: {e(metodo)}", "gold"),
    ]), unsafe_allow_html=True)

<<<<<<< HEAD
if uploaded is not None:
    st.info(f"📄 **{uploaded.name}** — {uploaded.size / (1024 * 1024):.2f} MB")
=======
    if not trabajos:
        st.markdown('<div class="quick-grid">'
                    + tarjeta_acceso("📤", "#574be0", "1 · Sube el PDF",
                                     "Uno o varios libros a la vez; acepta PDF protegidos con contraseña.")
                    + tarjeta_acceso("🔍", "#0284c7", "2 · Revisa la vista previa",
                                     "Capítulos detectados por marcadores o por texto, editables antes de generar.")
                    + tarjeta_acceso("📥", "#059669", "3 · Descarga los capítulos",
                                     "Un PDF por capítulo, el ZIP completo y el índice en CSV.")
                    + "</div>", unsafe_allow_html=True)
>>>>>>> 50c34f1e001b8563ee77a464db68ba9b771e2898

    # ---- Subida y análisis ----
    with st.container(border=True):
        st.markdown(seccion("Subir libros"), unsafe_allow_html=True)
        subidos = st.file_uploader(
            "Archivos PDF", type=["pdf"], accept_multiple_files=True,
            key=f"subidor_{st.session_state.get('n_limpieza', 0)}",
            help="Puedes seleccionar varios libros a la vez. Se procesan en tu equipo.",
        )
        b1, b2, _ = st.columns([1, 1, 2])
        analizar = b1.button("🔍 Analizar", type="primary", disabled=not subidos)
        b2.button("🧹 Limpiar", disabled=not subidos and not trabajos, on_click=_limpiar_todo)

        if analizar:
            password = st.session_state.get("password") or None
            nuevos = []
            barra = st.progress(0, text="Analizando…")
            for i, archivo in enumerate(subidos, start=1):
                barra.progress(i / len(subidos), text=f"Analizando «{archivo.name}» ({i} de {len(subidos)})…")
                job = {"id": _fingerprint(archivo), "nombre": archivo.name, "bytes": archivo.getvalue()}
                try:
                    informe = core.analizar_pdf(job["bytes"], password=password, nombre=archivo.name)
                    job.update({
                        "paginas": informe.paginas,
                        "protegido": informe.protegido,
                        "metodo": informe.metodo,
                        "capitulos": informe.capitulos,
                        "estado": "analizado",
                    })
                    if not informe.capitulos:
                        st.session_state["historial"].append({
                            "hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "archivo": archivo.name, "metodo": informe.metodo,
                            "capitulos": 0, "paginas": informe.paginas, "tamano": "—",
                            "estado": "Sin capítulos",
                        })
                except core.ErrorSegmentador as err:
                    job.update({"paginas": 0, "protegido": False, "metodo": "—",
                                "capitulos": [], "estado": "error", "error": str(err)})
                    st.session_state["historial"].append({
                        "hora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "archivo": archivo.name, "metodo": "—", "capitulos": 0,
                        "paginas": 0, "tamano": "—", "estado": "Error",
                    })
                nuevos.append(job)
            barra.progress(1.0, text="Análisis completado")
            st.session_state["trabajos"] = nuevos
            st.rerun()

    # ---- Trabajos (pestañas si hay varios libros) ----
    if trabajos:
        editados: dict = {}
        if len(trabajos) == 1:
            _dibujar_trabajo(trabajos[0], editados)
        else:
            pestañas = st.tabs([f"📖 {j['nombre'][:32]}" for j in trabajos])
            for pestana, job in zip(pestañas, trabajos):
                with pestana:
                    _dibujar_trabajo(job, editados)

    st.markdown(
        '<div class="pie">Hecho con PyMuPDF + Streamlit · Segmentación local, sin subir datos a terceros · '
        'Interfaz inspirada en <a href="https://github.com/yhquintero/inventario" target="_blank">NovaGest</a></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Vista: Historial
# ---------------------------------------------------------------------------

def vista_historial() -> None:
    hoy = datetime.datetime.now().strftime("%d/%m/%Y")
    st.markdown(topbar("Historial", f"{hoy} · Trabajos de esta sesión"), unsafe_allow_html=True)

    historial = st.session_state["historial"]
    if not historial:
        st.markdown(banner("ℹ️ Todavía no hay trabajos en el historial. Genera capítulos desde el <b>Panel</b> y aparecerán aquí.", "info"), unsafe_allow_html=True)
        return

    total_caps = sum(h["capitulos"] for h in historial)
    total_pags = sum(h["paginas"] for h in historial)
    errores = sum(1 for h in historial if h["estado"] == "Error")
    st.markdown(fila_kpis([
        ("Trabajos", str(len(historial)), "en esta sesión", ""),
        ("Capítulos generados", str(total_caps), "archivos PDF", "green"),
        ("Páginas procesadas", str(total_pags), "en total", "blue"),
        ("Incidencias", str(errores), "archivos con error", "red" if errores else "green"),
    ]), unsafe_allow_html=True)

    filas = ""
    for h in reversed(historial):
        color = "ok" if h["estado"] == "Generado" else ("err" if h["estado"] == "Error" else "warn")
        filas += (
            f'<tr class="dotted"><td>{e(h["hora"])}</td><td>{e(h["archivo"])}</td>'
            f'<td>{e(h["metodo"])}</td><td class="r">{h["capitulos"]}</td>'
            f'<td class="r">{h["paginas"]}</td><td class="r">{e(h["tamano"])}</td>'
            f'<td>{etiqueta(h["estado"], color)}</td></tr>'
        )
    st.markdown(f"""
    <table class="tabla">
      <thead><tr>
        <th>Fecha</th><th>Archivo</th><th>Método</th>
        <th class="r">Capítulos</th><th class="r">Páginas</th><th class="r">Tamaño ZIP</th><th>Estado</th>
      </tr></thead>
      <tbody>{filas}</tbody>
    </table>""", unsafe_allow_html=True)

    if st.button("🧹 Limpiar historial", key="limpiar_hist"):
        st.session_state["historial"] = []
        st.rerun()


# ---------------------------------------------------------------------------
# Vista: Ajustes
# ---------------------------------------------------------------------------

FORMATOS_LABEL = {
    "num": "01_Título",
    "cap": "Cap01_Título",
    "punto": "01. Título",
    "titulo": "Solo_Título",
}


def vista_ajustes() -> None:
    hoy = datetime.datetime.now().strftime("%d/%m/%Y")
    st.markdown(topbar("Ajustes", f"{hoy} · Apariencia, contraseña y formato de salida"), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(seccion("Apariencia"), unsafe_allow_html=True)
        tema_label = st.radio(
            "Tema de la interfaz",
            ["Automático", "Claro", "Oscuro"],
            index={"auto": 0, "claro": 1, "oscuro": 2}[st.session_state["tema"]],
            horizontal=True,
            help="«Automático» sigue al modo claro/oscuro de tu sistema operativo.",
        )
        st.session_state["tema"] = {"Automático": "auto", "Claro": "claro", "Oscuro": "oscuro"}[tema_label]

    with st.container(border=True):
        st.markdown(seccion("Generación de capítulos"), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.text_input(
                "Contraseña del PDF (si aplica)",
                type="password", key="password",
                help="Se usa al analizar libros protegidos. No se guarda fuera de tu sesión.",
            )
        with c2:
            st.selectbox(
                "Formato del nombre del archivo",
                options=list(FORMATOS_LABEL),
                format_func=lambda k: FORMATOS_LABEL[k],
                key="formato",
                help="Así se nombrará cada capítulo dentro del ZIP.",
            )
        st.markdown(
            '<div class="hint">Los títulos individuales de cada capítulo se editan en la vista previa del '
            '<b>Panel</b> antes de generar.</div>',
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown(seccion("Privacidad"), unsafe_allow_html=True)
        st.markdown(
            banner(
                "🔒 <b>Tus datos mandan.</b> El análisis y la extracción se hacen en tu propio equipo, "
                "dentro de esta sesión. Ningún PDF se envía a servidores ni a servicios de terceros.",
                "info",
            ),
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown(seccion("Acerca de"), unsafe_allow_html=True)
        st.markdown(
            f'<div class="hint"><b>SegmentadorMedicina v{__version__}</b> — Divide libros PDF de Medicina '
            'por capítulos (PyMuPDF + Streamlit).<br/>Interfaz inspirada en el sistema '
            '<a href="https://github.com/yhquintero/inventario" target="_blank">NovaGest · Cuadres, Inventarios</a>.</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Vista: Ayuda
# ---------------------------------------------------------------------------

def vista_ayuda() -> None:
    hoy = datetime.datetime.now().strftime("%d/%m/%Y")
    st.markdown(topbar("Ayuda", f"{hoy} · Cómo funciona y problemas comunes"), unsafe_allow_html=True)

    st.markdown('<div class="quick-grid">'
                + tarjeta_acceso("📤", "#574be0", "1 · Sube el PDF",
                                 "En el Panel, uno o varios libros. Si está protegido, pon la contraseña en Ajustes.")
                + tarjeta_acceso("🔍", "#0284c7", "2 · Analiza y revisa",
                                 "Se detectan los capítulos por marcadores (TOC) o por texto. Edita y confirma.")
                + tarjeta_acceso("📥", "#059669", "3 · Genera y descarga",
                                 "ZIP completo, capítulos sueltos e índice CSV. Todo queda en el Historial.")
                + "</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(seccion("Problemas comunes"), unsafe_allow_html=True)
        with st.expander("❌ «No se detectaron capítulos»"):
            st.markdown("El PDF suele estar **escaneado** (imágenes, sin texto seleccionable). "
                        "Necesita OCR previo (por ejemplo con OCRmyPDF) antes de segmentar.")
        with st.expander("🔒 «El PDF está protegido con contraseña»"):
            st.markdown("Escribe la contraseña en **Ajustes → Contraseña del PDF** y vuelve a pulsar **Analizar**.")
        with st.expander("🐢 «El archivo es muy grande y tarda»"):
            st.markdown("Libros de más de 500 MB pueden tardar varios minutos. La barra de progreso "
                        "muestra el avance; evita cerrar la pestaña mientras se genera el ZIP.")
        with st.expander("🛡 «El antivirus bloquea la descarga»"):
            st.markdown("Es un falso positivo habitual con archivos ZIP generados localmente. "
                        "Añade la descarga a las exclusiones del antivirus.")

    with st.container(border=True):
        st.markdown(seccion("Formatos de nombre"), unsafe_allow_html=True)
        filas = "".join(
            f'<tr class="dotted"><td><b>{e(etiqueta_nombre)}</b></td><td>{e(k)}</td></tr>'
            for k, etiqueta_nombre in FORMATOS_LABEL.items()
        )
        st.markdown(f"""
        <table class="tabla">
          <thead><tr><th>Ejemplo</th><th>Clave</th></tr></thead>
          <tbody>{filas}</tbody>
        </table>
        <div class="hint" style="margin-top:8px">Se eligen en <b>Ajustes → Formato del nombre del archivo</b>.</div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------

def main() -> None:
    init_estado()
    st.markdown(css_tema(st.session_state["tema"]), unsafe_allow_html=True)
    barra_lateral()
    vistas = {
        "panel": vista_panel,
        "historial": vista_historial,
        "ajustes": vista_ajustes,
        "ayuda": vista_ayuda,
    }
    vistas.get(st.session_state["vista"], vista_panel)()


if __name__ == "__main__":
    main()
