"""Regresiones de los errores de arranque observados en Windows."""

import pytest

from verificar_proyecto import FUENTES, RAIZ, main, verificar_archivo


def test_archivos_distribuidos_validos():
    for nombre in (*FUENTES, ".streamlit/config.toml"):
        assert verificar_archivo(RAIZ / nombre) == []
    assert main() == 0


@pytest.mark.parametrize("marcador", ["<<<<<<< HEAD", "=======", ">>>>>>> abc123", "||||||| base"])
@pytest.mark.parametrize("nombre", ["app_web.py", "config.toml"])
def test_detecta_conflictos(tmp_path, marcador, nombre):
    ruta = tmp_path / nombre
    ruta.write_text(marcador + "\n", encoding="utf-8")
    assert any("conflicto de Git" in error for error in verificar_archivo(ruta))


def test_detecta_bom_toml(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text('[theme]\nbase = "light"\n', encoding="utf-8-sig")
    assert "BOM" in verificar_archivo(ruta)[0]


@pytest.mark.parametrize("nombre,contenido", [
    ("app_web.py", "def funcion(\n"),
    ("config.toml", "[theme\n"),
])
def test_detecta_sintaxis_invalida(tmp_path, nombre, contenido):
    ruta = tmp_path / nombre
    ruta.write_text(contenido, encoding="utf-8")
    assert "sintaxis inválida" in verificar_archivo(ruta)[0]


def test_error_si_falta_archivo(tmp_path):
    assert "no se pudo leer" in verificar_archivo(tmp_path / "ausente.py")[0]


def test_main_falla_sin_modificar_archivos(tmp_path, monkeypatch, capsys):
    import verificar_proyecto

    monkeypatch.setattr(verificar_proyecto, "RAIZ", tmp_path)
    ruta = tmp_path / "app_web.py"
    contenido = b">>>>>>> abc123\n"
    ruta.write_bytes(contenido)
    assert main() == 1
    assert "conflicto de Git" in capsys.readouterr().err
    assert ruta.read_bytes() == contenido
