"""Corpus sintético reproducible. No usa PDFs privados ni servicios de OCR externos."""
import io
import json
import zipfile

import pandas as pd
import pymupdf as fitz
import pytest

import deteccion_pdf as detector
import segmentador_core as core
from web_pdf import filas_a_segmentos


def pdf_paginas(titulos, toc=None):
    with fitz.open() as doc:
        for titulo in titulos:
            p = doc.new_page()
            p.insert_text((72, 30), "Tratado de medicina", fontsize=9)  # cabecera, no título
            if titulo:
                for n, linea in enumerate(titulo.split("\n")):
                    p.insert_text((72, 95 + n * 28), linea, fontsize=20)
            p.insert_text((72, 250), "Texto de desarrollo suficientemente largo para estimar la fuente del cuerpo.", fontsize=10)
        if toc:
            doc.set_toc(toc)
        return doc.tobytes()


def test_preliminares_con_toc_parcial():
    datos = pdf_paginas(["Portada", "Copyright", "Prefacio", "Capítulo 1", None, "Capítulo 2"],
                        [[1, "Capítulo 1", 4], [1, "Capítulo 2", 6]])
    informe = core.analizar_pdf(datos)
    assert [c.inicio for c in informe.capitulos] == [1, 2, 3, 4, 6]
    assert informe.capitulos[1].categoria == "Copyright"
    assert informe.capitulos[3].fuente == "Marcadores (TOC)"
    assert len(informe.diagnostico) == 6
    assert any(c["elegido"] for c in informe.candidatos)


@pytest.mark.parametrize("titulo,categoria", [
    ("Presentación", "Presentación"), ("Copyright © 2026", "Copyright"),
    ("Prefácio", "Prefacio"), ("Reconocimientos", "Reconocimientos"),
    ("Acknowledgements", "Reconocimientos"), ("Acknowledgments", "Reconocimientos"),
    ("Agradecimentos", "Reconocimientos"), ("Remerciements", "Reconocimientos"),
    ("Danksagung", "Reconocimientos"), ("Ringraziamenti", "Reconocimientos"),
    ("Colaboradores", "Colaboradores"), ("Contributors", "Colaboradores"),
    ("Editores de la edición actual y ediciones previas", "Editores"),
    ("Editors of previous editions", "Editores"), ("Herausgeber", "Editores"),
    ("Nota del editor", "Nota"), ("Dedicatoria", "Dedicatoria"),
    ("Capítulo IV", "Capítulo / parte"), ("Chapter 2", "Capítulo / parte"),
    ("Chapitre 2", "Capítulo / parte"), ("Kapitel 2", "Capítulo / parte"),
    ("Capitolo 2", "Capítulo / parte"), ("Seção 3", "Capítulo / parte"),
    ("Anexos", "Anexos"), ("Appendix A", "Anexos"), ("Bibliografía", "Bibliografía"),
])
def test_vocabulario_multilingue(titulo, categoria):
    assert detector.categoria_titulo(titulo) == categoria
    # Helvetica de los PDFs sintéticos no representa todos los alfabetos; vocabulario latino.
    informe = core.analizar_pdf(pdf_paginas([titulo]), opciones=detector.OpcionesAnalisis(estrategia="texto"))
    assert len(informe.capitulos) == 1
    assert informe.capitulos[0].categoria == categoria


def test_titulo_debajo_de_cabecera_y_multilinea():
    informe = core.analizar_pdf(pdf_paginas(["CHAPTER\n1", None, "Capítulo 2\nAnatomía"]),
                               opciones=detector.OpcionesAnalisis(estrategia="texto"))
    assert [c.inicio for c in informe.capitulos] == [1, 3]
    assert informe.capitulos[0].titulo == "CHAPTER 1"
    assert "Anatomía" in informe.capitulos[1].titulo


