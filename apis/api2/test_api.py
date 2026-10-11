"""
Pruebas automáticas del API 2. Correr desde la carpeta api2/:
    python3 -m pytest -v

Usan una carpeta temporal y llaves de prueba: no tocan tus resultados reales ni tu .env.
"""
import io
import os
import sys
import tempfile
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

# Configuración de prueba ANTES de importar main (main lee las variables al cargarse)
CARPETA_PRUEBA = Path(tempfile.mkdtemp(prefix="api2_pruebas_"))
os.environ["RESULTADOS_DIR"] = str(CARPETA_PRUEBA)
os.environ["API_KEY"] = "lectura-de-prueba-123"
os.environ["API_KEY_ESCRITURA"] = "escritura-de-prueba-456"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

LECTURA = {"X-API-Key": "lectura-de-prueba-123"}
ESCRITURA = {"X-API-Key": "escritura-de-prueba-456"}
TABLA = pl.DataFrame({"pitcher_anon_id": ["pitcher_00001", "pitcher_00002", "pitcher_00003"],
                      "year": [2025, 2025, 2026], "tipo": ["Slider", "Four-Seam", "Slider"],
                      "altitude_category": ["No Altitude", "Extreme Altitude", "No Altitude"],
                      "stuff_plus": [104.2, 97.1, 111.0]})


def parquet(df: pl.DataFrame) -> bytes:
    b = io.BytesIO()
    df.write_parquet(b)
    return b.getvalue()


def subir(c, df=TABLA, nombre="stuff_plus_por_pitcher", version="v1", llave=ESCRITURA):
    return c.post(f"/resultados/{nombre}", params={"modelo": "stuff_plus", "version": version},
                  content=parquet(df), headers=llave)


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


def test_salud_sin_llave(cliente):
    assert cliente.get("/salud").json()["ok"] is True


def test_leer_pide_llave(cliente):
    assert cliente.get("/resultados").status_code == 401
    assert cliente.get("/resultados", headers={"X-API-Key": "incorrecta"}).status_code == 401


def test_llave_de_lectura_no_puede_subir(cliente):
    assert subir(cliente, llave=LECTURA).status_code == 403


def test_subir_y_leer_identico(cliente):
    r = subir(cliente)
    assert r.status_code == 200 and r.json()["renglones"] == 3
    remoto = pl.read_parquet(io.BytesIO(
        cliente.get("/resultados/stuff_plus_por_pitcher/descargar", headers=LECTURA).content))
    assert_frame_equal(remoto, TABLA)


def test_metadatos(cliente):
    info = cliente.get("/resultados", headers=LECTURA).json()["stuff_plus_por_pitcher"]
    assert info["modelo"] == "stuff_plus" and info["version"] == "v1" and info["renglones"] == 3


def test_filtros(cliente):
    r = cliente.get("/resultados/stuff_plus_por_pitcher", headers=LECTURA,
                    params={"tipo": "Slider", "altitud": "No Altitude"}).json()
    assert r["total"] == 2 and all(x["tipo"] == "Slider" for x in r["registros"])


def test_reemplazo_guarda_historial(cliente):
    subir(cliente, TABLA.head(1), version="v2")
    assert cliente.get("/resultados", headers=LECTURA).json()["stuff_plus_por_pitcher"]["version"] == "v2"
    assert any("stuff_plus_por_pitcher__" in p.name and "v1" in p.name
               for p in (CARPETA_PRUEBA / "historial").iterdir())


def test_sobrevive_reinicio():
    """Lo subido se guarda en disco: un servidor nuevo lo vuelve a cargar."""
    with TestClient(main.app) as c:
        assert "stuff_plus_por_pitcher" in c.get("/salud").json()["tablas"]


def test_nombre_invalido(cliente):
    assert subir(cliente, nombre="..%2F..%2Fhack").status_code in (404, 422)
    assert subir(cliente, nombre="Mayusculas").status_code == 422


def test_cuerpo_no_parquet(cliente):
    r = cliente.post("/resultados/x", params={"modelo": "m"}, content=b"esto no es parquet", headers=ESCRITURA)
    assert r.status_code == 400


def test_tabla_inexistente(cliente):
    assert cliente.get("/resultados/no_existe", headers=LECTURA).status_code == 404


def test_borrar_mueve_a_historial(cliente):
    subir(cliente, nombre="temporal")
    assert cliente.delete("/resultados/temporal", headers=LECTURA).status_code == 403
    assert cliente.delete("/resultados/temporal", headers=ESCRITURA).status_code == 200
    assert cliente.get("/resultados/temporal", headers=LECTURA).status_code == 404
    assert any(p.name.startswith("temporal__") for p in (CARPETA_PRUEBA / "historial").iterdir())


def test_cliente_python():
    """ClienteAPI2.subir() y .leer() de api/cliente.py funcionan contra el API (vía TestClient)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
    from cliente import ClienteAPI2
    with TestClient(main.app) as c:
        api2 = ClienteAPI2("http://testserver", "escritura-de-prueba-456")
        api2.sesion = c                                   # TestClient habla igual que requests.Session
        api2.sesion.headers["X-API-Key"] = "escritura-de-prueba-456"
        api2.subir("bayesball_prueba", TABLA, modelo="bayesball", version="v1")
        assert_frame_equal(api2.leer("bayesball_prueba"), TABLA)
        assert api2.tablas()["bayesball_prueba"]["modelo"] == "bayesball"
