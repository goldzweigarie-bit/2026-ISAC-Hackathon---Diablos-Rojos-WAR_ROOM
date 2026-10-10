"""Memoria del traductor: al arrancar pide los datos a los dos APIs, arma las tablas y precalcula todo.

    API 1 (pitcheos) ─→ preparar.py ─→ arsenal / pitchers ─┐
                                                           ├─→ proj: cada pitcheo en cada uno de los 20 parques
    API 2 (Stuff+ por nivel de altitud) ───────────────────┘        (física de physics.py + Stuff+ del modelo)

Si el API 2 todavía no tiene la tabla de Stuff+, se usa el Stuff+ provisional de model.py y la web app lo avisa.
"""
from __future__ import annotations

import json
import logging
import os
import unicodedata
import re
from pathlib import Path

import numpy as np
import polars as pl

from .fuentes import Fuentes, cargar_env
from .model import FEATURE_COLUMNS, PlaceholderStuffModel, stuff_plus
from .physics import air_density, at_density, flight, movement_inches
from .preparar import preparar

BACKEND_DIR = Path(__file__).resolve().parents[1]
cargar_env(BACKEND_DIR / ".env")
DATA_DIR = Path(os.environ.get("STUFFPLUS_DATA_DIR", BACKEND_DIR / "data"))
SEA_LEVEL_ID = "sea-level"
log = logging.getLogger("traductor")