def test_tipografia_detecta_titulo_no_catalogado():
    informe = core.analizar_pdf(pdf_paginas(["Bases moleculares", None, "Sistema nervioso"]),
                               opciones=detector.OpcionesAnalisis(estrategia="tipografia"))
    assert [c.inicio for c in informe.capitulos] == [1, 3]
    assert all(c.fuente == "Tipografía" for c in informe.capitulos)


def test_cabecera_repetida_no_crea_segmentos():
    informe = core.analizar_pdf(pdf_paginas(["Chapter 1"] * 6),
                               opciones=detector.OpcionesAnalisis(estrategia="texto"))
    assert informe.capitulos == []


def test_toc_nivel_y_orden_sin_solapamientos():
    datos = pdf_paginas([None] * 6, [[1, "Parte I", 1], [2, "Capítulo 1", 2],
                                   [2, "Capítulo 2", 4], [1, "Parte II", 6]])
    op = detector.OpcionesAnalisis(estrategia="marcadores", nivel_toc=2)
    informe = core.analizar_pdf(datos, opciones=op)
    assert [(c.inicio, c.fin) for c in informe.capitulos] == [(1, 1), (2, 3), (4, 5), (6, 6)]
    core.validar_segmentos(informe.capitulos, 6)


def test_cobertura_inicial_se_puede_desactivar():
    datos = pdf_paginas([None] * 4, [[1, "Capítulo 1", 3]])
    op = detector.OpcionesAnalisis(estrategia="marcadores")
    assert core.analizar_pdf(datos, opciones=op).capitulos[0].inicio == 1
    op.incluir_preliminares = False
    assert core.analizar_pdf(datos, opciones=op).capitulos[0].inicio == 3


def test_misma_pagina_un_solo_limite():
    datos = pdf_paginas(["Copyright\nPrefacio", "Chapter 1"])
    informe = core.analizar_pdf(datos)
    assert [c.inicio for c in informe.capitulos] == [1, 2]
    assert len([c for c in informe.candidatos if c["pagina"] == 1]) > 1
    assert sum(c["elegido"] for c in informe.candidatos if c["pagina"] == 1) == 1


def test_indice_no_confunde_listado_con_capitulos():
    datos = pdf_paginas(["Contents\nChapter 1 .... 3\nChapter 2 .... 5", None, "Chapter 1", None, "Chapter 2"])
    informe = core.analizar_pdf(datos, opciones=detector.OpcionesAnalisis(estrategia="texto"))
    assert [c.inicio for c in informe.capitulos] == [1, 3, 5]
    assert informe.capitulos[0].categoria == "Índice"


def test_indice_pegado_con_desfase_y_validacion():
    datos = pdf_paginas([None] * 7)
    caps, avisos = core.segmentos_desde_indice(datos, "Prefacio ... 1\nChapter 1 ... 3", desfase=2)
    assert not avisos
    assert [(c.inicio, c.fin) for c in caps] == [(3, 4), (5, 7)]
    _, avisos = core.segmentos_desde_indice(datos, "Título ... 999\nLínea mal formada")
    assert len(avisos) == 2


def test_indice_romano_etiquetas_no_adivina():
    with fitz.open(stream=pdf_paginas([None] * 5), filetype="pdf") as doc:
        doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1}])
        datos = doc.tobytes()
    caps, avisos = core.segmentos_desde_indice(datos, "Prefacio ... ii\nChapter 1 ... iv")
    assert [c.inicio for c in caps] == [2, 4]
    assert not avisos
    _, avisos = core.segmentos_desde_indice(pdf_paginas([None] * 5), "Prefacio ... ii")
    assert avisos


def test_indice_automatico_impreso():
    datos = pdf_paginas(["Contents\nPrefacio .... 2\nChapter 1 .... 4", "Prefacio", None, "Chapter 1"])
    op = detector.OpcionesAnalisis(estrategia="indice", paginas_indice=1)
    informe = core.analizar_pdf(datos, opciones=op)
    assert [c.inicio for c in informe.capitulos] == [1, 2, 4]
    assert informe.capitulos[-1].fuente == "Índice impreso"


