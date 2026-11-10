# Laboratorio PDF · guía de detección y depuración

## Alcance real

La Web v3 separa **páginas del PDF original** en segmentos: portada, copyright,
presentación, prefacio, reconocimientos, colaboradores, editores (actuales y
anteriores), notas, dedicatorias, índices, introducción, capítulos, anexos,
bibliografía y glosario. «Capítulo» en los botones también puede ser cualquiera
de estas secciones. Los títulos y rangos finales siempre son revisables.

No existe una detección universal: un PDF puede contener posiciones de glifos o
imágenes sin una estructura semántica fiable. La documentación de pypdf explica
estas diferencias entre PDF nativos, escaneados y con capa OCR. [1](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)

Sin ejemplos de los PDF que fallan no se puede prometer un porcentaje de acierto.
Las pruebas del proyecto usan documentos sintéticos; no son un benchmark de libros
reales ni cubren todas las editoriales, escrituras o formatos de impresión.

## Métodos implementados

| Método | Cuándo usarlo | Límite / control disponible |
|---|---|---|
| **Automático combinado** | Libro con marcadores incompletos y preliminares sin marcar | Combina candidatos por página; un marcador válido tiene prioridad sobre texto y tipografía |
| **Marcadores** | Índice navegable fiable | Profundidad de 1 a 10; elimina destinos inválidos y duplicados por página; orden físico |
| **Texto multilingüe** | Títulos reconocibles aunque haya cabeceras antes | Vocabulario inicial ES/EN/PT/FR/DE/IT, normalización Unicode, búsqueda en primeras líneas de la zona superior; copyright también más abajo |
| **Tipografía** | Títulos no catalogados | Compara tamaño de fuente con el cuerpo estimado; umbral configurable. Experimental, puede confundir citas, tablas y cubiertas |
| **Índice impreso** | Tabla de contenido con «Título ... página» | Examina las primeras N páginas; usa etiquetas PDF exactas o desfase numérico explícito. Experimental: columnas o saltos requieren corrección |
| **Índice pegado** | Es más fácil copiar/corregir el índice que editar cada fila | Acepta puntos guía, tabulaciones o dos espacios. No reemplaza la tabla si hay destinos inválidos o líneas mal formadas |
| **OCR local** | Escaneos o fuentes con mapa de caracteres defectuoso | Desactivado por defecto; automático en páginas con texto escaso/corrupto o forzado. Idioma, carpeta tessdata y máximo de páginas configurables |
| **Manual / intervalos** | Ningún método funciona, o el libro no tiene títulos | Añadir/borrar filas, editar títulos, tipo, inicio y fin; dividir cada N páginas o partir del documento completo. No requiere OCR |

