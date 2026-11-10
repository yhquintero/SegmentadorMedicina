"""
Pruebas del núcleo de segmentación (`segmentador_core`).

Construyen PDFs pequeños en memoria con PyMuPDF y comprueban la detección
de capítulos por marcadores (TOC), por texto, la protección con contraseña
y la generación del ZIP de salida.
"""

import io
import zipfile

import fitz  # PyMuPDF
import pytest

import segmentador_core as core


def _pdf_con_toc() -> bytes:
    doc = fitz.open()
    for _ in range(6):
        doc.new_page()
    doc.set_toc([
        [1, "Capítulo 1 · Introducción", 1],
        [1, "Capítulo 2 · Anatomía", 3],
        [1, "Capítulo 3 · Fisiología", 5],
    ])
    datos = doc.tobytes()
    doc.close()
    return datos


def _pdf_con_texto() -> bytes:
    doc = fitz.open()
    titulos = {0: "Capítulo 1 Introducción", 2: "Capítulo 2 Anatomía", 4: "Capítulo 3 Fisiología"}
    for i in range(6):
        pagina = doc.new_page()
        titulo = titulos.get(i)
        if titulo:
            pagina.insert_text((72, 72), titulo, fontsize=14)
        pagina.insert_text((72, 120), f"Contenido médico de la página {i + 1}.", fontsize=11)
    datos = doc.tobytes()
    doc.close()
    return datos


def _pdf_protegido(password: str = "secreto") -> bytes:
    doc = fitz.open()
    for _ in range(2):
        doc.new_page()
    doc.set_toc([[1, "Capítulo 1", 1]])
    datos = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw=password,
        user_pw=password,
    )
    doc.close()
    return datos


# ---------------- limpiar_nombre ----------------

def test_limpia_caracteres_prohibidos():
    assert core.limpiar_nombre('Capítulo 1: El "corazón" / hígado?') == "Capítulo 1 El corazón hígado"

def test_limpia_saltos_y_espacios():
    assert core.limpiar_nombre("  A\nB\tC  ") == "A B C"

def test_nombre_vacio_usa_por_defecto():
    assert core.limpiar_nombre("///") == "Capitulo_Sin_Titulo"

def test_limita_longitud():
    assert len(core.limpiar_nombre("x" * 500)) == 100


# ---------------- nombres de archivo ----------------

@pytest.mark.parametrize("formato, esperado", [
    ("num", "01_Introducción.pdf"),
    ("cap", "Cap01_Introducción.pdf"),
    ("punto", "01. Introducción.pdf"),
    ("titulo", "Introducción.pdf"),
])
def test_nombre_archivo(formato, esperado):
    assert core.nombre_archivo(1, "Introducción", formato) == esperado


# ---------------- detección de capítulos ----------------

def test_deteccion_por_toc():
    doc = fitz.open(stream=_pdf_con_toc(), filetype="pdf")
    caps, metodo = core.detectar_capitulos(doc)
    doc.close()
    assert metodo == core.METODO_TOC
    assert [(c.titulo, c.inicio, c.fin) for c in caps] == [
        ("Capítulo 1 · Introducción", 1, 2),
        ("Capítulo 2 · Anatomía", 3, 4),
        ("Capítulo 3 · Fisiología", 5, 6),
    ]

def test_deteccion_por_texto():
    doc = fitz.open(stream=_pdf_con_texto(), filetype="pdf")
    caps, metodo = core.detectar_capitulos(doc)
    doc.close()
    assert metodo == core.METODO_TEXTO
    assert [(c.inicio, c.fin) for c in caps] == [(1, 2), (3, 4), (5, 6)]
    assert caps[1].titulo.startswith("Capítulo 2")

def test_sin_capitulos():
    doc = fitz.open()
    doc.new_page()
    caps, metodo = core.detectar_capitulos(doc)
    doc.close()
    assert caps == []
    assert metodo == core.METODO_TEXTO

def test_analizar_pdf_devuelve_informe():
    informe = core.analizar_pdf(_pdf_con_toc(), nombre="libro.pdf")
    assert informe.nombre == "libro.pdf"
    assert informe.paginas == 6
    assert informe.paginas_en_capitulos == 6
    assert informe.metodo == core.METODO_TOC
    assert len(informe.capitulos) == 3


# ---------------- contraseñas ----------------

def test_pdf_protegido_sin_password_da_error():
    with pytest.raises(core.ErrorSegmentador):
        core.analizar_pdf(_pdf_protegido())

def test_pdf_protegido_password_incorrecta():
    with pytest.raises(core.ErrorSegmentador, match="incorrecta"):
        core.analizar_pdf(_pdf_protegido(), password="mala")

def test_pdf_protegido_password_correcta():
    informe = core.analizar_pdf(_pdf_protegido(), password="secreto")
    assert informe.protegido
    assert len(informe.capitulos) == 1


# ---------------- extracción y ZIP ----------------

def test_extraer_capitulo():
    doc = fitz.open(stream=_pdf_con_toc(), filetype="pdf")
    datos = core.extraer_capitulo(doc, core.Capitulo("Prueba", 3, 4))
    doc.close()
    nuevo = fitz.open(stream=datos, filetype="pdf")
    assert nuevo.page_count == 2
    nuevo.close()

def test_construir_zip():
    zip_bytes, archivos = core.construir_zip(_pdf_con_toc(), [
        core.Capitulo("Introducción", 1, 2),
        core.Capitulo("Anatomía", 3, 4),
    ])
    assert [a["nombre"] for a in archivos] == ["01_Introducción.pdf", "02_Anatomía.pdf"]
    assert all(a["bytes"].startswith(b"%PDF") for a in archivos)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert sorted(zf.namelist()) == ["01_Introducción.pdf", "02_Anatomía.pdf"]

def test_zip_vacio_da_error():
    with pytest.raises(core.ErrorSegmentador):
        core.construir_zip(_pdf_con_toc(), [])

def test_progreso_se_invoca():
    llamadas = []
    core.construir_zip(_pdf_con_toc(), [
        core.Capitulo("A", 1, 2),
        core.Capitulo("B", 3, 4),
        core.Capitulo("C", 5, 6),
    ], progreso=lambda hecho, total: llamadas.append((hecho, total)))
    assert llamadas == [(1, 3), (2, 3), (3, 3)]


# ---------------- índice CSV ----------------

def test_indice_csv():
    caps = [core.Capitulo("Introducción", 1, 2), core.Capitulo("Anatomía", 3, 4)]
    _, archivos = core.construir_zip(_pdf_con_toc(), caps)
    csv_texto = core.indice_csv(caps, archivos)
    lineas = csv_texto.strip().splitlines()
    assert lineas[0] == "numero,titulo,pagina_inicio,pagina_fin,paginas,archivo"
    assert len(lineas) == 3
    assert "Introducción" in lineas[1]
