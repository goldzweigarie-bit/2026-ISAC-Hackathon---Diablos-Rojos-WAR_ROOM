"""
Pruebas automáticas del API 1. Correr desde la carpeta api/:
    python3 -m pytest -v

TestClient simula peticiones HTTP sin levantar el servidor de verdad: así se comprueba
cada ruta en segundos y se detecta si un cambio rompió algo.
"""
import io

import polars as pl
import pytest
from polars.testing import assert_frame_equal
from fastapi.testclient import TestClient

import main


@pytest.fixture(scope="module")
def cliente():
    """Arranca el API una vez para todas las pruebas (carga los datos reales)."""
    with TestClient(main.app) as c:          # el "with" ejecuta el arranque (ciclo_de_vida)
        yield c


@pytest.fixture(scope="module")
def llave():
    return {"X-API-Key": main.API_KEY}


def test_salud_sin_llave(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["pitcheos"] > 600_000


def test_rechaza_sin_llave(cliente):
    assert cliente.get("/constantes/carreras").status_code == 401


def test_rechaza_llave_incorrecta(cliente):
    assert cliente.get("/constantes/carreras", headers={"X-API-Key": "incorrecta"}).status_code == 401


def test_constantes(cliente, llave):
    c = cliente.get("/constantes/carreras", headers=llave).json()
    v = c["valor_evento"]
    assert v["Out"] == 0
    assert v["HomeRun"] > v["Triple"] > v["Double"] > v["Single"] > v["Walk"] > 0   # orden lógico


def test_filtros(cliente, llave):
    r = cliente.get("/pitcheos", headers=llave,
                    params={"year": 2024, "tipo": "Slider", "altitud": "Extreme Altitude",
                            "columnas": "year,AutoPitchType,altitude_category", "limit": 50}).json()
    assert r["n"] == 50 and r["total"] > 50
    assert all(x == {"year": 2024, "AutoPitchType": "Slider", "altitude_category": "Extreme Altitude"}
               for x in r["registros"])


def test_altitud_invalida(cliente, llave):
    assert cliente.get("/pitcheos", headers=llave, params={"altitud": "Marte"}).status_code == 422


def test_columna_inexistente(cliente, llave):
    assert cliente.get("/pitcheos", headers=llave, params={"columnas": "no_existe"}).status_code == 400


def test_paginacion_sin_repetir(cliente, llave):
    p = {"year": 2025, "columnas": "PitchUID", "limit": 100}
    a = cliente.get("/pitcheos", headers=llave, params={**p, "offset": 0}).json()["registros"]
    b = cliente.get("/pitcheos", headers=llave, params={**p, "offset": 100}).json()["registros"]
    assert not {x["PitchUID"] for x in a} & {x["PitchUID"] for x in b}


def test_descarga_parquet_identica_a_los_datos(cliente, llave):
    """Lo que entrega el API debe ser exactamente lo que tiene cargado (mismos valores y tipos)."""
    r = cliente.get("/pitcheos/descargar", headers=llave, params={"year": 2025, "pitcher": "pitcher_00386"})
    remoto = pl.read_parquet(io.BytesIO(r.content))
    local = main.DATOS["pitcheos"].filter((pl.col("year") == 2025) & (pl.col("pitcher_anon_id") == "pitcher_00386"))
    assert remoto.height == local.height > 0
    assert_frame_equal(remoto, local)


def test_ya_no_tiene_resultados(cliente, llave):
    """Los resultados se mudaron al API 2."""
    assert cliente.get("/resultados", headers=llave).status_code == 404
