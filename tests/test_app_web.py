"""
Pruebas de humo y de flujo completo de la vista Web (`app_web.py`).

Usan el framework de pruebas de Streamlit (`streamlit.testing.v1.AppTest`)
para recorrer la interfaz sin navegador: navegación por las vistas, análisis
de un PDF con marcadores, generación de capítulos y registro en el Historial.
"""

import os

import fitz  # PyMuPDF
import pytest
from streamlit.testing.v1 import AppTest

RUTA_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_web.py")


def _pdf_con_toc() -> bytes:
    doc = fitz.open()
    for i in range(6):
        pagina = doc.new_page()
        pagina.insert_text((72, 72), f"Contenido médico página {i + 1}", fontsize=12)
    doc.set_toc([
        [1, "Capítulo 1 · Introducción", 1],
        [1, "Capítulo 2 · Anatomía", 3],
        [1, "Capítulo 3 · Fisiología", 5],
    ])
    datos = doc.tobytes()
    doc.close()
    return datos


def _pdf_protegido() -> bytes:
    doc = fitz.open()
    doc.new_page()
    datos = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="secreto", user_pw="secreto")
    doc.close()
    return datos


def _app() -> AppTest:
    at = AppTest.from_file(RUTA_APP, default_timeout=60)
    at.run()
    return at


def _boton(at: AppTest, fragmento: str):
    encontrados = [b for b in at.button if fragmento in (b.label or "")]
    assert encontrados, f"Botón {fragmento!r} no encontrado: {[b.label for b in at.button]}"
    return encontrados[0]


def _texto(at: AppTest) -> str:
    return " ".join(str(m.value) for m in at.markdown)


# ---------------- arranque y navegación ----------------

def test_panel_se_renderiza_sin_excepciones():
    at = _app()
    assert not at.exception
    texto = _texto(at)
    assert "Libros médicos" in texto
    assert "Subir libros" in texto
    assert "Marcadores (TOC)" in texto


def test_navegacion_entre_las_cuatro_vistas():
    at = _app()
    for fragmento, esperado in [
        ("Historial", "Todavía no hay trabajos"),
        ("Ajustes", "Generación de capítulos"),
        ("Ayuda", "Problemas comunes"),
        ("Panel", "Subir libros"),
    ]:
        _boton(at, fragmento).click()
        at.run()
        assert not at.exception
        assert esperado in _texto(at)


def test_tema_se_puede_cambiar():
    at = _app()
    assert "--bg: #f4f6ff" in _texto(at) or "--bg:#f4f6ff" in _texto(at).replace(" ", "")
    _boton(at, "Tema:").click()   # auto → claro
    at.run()
    _boton(at, "Tema:").click()   # claro → oscuro
    at.run()
    assert not at.exception
    assert "#070a1a" in _texto(at)


# ---------------- flujo completo: analizar → generar → historial ----------------

def test_flujo_completo_con_un_libro():
    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()

    _boton(at, "Analizar").click()
    at.run()
    assert not at.exception
    texto = _texto(at)
    assert "Vista previa" in texto
    assert "Marcadores (TOC)" in texto
    assert len(at.data_editor) == 1
    assert at.data_editor[0].value.shape[0] == 3   # tres capítulos

    _boton(at, "Generar").click()
    at.run()
    assert not at.exception
    texto = _texto(at)
    assert "3 capítulos" in texto and "generados" in texto
    descargas = list(at.get("download_button"))
    etiquetas = [d.label or "" for d in descargas]
    assert any("ZIP" in e for e in etiquetas)
    assert any("CSV" in e for e in etiquetas)
    assert sum(1 for e in etiquetas if e.startswith("📥 0")) == 3

    _boton(at, "Historial").click()
    at.run()
    texto = _texto(at)
    assert "demo.pdf" in texto
    assert "Generado" in texto


def test_flujo_con_dos_libros():
    at = _app()
    at.file_uploader[0].set_value([
        ("uno.pdf", _pdf_con_toc(), "application/pdf"),
        ("dos.pdf", _pdf_con_toc(), "application/pdf"),
    ])
    at.run()

    _boton(at, "Analizar").click()
    at.run()
    assert not at.exception
    assert "uno.pdf" in _texto(at) and "dos.pdf" in _texto(at)

    for nombre in ("uno.pdf", "dos.pdf"):
        _boton(at, f"Generar capítulos de «{nombre}»").click()
        at.run()
        assert not at.exception

    texto = _texto(at)
    assert texto.count("capítulos</b> generados") == 2 or texto.count("generados vía") == 2


def test_pdf_protegido_muestra_error():
    at = _app()
    at.file_uploader[0].upload("cifrado.pdf", _pdf_protegido(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click()
    at.run()
    assert not at.exception
    assert "protegido" in _texto(at).lower() or "contraseña" in _texto(at).lower()


def test_limpiar_vacia_la_sesion():
    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click()
    at.run()
    _boton(at, "Limpiar").click()
    at.run()
    assert not at.exception
    assert "Vista previa" not in _texto(at)