def test_manual_sin_texto_permite_extraer():
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        datos = doc.tobytes()
    informe = core.analizar_pdf(datos, opciones=detector.OpcionesAnalisis(estrategia="manual"))
    assert informe.capitulos == []
    assert any("texto escaso" in a for a in informe.avisos)
    zip_bytes, archivos = core.construir_zip(datos, core.segmentos_por_intervalo(2, 1))
    assert zip_bytes.startswith(b"PK")
    assert len(archivos) == 2


def test_ocr_falla_sin_perder_diagnostico(monkeypatch):
    def fallo(*args):
        raise RuntimeError("Tesseract no instalado")
    monkeypatch.setattr(detector, "_ocr_pagina", fallo)
    datos = pdf_paginas([None, None])
    op = detector.OpcionesAnalisis(ocr="forzado")
    informe = core.analizar_pdf(datos, opciones=op)
    assert len(informe.diagnostico) == 2
    assert any("Tesseract no instalado" in a for a in informe.avisos)
    assert all(p["caracteres"] > 0 for p in informe.diagnostico)


def test_ocr_respeta_limite(monkeypatch):
    llamadas = []
    def ocr(pagina, opciones):
        llamadas.append(pagina.number)
        return pagina.get_textpage()
    monkeypatch.setattr(detector, "_ocr_pagina", ocr)
    op = detector.OpcionesAnalisis(ocr="forzado", limite_ocr=1)
    informe = core.analizar_pdf(pdf_paginas(["Prefacio", "Chapter 1", "Chapter 2"]), opciones=op)
    assert llamadas == [0]
    assert informe.diagnostico[0]["ocr"]
    assert any("límite OCR" in a for a in informe.avisos)


@pytest.mark.parametrize("cap", [core.Capitulo("A", 0, 1), core.Capitulo("A", 1, 99),
                                  core.Capitulo("A", 2, 1), core.Capitulo("A", 1.5, 2),
                                  core.Capitulo("A", float("nan"), 2), core.Capitulo("", 1, 1)])
def test_rangos_invalidos(cap):
    with pytest.raises(core.ErrorSegmentador):
        core.construir_zip(pdf_paginas([None] * 3), [cap])


def test_rechaza_solapamientos_y_advierte_huecos():
    with pytest.raises(core.ErrorSegmentador, match="solapamientos"):
        core.validar_segmentos([core.Capitulo("A", 1, 3), core.Capitulo("B", 3, 4)], 5)
    assert core.validar_segmentos([core.Capitulo("A", 2, 3)], 5) == ["Páginas no incluidas: 1–1, 4–5"]


def test_zip_colisiones_y_nombres_windows():
    caps = [core.Capitulo("CON", 1, 1), core.Capitulo("con", 2, 2), core.Capitulo("CON", 3, 3)]
    datos, archivos = core.construir_zip(pdf_paginas([None] * 3), caps, formato_nombre="titulo")
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        assert len({n.casefold() for n in z.namelist()}) == 3
        assert z.namelist() == [a["nombre"] for a in archivos]
    assert core.limpiar_nombre("...") == "Capitulo_Sin_Titulo"


def test_informe_opcional_dentro_zip():
    datos, _ = core.construir_zip(pdf_paginas([None]), [core.Capitulo("Portada", 1, 1)], informe={"prueba": "sí"})
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        assert "indice_segmentos.csv" in z.namelist()
        assert json.loads(z.read("informe_segmentacion.json")) == {"prueba": "sí"}


def test_inspeccion_y_huella():
    datos = pdf_paginas(["Prefacio"])
    vista = core.inspeccionar_pagina(datos, 1)
    assert vista["imagen"].startswith(b"\x89PNG")
    assert "Prefacio" in vista["texto"]
    assert len(core.huella_pdf(datos)) == 64
    with pytest.raises(core.ErrorSegmentador):
        core.inspeccionar_pagina(datos, 2)


