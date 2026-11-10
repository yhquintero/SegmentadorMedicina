"""Herramientas Web de análisis, inspección y corrección de segmentos."""
import math

import pandas as pd
import streamlit as st

import segmentador_core as core
from deteccion_pdf import OpcionesAnalisis, categoria_titulo


ESTRATEGIAS = {
    "combinado": "Automático combinado · marcadores + texto + tipografía",
    "marcadores": "Solo marcadores · elegir profundidad",
    "texto": "Solo títulos reconocidos · ES / EN / PT / FR / DE / IT",
    "tipografia": "Solo tipografía · títulos grandes (experimental)",
    "indice": "Índice impreso · números y puntos guía (experimental)",
    "manual": "Manual · diagnosticar y definir rangos sin detección",
}


def opciones_analisis():
    with st.expander("🧪 Laboratorio PDF · métodos y OCR", expanded=False):
        st.caption("Prueba otro método cuando el automático no acierte. Las propuestas son heurísticas: "
                   "revísalas antes de generar. Ningún servicio externo recibe el documento.")
        estrategia = st.selectbox("Método de segmentación", list(ESTRATEGIAS),
                                 format_func=ESTRATEGIAS.get, key="analisis_metodo")
        a, b = st.columns(2)
        nivel = a.number_input("Profundidad de marcadores", min_value=1, max_value=10, value=1)
        umbral = b.slider("Tamaño de título / cuerpo", 1.05, 3.0, 1.35, .05,
                          help="Solo afecta a la tipografía. Un valor alto reduce falsos positivos.")
        preliminares = st.checkbox("Conservar páginas anteriores al primer segmento", value=True,
                                   help="Crea «Portada y preliminares (revisar)»; no adivina sus límites internos.")
        a, b = st.columns(2)
        desfase = a.number_input("Desfase del índice impreso", min_value=-2000, max_value=2000, value=0,
                                help="Página física = número impreso + desfase. Las etiquetas PDF exactas tienen prioridad.")
        paginas = b.number_input("Páginas iniciales donde buscar índice", min_value=1, max_value=200, value=20)
        ocr = st.selectbox("OCR local (opcional)", ["ninguno", "automatico", "forzado"],
                          format_func=lambda v: {"ninguno": "Desactivado · rápido",
                                                "automatico": "Solo páginas con texto escaso o corrupto",
                                                "forzado": "Todas las páginas hasta el límite"}[v])
        a, b = st.columns(2)
        idioma = a.text_input("Idiomas Tesseract", value="spa+eng", help="Ejemplos: spa, eng, por, fra, deu, ita. Instala sus archivos traineddata.")
        limite = b.number_input("Máximo de páginas con OCR", min_value=0, max_value=500, value=20)
        tessdata = st.text_input("Carpeta tessdata (opcional)", help="Ruta local en el equipo que ejecuta Streamlit. No se ejecutan comandos de shell.")
        st.info("OCR requiere los datos de Tesseract instalados. Es lento y puede cometer errores; "
                "el límite evita procesar un libro entero por accidente. Se usa para detectar y revisar texto, "
                "no añade una capa OCR a los PDF exportados.")
    return OpcionesAnalisis(estrategia=estrategia, nivel_toc=int(nivel),
                           incluir_preliminares=preliminares, ocr=ocr, idioma_ocr=idioma.strip(),
                           tessdata=tessdata.strip(), limite_ocr=int(limite), umbral_titulo=umbral,
                           desfase_indice=int(desfase), paginas_indice=int(paginas))


def _reemplazar(job, caps):
    job["capitulos"] = caps
    job.pop("generado", None)
    job.pop("base_editor", None)
    job.pop("tabla_editada", None)
    job["revision"] = job.get("revision", 0) + 1
    job["estado"] = "corregido"
    job["metodo"] = "Índice pegado" if caps and caps[0].fuente == "Índice impreso" else "Rangos manuales"
    st.rerun()


