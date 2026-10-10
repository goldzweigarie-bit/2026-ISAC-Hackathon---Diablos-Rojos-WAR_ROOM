"""Las pruebas sustituyen al API 1 y al API 2 por datos sintéticos (tests/sintetico.py).

Antes de importar la app se apunta STUFFPLUS_DATA_DIR a una carpeta temporal (con la configuración real del repo
y un roster sintético) y se reemplazan los métodos de Fuentes que hablan por red.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "tests"))

DATA_PRUEBA = Path(tempfile.mkdtemp(prefix="traductor_pruebas_"))
for carpeta in ("reference", "schedule"):
    shutil.copytree(BACKEND / "data" / carpeta, DATA_PRUEBA / carpeta)
os.environ["STUFFPLUS_DATA_DIR"] = str(DATA_PRUEBA)
os.environ.setdefault("API1_KEY", "llave-de-prueba")
os.environ.setdefault("API2_KEY", "llave-de-prueba")

import sintetico  # noqa: E402
from app.fuentes import Fuentes  # noqa: E402

PITCHEOS, ROSTER = sintetico.generar()
(DATA_PRUEBA / "rosters").mkdir()
ROSTER.write_csv(DATA_PRUEBA / "rosters" / "2026.csv")

# Lo que "tiene" el API 2 en cada prueba. None = la tabla todavía no existe.
API2: dict = {"stuff_plus_por_pitcher_tipo": None, "validacion": None}


def tabla_stuff_falsa(con_media: bool = True) -> pl.DataFrame:
    """Una tabla como la que subirá el modelo: un renglón por pitcher × temporada × tipo.
    Para poder comprobar el mapeo, el valor codifica el nivel: 100 / 105 / 110 + ruido chico."""
    keys = ["pitcher_anon_id", "year", "tipo"]
    t = (PITCHEOS.with_columns(tipo=pl.col("AutoPitchType").replace({"Sweeper": "Slider"}))
         .group_by(keys).len(name="pitcheos").sort(keys))
    ruido = pl.Series(np.random.default_rng(1).normal(0, 1, t.height))
    t = t.with_columns(stuff_plus_nivel_mar=100 + ruido, stuff_plus_cdmx=110 + ruido)
    return t.with_columns(stuff_plus_media=105 + ruido) if con_media else t


def _pitcheos(self):
    self.estado["pitcheos"] = "api1"
    return PITCHEOS.clone()


def _tabla_api2(self, nombre):
    self.estado[nombre] = "api2" if API2.get(nombre) is not None else "no_disponible"
    return API2.get(nombre)


Fuentes.pitcheos = _pitcheos
Fuentes.tabla_api2 = _tabla_api2
Fuentes.metadatos_api2 = lambda self: {"stuff_plus_por_pitcher_tipo": {"modelo": "stuff_plus", "version": "v-prueba"}}


@pytest.fixture(scope="session")
def app_main():
    from app import main
    return main
