"""Comprueba los archivos de arranque sin iniciar Streamlit ni modificar archivos.

Ejecutar desde cualquier carpeta: python verificar_proyecto.py
"""

import ast
from pathlib import Path
import re
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


RAIZ = Path(__file__).resolve().parent
FUENTES = (
    "app_web.py",
    "segmentador_core.py",
    "segmentar_libros.py",
    "segmentar_libros_gui.py",
)
MARCADOR = re.compile(r"^(?:<{7}|={7}|>{7}|\|{7})(?:\s|$)")


def verificar_archivo(ruta: Path) -> list[str]:
    """Devuelve errores de codificación, conflictos o sintaxis del archivo."""
    try:
        datos = ruta.read_bytes()
        texto = datos.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{ruta}: no se pudo leer como UTF-8: {exc}"]

    errores = []
    if datos.startswith(b"\xef\xbb\xbf") and ruta.suffix == ".toml":
        errores.append(f"{ruta}: marca BOM al inicio; guardar como UTF-8 sin BOM.")
    for numero, linea in enumerate(texto.splitlines(), 1):
        if MARCADOR.match(linea):
            errores.append(
                f"{ruta}:{numero}: marcador de conflicto de Git sin resolver."
            )
    if errores:
        return errores

    try:
        if ruta.suffix == ".toml":
            tomllib.loads(texto)
        else:
            ast.parse(texto.lstrip("\ufeff"), filename=str(ruta))
    except (SyntaxError, ValueError) as exc:
        errores.append(f"{ruta}: sintaxis inválida: {exc}")
    return errores


def main() -> int:
    rutas = [RAIZ / nombre for nombre in FUENTES]
    rutas.append(RAIZ / ".streamlit" / "config.toml")
    errores = [error for ruta in rutas for error in verificar_archivo(ruta)]
    if errores:
        print("No se puede iniciar con estos archivos:", file=sys.stderr)
        for error in errores:
            print(f"- {error}", file=sys.stderr)
        print(
            "Consulta «Errores de arranque en Windows» en README.md. "
            "No se ha modificado ningún archivo.",
            file=sys.stderr,
        )
        return 1
    print("Correcto: configuración TOML y sintaxis Python válidas, sin conflictos de Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