def laboratorio(job):
    ident = job["id"]
    avisos = job.get("avisos", [])
    for aviso in avisos[:3]:
        st.warning(aviso)
    if len(avisos) > 3:
        st.caption(f"Hay {len(avisos)} avisos. Abre Diagnóstico para verlos todos.")
    with st.expander("🔬 Diagnóstico · páginas, candidatos y vista del documento"):
        st.caption("Páginas físicas desde 1. Una etiqueta romana o impresa no equivale necesariamente "
                   "al número de página del archivo. Dos secciones en la misma página requieren elegir un límite: "
                   "no se recorta contenido dentro de una página.")
        if avisos:
            st.dataframe(pd.DataFrame({"Avisos del análisis": avisos}), hide_index=True)
        diag = job.get("diagnostico", [])
        if diag:
            st.dataframe(pd.DataFrame(diag), hide_index=True)
        candidatos = job.get("candidatos", [])
        if candidatos:
            st.markdown("**Candidatos y procedencia**")
            st.caption("La prioridad es una regla heurística, no una probabilidad. «Elegido» significa límite propuesto; "
                       "la tabla de segmentos de abajo es la que se exporta.")
            st.dataframe(pd.DataFrame(candidatos), hide_index=True)
        st.json({"sha256": job.get("sha256"), "reparado_al_abrir": job.get("reparado", False),
                 "opciones": {k: v for k, v in job.get("opciones", {}).items() if k != "tessdata"}})
        consulta = st.text_input("Buscar palabras en el texto nativo", key=f"busqueda_{ident}",
                                 placeholder="Prefacio, copyright, editor…")
        if st.button("Buscar en el documento", key=f"buscar_{ident}"):
            try:
                resultados, errores = core.buscar_texto(job["bytes"], consulta, job.get("password"))
                job["busqueda_resultados"] = resultados
                job["busqueda_consulta"] = consulta
                job["busqueda_errores"] = errores
            except core.ErrorSegmentador as exc:
                st.error(str(exc))
        if "busqueda_resultados" in job:
            st.caption(f"Búsqueda realizada: {job['busqueda_consulta']} · hasta 100 páginas con coincidencias. "
                       "No busca dentro de imágenes ni usa los resultados OCR del análisis.")
            if job["busqueda_resultados"]:
                st.dataframe(pd.DataFrame(job["busqueda_resultados"]), hide_index=True)
            else:
                st.info("No hay coincidencias en el texto nativo. Inspecciona la página o prueba OCR.")
            if job.get("busqueda_errores"):
                st.warning(f"No se pudieron leer estas páginas: {job['busqueda_errores']}")
        numero = st.number_input("Página física a inspeccionar", min_value=1, max_value=job["paginas"],
                                 value=1, key=f"pagina_{ident}")
        ocr = st.checkbox("Aplicar OCR a esta página", key=f"ver_ocr_{ident}")
        if st.button("🔎 Inspeccionar página", key=f"inspeccionar_{ident}"):
            try:
                op = job.get("opciones", {})
                job["inspeccion"] = core.inspeccionar_pagina(
                    job["bytes"], int(numero), job.get("password"), ocr,
                    op.get("idioma_ocr", "spa+eng"), op.get("tessdata", ""))
                job["pagina_inspeccion"] = numero
            except core.ErrorSegmentador as exc:
                st.error(str(exc))
        if job.get("inspeccion"):
            vista = job["inspeccion"]
            st.caption(f"Página inspeccionada: {job['pagina_inspeccion']} · etiqueta: {vista['etiqueta'] or 'sin etiqueta'} · rotación: {vista['rotacion']}°")
            imagen, texto = st.columns(2)
            imagen.image(vista["imagen"], caption="Vista de la página original")
            texto.code(vista["texto"][:30000] or "Sin texto seleccionable. Prueba OCR o define rangos manuales.", language=None)

    with st.expander("🛠 Corregir detección · rangos, intervalos e índice pegado"):
        st.markdown("**Puedes añadir, borrar y editar filas directamente en la tabla de segmentos.** "
                    "Marca Incluir, escribe un título y las páginas Desde / Hasta. "
                    "También funciona en un PDF escaneado sin OCR.")
        st.warning("Las acciones siguientes reemplazan toda la tabla y descartan el ZIP anterior. "
                   "No cambian el PDF original.")
        intervalo = st.number_input("Páginas por segmento", min_value=1, max_value=job["paginas"], value=1,
                                    key=f"intervalo_{ident}")
        if st.button("Dividir por intervalos", key=f"dividir_{ident}"):
            _reemplazar(job, core.segmentos_por_intervalo(job["paginas"], int(intervalo)))
        indice = st.text_area("Pegar índice: título ... página", key=f"indice_{ident}",
                              placeholder="Portada ... 1\nPrefacio ... 3\nCapítulo 1 ... 9")
        desfase = st.number_input("Desfase del índice pegado", min_value=-2000, max_value=2000,
                                  value=0, key=f"desfase_{ident}")
        if st.button("Aplicar índice a la tabla", key=f"aplicar_indice_{ident}"):
            try:
                caps, avisos = core.segmentos_desde_indice(job["bytes"], indice, job.get("password"), int(desfase))
                for aviso in avisos:
                    st.warning(aviso)
                if avisos:
                    st.error("Hay destinos sin resolver. Corrige el índice antes de reemplazar la tabla.")
                elif not caps:
                    st.error("Sin entradas válidas. Usa «Título ... 12» o números romanos con etiquetas PDF existentes.")
                else:
                    _reemplazar(job, caps)
            except core.ErrorSegmentador as exc:
                st.error(str(exc))
        if st.button("Usar documento completo como segmento", key=f"completo_{ident}"):
            _reemplazar(job, [core.Capitulo("Documento completo (revisar)", 1, job["paginas"])])


def filas_a_segmentos(tabla):
    caps = []
    for _, fila in tabla.iterrows():
        if pd.isna(fila.get("incluir")) or not bool(fila["incluir"]):
            continue
        titulo = fila.get("titulo")
        inicio, fin = fila.get("inicio"), fila.get("fin")
        if pd.isna(titulo) or not str(titulo).strip() or pd.isna(inicio) or pd.isna(fin):
            raise core.ErrorSegmentador("Completa título, Desde y Hasta en todas las filas marcadas.")
        try:
            if not math.isfinite(float(inicio)) or not math.isfinite(float(fin)) or float(inicio) != int(inicio) or float(fin) != int(fin):
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            raise core.ErrorSegmentador("Las páginas deben ser números enteros.") from None
        categoria = fila.get("categoria")
        fuente = fila.get("fuente")
        caps.append(core.Capitulo(str(titulo).strip(), int(inicio), int(fin),
                                 "Manual" if pd.isna(fuente) else str(fuente),
                                 categoria_titulo(str(titulo)) if pd.isna(categoria) else str(categoria)))
    return caps


def firma_plan(caps, formato):
    return (tuple((c.titulo, c.inicio, c.fin) for c in caps), formato)
