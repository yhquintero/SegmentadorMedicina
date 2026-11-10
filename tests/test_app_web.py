"""
Pruebas de humo y de flujo completo de la vista Web (`app_web.py`).

Usan el framework de pruebas de Streamlit (`streamlit.testing.v1.AppTest`)
para recorrer la interfaz sin navegador: navegación por las vistas, análisis
de un PDF con marcadores, generación de capítulos y registro en el Historial.
"""

import os
import io
import zipfile

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


def _comprobar_zip(job, cantidad):
    with zipfile.ZipFile(io.BytesIO(job["generado"]["zip"])) as archivo:
        assert len(archivo.namelist()) == cantidad
        assert all(nombre.endswith(".pdf") for nombre in archivo.namelist())
        for nombre in archivo.namelist():
            with fitz.open(stream=archivo.read(nombre), filetype="pdf") as doc:
                assert doc.page_count == 2


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
    assert not list(at.get("download_button"))  # Analizar no genera descargas.
    assert len(at.data_editor) == 1
    assert at.data_editor[0].value.shape[0] == 3   # tres capítulos

    _boton(at, "Generar").click()
    at.run()
    assert not at.exception
    texto = _texto(at)
    assert "3 capítulos" in texto and "generados" in texto
    descargas = list(at.get("download_button"))
    etiquetas = [d.label or "" for d in descargas]
    assert len(descargas) == 1
    assert all("ZIP" in etiqueta for etiqueta in etiquetas)
    _comprobar_zip(at.session_state["trabajos"][0], 3)
    at.run()  # Las descargas sueltas tampoco reaparecen tras un rerun.
    assert len(list(at.get("download_button"))) == 1

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
    descargas = list(at.get("download_button"))
    assert len(descargas) == 2
    assert all("ZIP" in d.label for d in descargas)
    for job in at.session_state["trabajos"]:
        _comprobar_zip(job, 3)


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


def _widget(elementos, etiqueta):
    return next(x for x in elementos if x.label == etiqueta)


def test_pdf_sin_texto_se_puede_segmentar_manualmente():
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        datos = doc.tobytes()
    at = _app()
    at.file_uploader[0].upload("escaneado.pdf", datos, "application/pdf")
    at.run()
    _boton(at, "Analizar").click().run()
    assert not at.exception
    assert len(at.data_editor) == 1
    assert at.data_editor[0].value.empty
    _boton(at, "Dividir por intervalos").click().run()
    assert not at.exception
    assert len(at.data_editor[0].value) == 2
    _boton(at, "Generar").click().run()
    assert not at.exception
    descargas = list(at.get("download_button"))
    assert len(descargas) == 1 and "ZIP" in descargas[0].label
    with zipfile.ZipFile(io.BytesIO(at.session_state["trabajos"][0]["generado"]["zip"])) as z:
        assert len(z.namelist()) == 2


def test_inspeccion_de_pagina_e_indice_manual():
    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click().run()
    _boton(at, "Inspeccionar página").click().run()
    assert not at.exception
    job = at.session_state["trabajos"][0]
    assert job["inspeccion"]["imagen"].startswith(b"\x89PNG")
    _widget(at.text_area, "Pegar índice: título ... página").set_value("Portada ... 1\nPrefacio ... 3\nCapítulo 1 ... 5").run()
    _boton(at, "Aplicar índice a la tabla").click().run()
    assert not at.exception
    assert at.data_editor[0].value.iloc[0]["titulo"] == "Portada"
    _boton(at, "Generar").click().run()
    assert not at.exception
    _comprobar_zip(at.session_state["trabajos"][0], 3)


def test_informe_dentro_zip_y_cambio_invalida_descarga():
    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click().run()
    _widget(at.checkbox, "Incluir índice CSV e informe de diagnóstico dentro del ZIP").check().run()
    _boton(at, "Generar").click().run()
    assert not at.exception
    job = at.session_state["trabajos"][0]
    with zipfile.ZipFile(io.BytesIO(job["generado"]["zip"])) as z:
        assert "informe_segmentacion.json" in z.namelist()
        assert "indice_segmentos.csv" in z.namelist()
        assert b'"password"' not in z.read("informe_segmentacion.json")
    assert len(list(at.get("download_button"))) == 1
    _widget(at.checkbox, "Incluir índice CSV e informe de diagnóstico dentro del ZIP").uncheck().run()
    assert not at.exception
    assert not list(at.get("download_button"))
    assert "generado" not in at.session_state["trabajos"][0]


def test_metodo_manual_se_puede_elegir_y_reanalizar():
    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _widget(at.selectbox, "Método de segmentación").set_value("manual").run()
    _boton(at, "Analizar").click().run()
    assert not at.exception
    assert at.data_editor[0].value.empty
    _boton(at, "Usar documento completo").click().run()
    assert at.data_editor[0].value.iloc[0]["fin"] == 6
    _widget(at.selectbox, "Método de segmentación").set_value("marcadores").run()
    _boton(at, "Analizar").click().run()
    assert not at.exception
    assert len(at.data_editor[0].value) == 3


def test_cambiar_formato_retira_zip_anterior():
    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click().run()
    _boton(at, "Generar").click().run()
    assert len(list(at.get("download_button"))) == 1
    _boton(at, "Ajustes").click().run()
    _widget(at.selectbox, "Formato del nombre del archivo").set_value("titulo").run()
    _boton(at, "Panel").click().run()
    assert not at.exception
    assert not list(at.get("download_button"))
    _boton(at, "Generar").click().run()
    assert not at.exception
    assert len(list(at.get("download_button"))) == 1
    nombres = [a["nombre"] for a in at.session_state["trabajos"][0]["generado"]["archivos"]]
    assert not nombres[0].startswith("01_")


def test_plan_solapado_no_ofrece_zip(monkeypatch):
    import streamlit as st

    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click().run()
    editor_real = st.data_editor
    def editor_con_solapamiento(data, **kwargs):
        editor_real(data, **kwargs)
        modificado = data.copy()
        modificado.loc[1, "inicio"] = 2  # final del segmento anterior
        return modificado
    monkeypatch.setattr(st, "data_editor", editor_con_solapamiento)
    _boton(at, "Generar").click().run()
    assert not at.exception
    assert any("solapamientos" in x.value for x in at.error)
    assert not list(at.get("download_button"))


def test_correcciones_se_conservan_al_navegar(monkeypatch):
    import streamlit as st

    at = _app()
    at.file_uploader[0].upload("demo.pdf", _pdf_con_toc(), "application/pdf")
    at.run()
    _boton(at, "Analizar").click().run()
    editor_real = st.data_editor
    def editar(data, **kwargs):
        editor_real(data, **kwargs)
        modificado = data.copy()
        modificado.loc[0, "titulo"] = "Portada corregida manualmente"
        return modificado
    monkeypatch.setattr(st, "data_editor", editar)
    at.run()
    monkeypatch.setattr(st, "data_editor", editor_real)
    _boton(at, "Historial").click().run()
    _boton(at, "Panel").click().run()
    assert not at.exception
    assert at.data_editor[0].value.iloc[0]["titulo"] == "Portada corregida manualmente"


def test_password_se_conserva_en_ajustes():
    at = _app()
    _boton(at, "Ajustes").click().run()
    _widget(at.text_input, "Contraseña del PDF (si aplica)").set_value("secreto").run()
    _boton(at, "Panel").click().run()
    assert at.session_state["password"] == "secreto"
    at.run()
    assert at.session_state["password"] == "secreto"
