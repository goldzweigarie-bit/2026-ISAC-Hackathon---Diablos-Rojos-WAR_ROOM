"""De dónde saca sus datos el traductor: el API 1 (pitcheos) y el API 2 (resultados de los modelos).

    API 1 :8000 ──(pitcheos)──────────┐
                                      ├──→  traductor :8002  ──→  frontend
    API 2 :8001 ──(Stuff+, BayesBall)─┘

Configuración en backend/.env (ver .env.example): API1_URL, API1_KEY, API2_URL, API2_KEY.

Si el API 1 no responde al arrancar, se usa la última copia guardada en data/cache/ (para que una demo no
dependa de que todo esté prendido). Si el API 2 no responde o todavía no tiene la tabla de Stuff+, el
traductor sigue funcionando con el Stuff+ provisional y la web app lo indica en el encabezado.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
import requests

log = logging.getLogger("traductor")


def cargar_env(ruta: Path) -> None:
    """Lee un .env (líneas CLAVE=valor). Las variables que ya existan en el sistema ganan."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


class FuenteNoDisponible(RuntimeError):
    """Un API no respondió o no tiene lo que se le pidió."""


@dataclass
class Fuentes:
    """Lo que el traductor necesita de los dos APIs. Las pruebas la sustituyen por una versión falsa."""

    cache_dir: Path
    timeout: int = 300
    estado: dict = field(default_factory=dict)       # qué se usó en la última carga (se muestra en /api/meta)

    def __post_init__(self):
        self.api1_url = os.getenv("API1_URL", "http://localhost:8000").rstrip("/")
        self.api2_url = os.getenv("API2_URL", "http://localhost:8001").rstrip("/")
        self.api1_key = os.getenv("API1_KEY", "")
        self.api2_key = os.getenv("API2_KEY", "")

    # ---------------------------------------------------------------------------------------- utilidades
    def _descargar(self, url: str, llave: str, ruta: str, **params) -> pl.DataFrame:
        if not llave:
            raise FuenteNoDisponible(f"Falta la llave para {url} en backend/.env")
        try:
            r = requests.get(f"{url}{ruta}", params={**params, "formato": "parquet"}, timeout=self.timeout,
                             headers={"X-API-Key": llave, "Accept-Encoding": "identity"})
        except requests.RequestException as e:
            raise FuenteNoDisponible(f"{url} no responde ({type(e).__name__}). ¿Está prendido?") from e
        if r.status_code != 200:
            detalle = r.json().get("detail") if "json" in r.headers.get("content-type", "") else r.text[:200]
            raise FuenteNoDisponible(f"{url}{ruta} respondió {r.status_code}: {detalle}")
        return pl.read_parquet(io.BytesIO(r.content))

    # ---------------------------------------------------------------------------------------- API 1
    def pitcheos(self) -> pl.DataFrame:
        """Todo el dataset del API 1. Guarda una copia local para poder arrancar aunque el API 1 esté apagado."""
        copia = self.cache_dir / "pitcheos_api1.parquet"
        try:
            df = self._descargar(self.api1_url, self.api1_key, "/pitcheos/descargar")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            df.write_parquet(copia)
            self.estado["pitcheos"] = "api1"
            log.info("API 1: %s pitcheos", f"{df.height:,}")
            return df
        except FuenteNoDisponible as e:
            if not copia.exists():
                raise FuenteNoDisponible(f"{e} Y no hay copia guardada en {copia}.") from e
            log.warning("%s Uso la copia guardada (%s).", e, copia.name)
            self.estado["pitcheos"] = "copia_local"
            return pl.read_parquet(copia)

    # ---------------------------------------------------------------------------------------- API 2
    def tabla_api2(self, nombre: str) -> pl.DataFrame | None:
        """Una tabla de resultados del API 2, o None si el API 2 no responde o la tabla no existe todavía."""
        try:
            df = self._descargar(self.api2_url, self.api2_key, f"/resultados/{nombre}/descargar")
            self.estado[nombre] = "api2"
            log.info("API 2: tabla '%s' (%s renglones)", nombre, f"{df.height:,}")
            return df
        except FuenteNoDisponible as e:
            self.estado[nombre] = "no_disponible"
            log.warning("API 2 sin '%s': %s", nombre, e)
            return None

    def metadatos_api2(self) -> dict:
        """Quién subió cada tabla, su versión y fecha (para mostrarlo en Metodología)."""
        if not self.api2_key:
            return {}
        try:
            r = requests.get(f"{self.api2_url}/resultados", headers={"X-API-Key": self.api2_key}, timeout=30)
            return r.json() if r.status_code == 200 else {}
        except requests.RequestException:
            return {}