def test_filas_editor_vacias_e_incompletas():
    assert filas_a_segmentos(pd.DataFrame()) == []
    with pytest.raises(core.ErrorSegmentador, match="Completa"):
        filas_a_segmentos(pd.DataFrame([{"incluir": True, "titulo": "A", "inicio": 1, "fin": None}]))
    with pytest.raises(core.ErrorSegmentador, match="enteros"):
        filas_a_segmentos(pd.DataFrame([{"incluir": True, "titulo": "A", "inicio": 1.5, "fin": 2}]))


def test_opciones_invalidas_y_pdf_roto():
    with pytest.raises(core.ErrorSegmentador):
        core.analizar_pdf(b"no es PDF")
    with pytest.raises(core.ErrorSegmentador, match="Estrategia"):
        core.analizar_pdf(pdf_paginas([None]), opciones=detector.OpcionesAnalisis(estrategia="inexistente"))


def test_busqueda_normalizada_y_limite():
    datos = pdf_paginas(["Prefácio", "Prefácio", "Prefácio"])
    resultados, errores = core.buscar_texto(datos, "prefacio", limite=2)
    assert [r["pagina"] for r in resultados] == [1, 2]
    assert errores == []
    with pytest.raises(core.ErrorSegmentador):
        core.buscar_texto(datos, "a")


def test_filas_nuevas_y_excluidas():
    tabla = pd.DataFrame([
        {"incluir": True, "titulo": "Portada", "inicio": 1, "fin": 2},
        {"incluir": False, "titulo": None, "inicio": None, "fin": None},
    ])
    caps = filas_a_segmentos(tabla)
    assert [(c.titulo, c.inicio, c.fin) for c in caps] == [("Portada", 1, 2)]
    assert caps[0].categoria == "Portada"


def test_ocr_real_opcional():
    import os
    tessdata = os.environ.get("SEGMENTADOR_TESSDATA_TEST")
    if not tessdata:
        pytest.skip("OCR real opcional: define SEGMENTADOR_TESSDATA_TEST con eng.traineddata instalado")
    # Crear una imagen de texto y meterla en un PDF SIN capa de texto.
    with fitz.open() as doc:
        pagina = doc.new_page()
        pagina.insert_text((72, 110), "PREFACE", fontsize=32)
        pagina.insert_text((72, 160), "Medical handbook test page.", fontsize=14)
        imagen = pagina.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    with fitz.open() as doc:
        pagina = doc.new_page()
        pagina.insert_image(pagina.rect, stream=imagen)
        datos = doc.tobytes()
    op = detector.OpcionesAnalisis(ocr="automatico", idioma_ocr="eng", tessdata=tessdata, limite_ocr=1)
    informe = core.analizar_pdf(datos, opciones=op)
    assert informe.diagnostico[0]["ocr"]
    assert informe.capitulos[0].categoria == "Prefacio"
    assert "PREFACE" in informe.diagnostico[0]["muestra"]


def test_titulo_grande_no_se_descarta_por_repetirse_como_cabecera():
    with fitz.open() as doc:
        for n in range(5):
            p = doc.new_page()
            p.insert_text((72, 30), "Chapter 1", fontsize=9)
            if n == 0:
                p.insert_text((72, 110), "Chapter 1", fontsize=24)
            p.insert_text((72, 250), "Contenido suficientemente largo para estimar la fuente del cuerpo.", fontsize=10)
        datos = doc.tobytes()
    informe = core.analizar_pdf(datos, opciones=detector.OpcionesAnalisis(estrategia="texto"))
    assert len(informe.capitulos) == 1
    assert informe.capitulos[0].inicio == 1
    assert informe.capitulos[0].fin == 5


def test_fallo_extraccion_se_informa_con_rango(monkeypatch):
    datos = pdf_paginas(["Prefacio"])
    def fallo(*args, **kwargs):
        raise RuntimeError("Página dañada")
    monkeypatch.setattr(fitz.Document, "insert_pdf", fallo)
    with pytest.raises(core.ErrorSegmentador, match="páginas 1–1"):
        core.construir_zip(datos, [core.Capitulo("Prefacio", 1, 1)])