PyMuPDF proporciona el acceso a marcadores, texto con coordenadas/tamaños y OCR
usado por este motor. [1](https://github.com/pymupdf/pymupdf)

### Reglas importantes del automático

- Busca varias líneas en la zona superior, no solo la primera línea.
- Reconoce «CHAPTER» y el número en líneas consecutivas; intenta completar el título.
- Descarta cabeceras repetidas y líneas con aspecto de entradas de índice.
- Solo propone **un límite por página**; en diagnóstico se muestran los candidatos
  alternativos y por qué se priorizó uno. La prioridad no es una probabilidad.
- Conserva opcionalmente el hueco anterior al primer límite como
  **Portada y preliminares (revisar)**. No inventa la separación interna de esas páginas.
- Los segmentos llegan hasta la página anterior al siguiente inicio. Verifica esos
  finales, especialmente las páginas blancas y el material que sigue a un capítulo.
- Las cabeceras repetidas, libros muy breves, portadas gráficas, textos a dos columnas
  y secciones con títulos muy parecidos pueden requerir corrección manual.

## Procedimiento recomendado cuando falla un libro

1. **Sube y analiza** con Automático combinado, inicialmente sin OCR.
2. Abre **Diagnóstico**: revisa caracteres por página, etiquetas, rotación, muestras,
   avisos y candidatos. Se indica si MuPDF reparó la estructura al abrirla.
3. **Busca** palabras como `prefacio`, `copyright`, `editor` o `contributors`.
   La búsqueda normaliza acentos, trabaja solo sobre texto nativo y muestra hasta
   100 páginas coincidentes. No busca en imágenes ni en el OCR de una ejecución anterior.
4. **Inspecciona** una página física: imagen del original al lado de su texto.
   Opcionalmente aplica OCR a esa página para comprobar idioma y calidad.
5. Si hay texto pero no se detecta bien, cambia a Marcadores (con más profundidad),
   Texto o Tipografía y pulsa **Analizar** de nuevo. Esto reemplaza el plan anterior.
6. Si hay un índice impreso, revisa las etiquetas y establece el desfase. Por ejemplo,
   si la página impresa 1 es la física 13, usa `12`. Los números romanos solo se
   resuelven si existen etiquetas PDF inequívocas: nunca se adivina su desplazamiento.
7. Corrige la tabla: **Incluir, título, tipo, Desde y Hasta**. Añade o elimina filas.
   Las columnas de origen y páginas originales son referencias, no valores recalculados.
8. Si todo falla, usa **intervalos** o **documento completo** como punto de partida.
   Es posible separar un escaneo por rangos sin reconocer su texto.
9. Atiende los avisos de **páginas omitidas**. Los rangos fuera del documento,
   fraccionarios, invertidos, desordenados o solapados impiden generar el ZIP.
10. Pulsa **Generar** y descarga **solo el ZIP**. El documento original no se modifica.

No se recortan regiones de una página: si Prefacio y Reconocimientos comparten una
misma página, no pueden convertirse en dos PDF sin duplicar/recortar contenido.
Esta versión exige rangos sin solapamiento y deja esa decisión al usuario.

## OCR: configuración y límites

El OCR usa la integración de PyMuPDF con Tesseract y necesita sus datos de idioma
(`spa.traineddata`, `eng.traineddata`, etc.). La documentación de PyMuPDF muestra
`get_textpage_ocr` y el uso del TextPage resultante. [2](https://pymupdf.readthedocs.io/en/latest/the-basics.html)

En Windows, una instalación habitual de Tesseract contiene los datos en:

```text
C:\Program Files\Tesseract-OCR\tessdata
```

Escribe esa carpeta en **Laboratorio PDF → Carpeta tessdata**, elige `spa+eng` solo
si tienes ambos archivos y empieza con un límite pequeño (por defecto 20 páginas).
La instalación concreta depende del sistema y de la distribución de PyMuPDF; si
falla, se conserva el texto nativo y se muestra el error, sin abortar los otros libros.

- OCR automático solo se intenta con texto escaso o abundantes caracteres de reemplazo;
  una capa OCR equivocada pero aparentemente legible puede requerir **forzado**.
- El límite cuenta páginas intentadas, no solo éxitos. Alcanzarlo genera un aviso.
- Las páginas excesivamente grandes se rechazan para OCR a 200 dpi por seguridad de memoria.
- Un fallo OCR suspende nuevos intentos de ese análisis; corrige la instalación y reanaliza.
- El OCR puede ser lento, omitir palabras y equivocarse en nombres propios o números.
- **Se usa para detectar e inspeccionar. Los segmentos exportados conservan las páginas
  originales: no se les incorpora una nueva capa de texto OCR.**

### Preprocesamiento externo (opcional, no ejecutado por la Web)

Para un escaneo inclinado o girado, OCRmyPDF ofrece corrección de inclinación,
orientación y selección de idiomas. El idioma correcto y sus paquetes importan. [1](https://ocrmypdf.readthedocs.io/en/latest/cookbook.html) [2](https://ocrmypdf.readthedocs.io/en/v11.7.3/cookbook.html)

Tras instalar OCRmyPDF y sus dependencias **por separado**, un ejemplo habitual es:

```bash
ocrmypdf --skip-text --deskew --rotate-pages -l spa+eng entrada.pdf preparado.pdf
```

Conserva siempre el original y sube `preparado.pdf` a la Web. `--skip-text` no rehace
las páginas que ya contienen texto; una capa OCR incorrecta puede necesitar otro
modo. Revisa las opciones de tu versión antes de procesar el libro completo.

## Otros enfoques internacionales evaluados, no integrados

No se añaden motores pesados o servicios de terceros sin necesidad y sin control
de privacidad. Las siguientes alternativas no están instaladas ni activadas aquí:

| Enfoque | Aplicación potencial | Por qué no es una garantía universal |
|---|---|---|
| Otro parser nativo (pypdf) | Comparar extracción en PDF digitales | No reconoce texto dentro de imágenes ni recupera semántica ausente. [1](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) |
| Docling / modelos de diseño documental | Reconstruir orden de lectura, títulos y tablas | Añade modelos y requisitos; requiere evaluar el resultado en los libros reales. El proyecto documenta conversión y reconocimiento de disposición. [1](https://github.com/docling-project/docling) |
| GROBID / estructura científica | Publicaciones técnicas, encabezados, bibliografía y XML/TEI | Especializado en publicaciones científicas; no supone una separación infalible de preliminares editoriales en cualquier libro. [1](https://github.com/kermitt2/grobid) |
| OCRmyPDF / preprocesamiento | Rotación, inclinación y capa OCR en escaneos | Mejora la entrada, pero el reconocimiento puede fallar y no identifica automáticamente todos los límites editoriales. [1](https://ocrmypdf.readthedocs.io/en/latest/cookbook.html) |

Esta revisión cubre familias principales de técnicas, no «todos los métodos
existentes». Para incorporar modelos adicionales con rigor hace falta un corpus
representativo y anotado de los PDF que actualmente fallan.

## Seguridad, trazabilidad y exportación

- El ZIP contiene los segmentos en PDF. No hay botones para descargar PDF individuales.
- Opcionalmente incluye **índice CSV e informe JSON dentro del mismo ZIP**, nunca
  como descargas separadas. El informe contiene SHA-256 del original, rangos,
  procedencia, categorías, opciones y diagnóstico por página.
- El informe **no contiene la contraseña ni la ruta tessdata**, pero sí puede incluir
  nombre del documento y muestras de texto. No lo publiques sin revisarlo.
- Los nombres de archivo se limpian y se evitan nombres reservados de Windows y
  colisiones entre títulos iguales, incluso sin numeración.
- Al cambiar el plan, el formato o la opción de informe, el ZIP anterior deja de
  ofrecerse: hay que generar de nuevo. Las correcciones de la tabla y los ajustes
  de formato/contraseña se conservan al navegar entre las vistas durante la sesión.
- La contraseña usada al analizar queda asociada al trabajo en memoria para extraer
  ese mismo libro; no se escribe en archivos ni en el informe.
- MuPDF puede reparar estructuras al abrirlas y se informa de ello. Esto no garantiza
  recuperar un archivo truncado o páginas dañadas ni modifica el original.
- La Web está pensada para ejecutarse localmente. Si la despliegas en un servidor,
  el archivo se transmite a ese servidor y se procesa allí; no equivale a procesamiento
  dentro del navegador. No expongas el servicio sin autenticación y límites de recursos.
- El límite de subida no es una garantía de memoria disponible. Documentos muy grandes
  o maliciosos pueden agotar recursos; usa copias y mantén las dependencias actualizadas.

## Pruebas reproducibles

```bash
python verificar_proyecto.py
python -m pytest -q
```

El corpus sintético cubre preliminares con marcadores parciales, vocabulario en
seis idiomas latinos, títulos bajo cabeceras y multilínea, cabeceras repetidas,
marcadores anidados, índices con etiquetas romanas/desfases, PDF sin texto,
fallos/límites OCR, corrección manual, validación de rangos, colisiones y ZIP.

La prueba **OCR real** es opcional y no descarga datos durante las pruebas. Instala
`eng.traineddata` de Tesseract y configura:

```powershell
$env:SEGMENTADOR_TESSDATA_TEST = 'C:\Program Files\Tesseract-OCR\tessdata'
python -m pytest tests/test_deteccion_avanzada.py -q
```

Sin esa variable, solo esa prueba se omite. Los fallos OCR y el límite de intentos
se prueban siempre de forma determinista sin depender de instalaciones externas.
