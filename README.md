<div align="center">

<img src="assets/segmentador-icon.png" width="96" alt="Logotipo de SegmentadorMedicina" />

# Segmentador de Libros Médicos PDF

### Divide. Revisa. Descarga.

**Divide automáticamente libros PDF de Medicina por capítulos — con vista previa editable,
modo claro/oscuro y descarga exclusivamente en ZIP con los capítulos en PDF dentro.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](#-requisitos)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-motor%20PDF-cc3c2c?style=flat-square)](#-requisitos)
[![Streamlit](https://img.shields.io/badge/Streamlit-vista%20Web-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](#-inicio-rápido)
[![Plataformas](https://img.shields.io/badge/plataformas-Windows%20·%20macOS%20·%20Linux-1e1b4b?style=flat-square)](#-requisitos)
[![Local](https://img.shields.io/badge/procesamiento-100%25%20local-059669?style=flat-square)](#-privacidad)
[![CI](https://github.com/yhquintero/SegmentadorMedicina/actions/workflows/ci.yml/badge.svg)](https://github.com/yhquintero/SegmentadorMedicina/actions/workflows/ci.yml)

[Resumen](#-resumen) · [Funciones](#-funciones) · [Vista Web](#-vista-web) · [Requisitos](#-requisitos) · [Inicio rápido](#-inicio-rápido) · [Pruebas y CI](#-pruebas-y-ci) · [Problemas comunes](#-problemas-comunes)

</div>

<p align="center">
  <img src="assets/hero.jpg" width="100%" alt="Libros de Medicina con estetoscopio: un capítulo por archivo" />
</p>

---

## 🧭 Resumen

| Ficha del proyecto | Detalle |
|---|---|
| **Qué es** | Herramienta que divide libros PDF de Medicina en un PDF por capítulo |
| **Para quién** | Estudiantes, docentes, bibliotecas y profesionales de la salud que estudian por capítulos |
| **Cómo está hecho** | Python 3.10+ · [PyMuPDF](https://pymupdf.readthedocs.io/) (detección y extracción) · Streamlit (vista Web) · Tkinter (escritorio) · PyInstaller (.exe) |
| **Dónde corre** | Windows, macOS y Linux. Sin dependencia de la nube |
| **Cómo se usa** | Vista Web (navegador), GUI de escritorio o línea de comandos |
| **Detección** | Marcadores/TOC del propio PDF (método principal) y, si no hay, detección de títulos por texto |

> 📖 **Antes de generar nada** la vista Web te muestra la lista de capítulos detectados:
> edita los títulos, excluye los que no quieras y confirma. Nunca se genera a ciegas.

---

## ✨ Funciones

- 📚 **Doble método de detección** — usa los marcadores (TOC) del PDF y, si no existen, busca títulos de capítulo en el texto (*Capítulo*, *Chapter*, *Sección*, *Unidad*, *Parte*, *Tema*…).
- 👀 **Vista previa con confirmación** — revisa capítulos y páginas antes de extraer: edita títulos y desmarca los que no quieras.
- 📦 **Varios libros a la vez** — sube uno o varios PDF y gestiona cada uno en su pestaña.
- 📥 **Descarga solo en ZIP** — pulsa Generar para obtener un ZIP por libro con todos los capítulos seleccionados en PDF; no se ofrecen PDF individuales ni CSV separados; el nombre de cada archivo sigue el formato que elijas (`01_Título`, `Cap01_Título`, `01. Título` o `Solo_Título`).
- 🔒 **PDF protegidos** — acepta documentos con contraseña (se introduce en Ajustes).
- 🌗 **Tema Claro, Oscuro y Automático** — el modo automático sigue a tu sistema operativo en vivo.
- 📊 **Historial de la sesión** — cada trabajo con su método, capítulos, páginas y estado.
- 🖥 **Tres versiones** — Web (Streamlit), escritorio (Tkinter) y CLI, con el mismo motor.

---

## 🖥 Vista Web

La vista Web se ejecuta con Streamlit y está diseñada con el lenguaje visual de
[NovaGest · Cuadres, Inventarios](https://github.com/yhquintero/inventario) (del mismo autor):
rail lateral oscuro, panel con héroe e indicadores, tablas con etiquetas de estado y modo claro/oscuro.

```bash
streamlit run app_web.py
```

1. **Panel** — sube los PDF, pulsa **Analizar** y revisa la vista previa de capítulos.
2. **Generar** — extrae los capítulos seleccionados y prepara un ZIP con los PDF dentro. El único botón de descarga es **Descargar todos los capítulos (ZIP)**.
3. **Historial** — resumen de los trabajos de la sesión.
4. **Ajustes** — tema, contraseña del PDF y formato de los nombres de archivo.
5. **Ayuda** — problemas comunes y guía rápida.

---

## ⚙️ Requisitos

| Componente | Necesitas |
|---|---|
| **Python** | 3.10 o posterior ([python.org](https://python.org), marca *Add Python to PATH*) |
| **Vista Web** | Cualquier navegador actualizado |
| **GUI / .exe** | Windows (para el .exe compilado) o cualquier sistema con Tkinter |
| **Opcional** | PyInstaller, solo para crear el ejecutable |

---

## 🚀 Inicio rápido

### 1 · Instalar dependencias

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2 · Vista Web (recomendada)

```bash
python verificar_proyecto.py
python -m streamlit run app_web.py
```

El verificador no modifica archivos: comprueba conflictos de Git, codificación y
sintaxis antes del arranque. `python -m streamlit` usa el entorno virtual activo.

### 3 · Versión GUI (escritorio)

```bash
python segmentar_libros_gui.py
```

1. Pulsa **Elegir…** para seleccionar el PDF y la carpeta de salida.
2. Si el PDF tiene contraseña, escríbela.
3. Pulsa **▶ Segmentar PDF**.

### 4 · Versión CLI

```bash
python segmentar_libros.py libro.pdf carpeta_salida/
python segmentar_libros.py libro.pdf carpeta_salida/ --password 1234
```

---

## 📦 Crear el .exe (Windows)

```bash
pyinstaller --onefile --windowed --name "SegmentadorMedicina" ^
  --collect-all=pymupdf --collect-all=fitz ^
  segmentar_libros_gui.py
```

El `.exe` aparecerá en `dist/SegmentadorMedicina.exe`.

---

## 🧪 Pruebas y CI

El motor de segmentación (`segmentador_core.py`) y la vista Web tienen pruebas
automatizadas que construyen PDFs reales en memoria:

```bash
pip install pytest
python -m pytest -q
```

| Suite | Qué cubre |
|---|---|
| `tests/test_segmentador_core.py` | Detección por TOC y por texto, contraseñas, limpieza de nombres, ZIP, CSV y progreso |
| `tests/test_app_web.py` | Flujo completo de la vista Web sin navegador (subir → analizar → generar → historial) con `streamlit.testing.v1` |

La [integración continua](.github/workflows/ci.yml) ejecuta las dos suites y un
arranque de humo de la vista Web en cada *push* y *pull request*.

---

## 🔒 Privacidad

El análisis y la extracción se hacen **en tu propio equipo**. Ningún PDF se envía a
servidores ni a servicios de terceros; el ZIP se genera en la sesión de tu navegador
y se descarga directamente.

---

## ❓ Problemas comunes

### Errores de arranque en Windows

**`SyntaxError: invalid decimal literal` en una línea `>>>>>>> ...`** significa que
el archivo contiene un conflicto de Git sin resolver. **`TOMLDecodeError: Invalid
statement (at line 1, column 1)`** puede indicar otro conflicto en la configuración
o una marca BOM (frecuente al guardar archivos desde Windows PowerShell).

Ejecuta `python verificar_proyecto.py` para identificar el archivo afectado. Si el
verificador no está aún en tu copia local, inspecciona `app_web.py` y
`.streamlit/config.toml` directamente. No basta con borrar los marcadores: también
hay que elegir la versión correcta del contenido entre ellos.

Si **no necesitas conservar modificaciones locales en esos dos archivos**, puedes
recuperar la versión de `origin/main`. En PowerShell, desde la raíz del proyecto:

```powershell
# Primero guarda copias: git restore sustituirá el contenido local.
Copy-Item app_web.py app_web.py.bak
Copy-Item .streamlit/config.toml .streamlit/config.toml.bak
# Si algún comando falla, detente y revisa el error antes de continuar.
git fetch origin
git restore --source=origin/main --staged --worktree -- app_web.py .streamlit/config.toml
python verificar_proyecto.py
python -m streamlit run app_web.py
```

Esto no cambia de rama. Si tienes un merge o rebase en curso, revisa primero
`git status` y resuelve la operación; los comandos anteriores no completan ese
proceso ni recuperan cambios locales personalizados (quedan en los `.bak`).

Si persiste **solo el error TOML**, comprueba también la configuración global
`$HOME/.streamlit/config.toml`: Streamlit lee tanto la global como la del proyecto.
Guarda los archivos TOML como **UTF-8 sin BOM**; en PowerShell puedes corregir el del
proyecto, después de hacer la copia de seguridad, con:

```powershell
$ruta = (Resolve-Path .streamlit/config.toml).Path
$texto = [System.IO.File]::ReadAllText($ruta)
[System.IO.File]::WriteAllText($ruta, $texto, [System.Text.UTF8Encoding]::new($false))
```

El verificador comprueba únicamente los archivos del proyecto, no la configuración
global. No publiques archivos de configuración que contengan secretos.

- **«No se detectaron capítulos»** — el PDF suele estar escaneado (imágenes sin texto seleccionable). Necesita OCR previo (por ejemplo con [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF)).
- **«El PDF está protegido con contraseña»** — escríbela en **Ajustes → Contraseña del PDF** y vuelve a analizar.
- **El antivirus bloquea el .exe o el ZIP** — falso positivo habitual de PyInstaller y de los ZIP generados localmente. Añade el archivo a las exclusiones.
- **Error de memoria con PDF enormes** — libros de más de 500 MB pueden necesitar más RAM; divide el PDF manualmente antes de segmentar.

---

## 🙏 Créditos

- **PyMuPDF** — motor de PDF ([pymupdf.readthedocs.io](https://pymupdf.readthedocs.io/)).
- **Streamlit** — vista Web ([streamlit.io](https://streamlit.io/)).
- **NovaGest · Cuadres, Inventarios** — el sistema de gestión comercial de
  [yhquintero/inventario](https://github.com/yhquintero/inventario), cuyo lenguaje visual
  inspira la interfaz de la vista Web de este proyecto.
