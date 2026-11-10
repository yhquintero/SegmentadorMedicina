# Segmentador de Libros Médicos PDF

Divide automáticamente libros PDF de Medicina por capítulos.

## Instalación

1. Instala Python 3.10+ desde https://python.org (marca "Add Python to PATH").
2. Abre una terminal en esta carpeta y ejecuta:

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## Uso — Versión GUI (recomendada)

```bash
python segmentar_libros_gui.py
```

1. Pulsa "Elegir…" para seleccionar el PDF.
2. Elige la carpeta de salida (se propone una automáticamente).
3. Si el PDF tiene contraseña, escríbela.
4. Pulsa "▶ Segmentar PDF".

## Uso — Versión CLI

```bash
python segmentar_libros.py libro.pdf carpeta_salida/
python segmentar_libros.py libro.pdf carpeta_salida/ --password 1234
```

## Uso — Versión Web

```bash
streamlit run app_web.py
```

## Crear el .exe (Windows)

```bash
pyinstaller --onefile --windowed --name "SegmentadorMedicina" ^
  --collect-all=pymupdf --collect-all=fitz ^
  segmentar_libros_gui.py
```

El .exe aparecerá en `dist/SegmentadorMedicina.exe`.

## Problemas comunes

- **"No se detectaron capítulos"**: PDF escaneado. Necesita OCR previo.
- **Antivirus bloquea el .exe**: falso positivo de PyInstaller. Añadir a exclusiones.
- **Error de memoria**: PDF demasiado grande. Dividir manualmente o usar más RAM.