def norm_text(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def serie(nombre: str, valores) -> pl.Series:
    """Arreglo de numpy → columna de Polars; los NaN quedan como vacíos (null), igual que en el resto de la app."""
    return pl.Series(nombre, np.asarray(valores, dtype=float), nan_to_null=True)


class Store:
    def __init__(self, data_dir: Path = DATA_DIR, fuentes: Fuentes | None = None):
        self.data_dir = Path(data_dir)
        self.fuentes = fuentes or Fuentes(cache_dir=self.data_dir / "cache")
        self.load()

    # ------------------------------------------------------------------------------------------ loading
    def load(self) -> None:
        ref = self.data_dir / "reference"
        self.config = _read_json(ref / "app_config.json")
        self.stadiums = _read_json(ref / "stadiums.json")["stadiums"]
        self.stadium_by_id = {s["id"]: s for s in self.stadiums}
        self.stadium_by_team = {s["team_code"]: s for s in self.stadiums}

        # 1) API 1: pitcheos → tablas físicas
        t = preparar(self.fuentes.pitcheos(), self.data_dir)
        for aviso in t["log"]:
            log.warning(aviso)
        self.meta = t["meta"]
        self.altitude_study = t["altitude_study"]
        self.arsenal: pl.DataFrame = t["arsenal"]
        self.pitchers: pl.DataFrame = t["pitchers"]
        self.appearances: pl.DataFrame | None = t["appearances"]
        self.team_hand: pl.DataFrame | None = t["team_hand"]
        self.rosters: pl.DataFrame | None = t["rosters"]

        # 2) API 2: Stuff+ del modelo y métricas de validación (si ya existen)
        cfg = self.config["api2"]
        self.stuff_table = self.fuentes.tabla_api2(cfg["tabla_stuff"])
        self.validation = self._validation(self.fuentes.tabla_api2(cfg["tabla_validacion"]))
        self.api2_meta = self.fuentes.metadatos_api2()
        self.model = self._model_info()
        self.levels_interpolated: list[str] = []
        self.schedules: dict[int, pl.DataFrame] = {}
        for f in sorted((self.data_dir / "schedule").glob("*.csv")):
            sched = pl.read_csv(f, schema_overrides={"stadium_id": pl.String, "date": pl.String,
                                                     "status": pl.String})
            if "stadium_id" not in sched.columns:
                sched = sched.with_columns(stadium_id=pl.lit(None, dtype=pl.String))
            sched = sched.with_columns(stadium_id=pl.Series(
                [s if s else self.stadium_by_team[h]["id"] for s, h in zip(sched["stadium_id"], sched["home_code"])]))
            self.schedules[int(f.stem)] = sched
        self.rho_ref = float(self.meta.get("rho_ref") or air_density(0, 25))
        self.seasons = sorted(self.arsenal["season"].unique().to_list())
        self.current_season = max(self.seasons)
        self._build_projections()
        self._build_universe()

    # --------------------------------------------------------------------------------- physics features
    def park_rho(self, stadium_id: str) -> float:
        if stadium_id == SEA_LEVEL_ID:
            return self.rho_ref
        s = self.stadium_by_id[stadium_id]
        return float(air_density(s["altitude_m"], s["typical_temp_c"]))

    def features_at(self, ars: pl.DataFrame, rho: float) -> pl.DataFrame:
        """Cada pitcheo del arsenal lanzado con la misma salida en un aire de densidad `rho`."""
        a = {c: ars[c].to_numpy() for c in ("ax_mag_sl", "ay_drag_sl", "az_mag_sl", "x0", "y0", "z0",
                                             "vx0", "vy0", "vz0", "arm_sign")}
        ax, ay, az = at_density(a["ax_mag_sl"], a["ay_drag_sl"], a["az_mag_sl"], rho, self.rho_ref)
        f = flight(a["x0"], a["y0"], a["z0"], a["vx0"], a["vy0"], a["vz0"], ax, ay, az)
        k = rho / self.rho_ref
        hb, ivb = movement_inches(a["ax_mag_sl"] * k, a["az_mag_sl"] * k, f["t"])
        out = ars.select("season", "pitcher_id", "pitch_type", "n", "usage", "rel_speed", "spin_rate", "spin_axis",
                         "extension", "rel_height", "rel_side", "arm_sign").with_columns(
            serie("plate_speed", f["plate_speed"]), serie("vaa", f["vaa"]), serie("t", f["t"]),
            serie("ivb", ivb), serie("hb", hb), serie("hb_arm", hb * a["arm_sign"]),
            pl.lit(rho / self.rho_ref).alias("rho_ratio"))
        # recta principal de cada pitcher-temporada (en el mismo parque): la más usada; si no tiene, la más rápida
        pk = ["season", "pitcher_id"]
        fbs = (out.filter(pl.col("pitch_type").is_in(["Four-Seam", "Sinker"]))
                  .sort("n", descending=True, maintain_order=True).unique(pk, keep="first", maintain_order=True))
        fallback = (out.sort("rel_speed", descending=True, nulls_last=True, maintain_order=True)
                       .unique(pk, keep="first", maintain_order=True))
        fb = (pl.concat([fbs, fallback]).unique(pk, keep="first", maintain_order=True)
                .select(pk + [pl.col("rel_speed").alias("fb_rel_speed"), pl.col("ivb").alias("fb_ivb"),
                              pl.col("hb_arm").alias("fb_hb_arm")]))
        return (out.join(fb, on=pk, how="left", maintain_order="left")
                   .join(self.pitchers.select(pk + ["throws"]), on=pk, how="left", maintain_order="left"))

    def _build_projections(self) -> None:
        min_n = self.config.get("min_pitches_pitch_type", 20)
        ars = self.arsenal.filter(pl.col("n") >= min_n)
        frames = [self.features_at(ars, self.park_rho(sid)).with_columns(stadium_id=pl.lit(sid))
                  for sid in [SEA_LEVEL_ID] + [s["id"] for s in self.stadiums]]
        proj = pl.concat(frames)
        if self.stuff_table is not None:
            proj = proj.with_columns(serie("stuff_plus", self._stuff_from_api2(proj)))
        else:
            raw = PlaceholderStuffModel().predict(proj.select(FEATURE_COLUMNS))
            groups = (proj["season"].cast(pl.String) + "|" + proj["stadium_id"]).to_numpy()
            proj = proj.with_columns(serie("raw", raw),
                                     serie("stuff_plus", stuff_plus(raw, proj["n"].to_numpy().astype(float), groups)))
        keys = ["season", "pitcher_id", "pitch_type"]
        neutral = (proj.filter(pl.col("stadium_id") != SEA_LEVEL_ID).group_by(keys)
                       .agg(stuff_neutral=pl.col("stuff_plus").mean()))
        self.proj = proj.join(neutral, on=keys, how="left", maintain_order="left")
        # Stuff+ de cada pitcher en cada parque = promedio de sus pitcheos ponderado por uso
        pp = (self.proj.filter(pl.col("stuff_plus").is_not_null())
                       .group_by(["season", "stadium_id", "pitcher_id"])
                       .agg(wsp=(pl.col("stuff_plus") * pl.col("n")).sum(), n=pl.col("n").sum())
                       .with_columns(stuff_plus=pl.col("wsp") / pl.col("n")).drop("wsp")
                       .sort(["season", "stadium_id", "pitcher_id"]))
        pn = (pp.filter(pl.col("stadium_id") != SEA_LEVEL_ID).group_by(["season", "pitcher_id"])
                .agg(stuff_neutral=pl.col("stuff_plus").mean()))
        self.pitcher_park = pp.join(pn, on=["season", "pitcher_id"], how="left", maintain_order="left")

    # ------------------------------------------------------------------------------------- Stuff+ (API 2)
    def altitude_level(self, stadium_id: str) -> str:
        """Nivel de altitud de un parque, con los mismos nombres que altitude_category del dataset."""
        if stadium_id == SEA_LEVEL_ID:
            return "No Altitude"
        s = self.stadium_by_id[stadium_id]
        if s.get("altitude_category"):                       # un parque puede fijar su nivel a mano
            return s["altitude_category"]
        for nivel in sorted(self.config["niveles_altitud"], key=lambda n: -n["desde_m"]):
            if s["altitude_m"] >= nivel["desde_m"]:
                return nivel["nivel"]
        return "No Altitude"

    def _stuff_from_api2(self, proj: pl.DataFrame) -> np.ndarray:
        """Stuff+ de cada pitcher × tipo en cada parque = la columna del nivel de altitud de ese parque.

        Si la tabla no trae la columna de un nivel (p. ej. todavía no hay stuff_plus_media), ese nivel se
        interpola entre nivel del mar y CDMX según la densidad del aire del parque."""
        cfg = self.config["api2"]["columnas"]
        keys = ["season", "pitcher_id", "pitch_type"]
        st = self.stuff_table.rename({cfg["pitcher"]: "pitcher_id", cfg["temporada"]: "season",
                                      cfg["tipo"]: "pitch_type"})
        cols = {nivel: c for nivel, c in cfg["stuff_por_nivel"].items() if c in st.columns}
        if "No Altitude" not in cols:
            raise RuntimeError(f"La tabla de Stuff+ del API 2 no trae {cfg['stuff_por_nivel']['No Altitude']}. "
                               f"Columnas recibidas: {self.stuff_table.columns}")
        st = (st.with_columns(pl.col("pitcher_id").cast(pl.String),
                              pl.col("season").cast(pl.Float64, strict=False).cast(pl.Int64, strict=False),
                              pl.col("pitch_type").cast(pl.String).replace({"Sweeper": "Slider"}),
                              *[pl.col(c).cast(pl.Float64, strict=False).fill_nan(None) for c in cols.values()])
                .group_by(keys).agg([pl.col(c).mean() for c in cols.values()]))
        cruce = proj.select(keys).join(st, on=keys, how="left", maintain_order="left")
        vals = {nivel: cruce[c].to_numpy().astype(float) for nivel, c in cols.items()}
        out = np.full(proj.height, np.nan)
        rho_cdmx = self.park_rho(self.config["home_stadium_id"])
        self.levels_interpolated = []
        sids = proj["stadium_id"].to_numpy()
        for sid in dict.fromkeys(sids):
            m = sids == sid
            nivel = self.altitude_level(sid)
            if nivel in vals:
                out[m] = vals[nivel][m]
            elif "Extreme Altitude" in vals:                 # interpolar por densidad
                w = (self.rho_ref - self.park_rho(sid)) / (self.rho_ref - rho_cdmx)
                out[m] = (1 - w) * vals["No Altitude"][m] + w * vals["Extreme Altitude"][m]
                if nivel not in self.levels_interpolated:
                    self.levels_interpolated.append(nivel)
            else:
                out[m] = vals["No Altitude"][m]
        return out

    def _validation(self, tabla: pl.DataFrame | None):
        """Tabla 'validacion' del API 2 (columnas: nombre, valor y opcionalmente split, tipo) → página Metodología."""
        if tabla is None or not {"nombre", "valor"} <= set(tabla.columns):
            return None
        metrics, subs = [], []
        for r in tabla.iter_rows(named=True):
            if r.get("tipo") == "submodelo":
                subs.append({"name": r["nombre"], "target": r.get("objetivo") or "", "metric": r.get("metrica") or "",
                             "value": r["valor"]})
            else:
                metrics.append({"name": r["nombre"], "value": r["valor"], "split": r.get("split")})
        return {"metrics": metrics, "submodels": subs, "notes": "Métricas subidas por el modelo al API 2."}

    def _model_info(self) -> dict:
        """Qué Stuff+ está sirviendo la app: el del modelo (API 2) o el provisional."""
        if self.stuff_table is None:
            return {"name": "placeholder", "source": "provisional"}
        m = self.api2_meta.get(self.config["api2"]["tabla_stuff"], {})
        version = m.get("version") or "sin versión"
        return {"name": f"{m.get('modelo', 'stuff_plus')} {version}", "source": "api2", "uploaded": m.get("subido")}

    def _build_universe(self) -> None:
        """La última temporada de cada pitcher y su estatus actual (código de equipo, 'FA' o '?')."""
        p = (self.pitchers.sort(["season", "pitcher_id"]).unique("pitcher_id", keep="last", maintain_order=True)
                 .with_columns(status=pl.when(pl.col("season") == self.current_season)
                               .then(pl.col("team_code")).otherwise(pl.lit("FA"))))
        if self.rosters is not None and self.rosters.height:
            r = (self.rosters.filter(pl.col("season") == self.rosters["season"].max())
                     .unique("pitcher_id", keep="last", maintain_order=True)
                     .select("pitcher_id", pl.col("team_code").alias("_roster_team")))
            p = (p.join(r, on="pitcher_id", how="left", maintain_order="left")
                  .with_columns(status=pl.coalesce("_roster_team", "status")).drop("_roster_team"))
        p = p.with_columns(pl.col("status").fill_null("FA"))
        if not self.meta.get("capabilities", {}).get("has_teams") and (self.rosters is None or not self.rosters.height):
            p = p.with_columns(status=pl.lit("?"))   # datos anonimizados: no se sabe en qué equipo está nadie
        self.universe = p.with_columns(
            _pid_norm=pl.Series([norm_text(x) for x in p["pitcher_id"]]),
            _name_norm=pl.Series([norm_text(x) for x in p["name"]]))
        self.status_by_id: dict[str, str] = dict(zip(p["pitcher_id"], p["status"]))

    # ------------------------------------------------------------------------------------------- lookups
    def team_name(self, code):
        s = self.stadium_by_team.get(code)
        return s["team_name"] if s else None

    def pitcher_row(self, pid: str, season: int | None = None) -> dict | None:
        rows = self.pitchers.filter(pl.col("pitcher_id") == pid)
        if rows.is_empty():
            return None
        if season is not None and (rows["season"] == season).any():
            return rows.filter(pl.col("season") == season).row(0, named=True)
        return rows.sort("season").row(-1, named=True)

    def search(self, q: str, limit: int = 8):
        nq = norm_text(q)
        if not nq:
            return {"pitchers": [], "stadiums": []}
        stadiums = []
        for s in self.stadiums:
            hay = [s["venue_name"], s["city"], s["team_name"], s["team_code"], *s.get("aliases", [])]
            if any(nq in norm_text(h) for h in hay):
                stadiums.append({"id": s["id"], "venue_name": s["venue_name"], "city": s["city"],
                                 "team_name": s["team_name"], "altitude_m": s["altitude_m"]})
        hits = self.universe.filter(pl.col("_pid_norm").str.contains(nq, literal=True)
                                    | pl.col("_name_norm").str.contains(nq, literal=True)).head(limit)
        pitchers = [{"pitcher_id": r["pitcher_id"], "name": r["name"], "status": r["status"], "throws": r["throws"],
                     "role": r["role"], "season": int(r["season"])} for r in hits.iter_rows(named=True)]
        return {"pitchers": pitchers, "stadiums": stadiums[:limit]}
