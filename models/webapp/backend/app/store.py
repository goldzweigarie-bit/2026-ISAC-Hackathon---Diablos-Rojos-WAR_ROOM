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
import pandas as pd

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
        self.arsenal = t["arsenal"]
        self.pitchers = t["pitchers"]
        self.appearances = t["appearances"]
        self.team_hand = t["team_hand"]
        self.rosters = t["rosters"]

        # 2) API 2: Stuff+ del modelo y métricas de validación (si ya existen)
        cfg = self.config["api2"]
        self.stuff_table = self.fuentes.tabla_api2(cfg["tabla_stuff"])
        self.validation = self._validation(self.fuentes.tabla_api2(cfg["tabla_validacion"]))
        self.api2_meta = self.fuentes.metadatos_api2()
        self.model = self._model_info()
        self.levels_interpolated: list[str] = []
        self.schedules = {}
        for f in sorted((self.data_dir / "schedule").glob("*.csv")):
            sched = pd.read_csv(f, dtype={"stadium_id": str})
            if "stadium_id" not in sched:
                sched["stadium_id"] = ""
            sched["stadium_id"] = [s if isinstance(s, str) and s else self.stadium_by_team[h]["id"]
                                   for s, h in zip(sched["stadium_id"].fillna(""), sched["home_code"])]
            self.schedules[int(f.stem)] = sched
        self.rho_ref = float(self.meta.get("rho_ref") or air_density(0, 25))
        self.seasons = sorted(int(s) for s in self.arsenal["season"].unique())
        self.current_season = max(self.seasons)
        self._build_projections()
        self._build_universe()

    # --------------------------------------------------------------------------------- physics features
    def park_rho(self, stadium_id: str) -> float:
        if stadium_id == SEA_LEVEL_ID:
            return self.rho_ref
        s = self.stadium_by_id[stadium_id]
        return float(air_density(s["altitude_m"], s["typical_temp_c"]))

    def features_at(self, ars: pd.DataFrame, rho: float) -> pd.DataFrame:
        ax, ay, az = at_density(ars["ax_mag_sl"], ars["ay_drag_sl"], ars["az_mag_sl"], rho, self.rho_ref)
        f = flight(ars["x0"], ars["y0"], ars["z0"], ars["vx0"], ars["vy0"], ars["vz0"], ax, ay, az)
        k = rho / self.rho_ref
        hb, ivb = movement_inches(ars["ax_mag_sl"] * k, ars["az_mag_sl"] * k, f["t"])
        out = ars[["season", "pitcher_id", "pitch_type", "n", "usage", "rel_speed", "spin_rate", "spin_axis",
                   "extension", "rel_height", "rel_side", "arm_sign"]].copy()
        out["plate_speed"] = f["plate_speed"]
        out["vaa"] = f["vaa"]
        out["t"] = f["t"]
        out["ivb"] = ivb
        out["hb"] = hb
        out["hb_arm"] = hb * ars["arm_sign"].to_numpy()
        out["rho_ratio"] = rho / self.rho_ref
        # primary fastball reference per pitcher-season (at the same park)
        fbs = out[out.pitch_type.isin(["Four-Seam", "Sinker"])].sort_values("n", ascending=False)
        fbs = fbs.drop_duplicates(["season", "pitcher_id"])
        fallback = out.sort_values("rel_speed", ascending=False).drop_duplicates(["season", "pitcher_id"])
        fb = pd.concat([fbs, fallback]).drop_duplicates(["season", "pitcher_id"])
        fb = fb[["season", "pitcher_id", "rel_speed", "ivb", "hb_arm"]].rename(
            columns={"rel_speed": "fb_rel_speed", "ivb": "fb_ivb", "hb_arm": "fb_hb_arm"})
        out = out.merge(fb, on=["season", "pitcher_id"], how="left")
        out = out.merge(self.pitchers[["season", "pitcher_id", "throws"]], on=["season", "pitcher_id"], how="left")
        return out

    def _build_projections(self) -> None:
        min_n = self.config.get("min_pitches_pitch_type", 20)
        ars = self.arsenal[self.arsenal["n"] >= min_n].reset_index(drop=True)
        frames = []
        for sid in [SEA_LEVEL_ID] + [s["id"] for s in self.stadiums]:
            feats = self.features_at(ars, self.park_rho(sid))
            feats["stadium_id"] = sid
            frames.append(feats)
        proj = pd.concat(frames, ignore_index=True)
        if self.stuff_table is not None:
            proj["stuff_plus"] = self._stuff_from_api2(proj)
        else:
            proj["raw"] = PlaceholderStuffModel().predict(proj[FEATURE_COLUMNS])
            groups = (proj["season"].astype(str) + "|" + proj["stadium_id"]).to_numpy()
            proj["stuff_plus"] = stuff_plus(proj["raw"].to_numpy(), proj["n"].to_numpy(dtype=float), groups)
        parks_only = proj[proj.stadium_id != SEA_LEVEL_ID]
        neutral = parks_only.groupby(["season", "pitcher_id", "pitch_type"])["stuff_plus"].mean().rename("stuff_neutral")
        proj = proj.merge(neutral.reset_index(), on=["season", "pitcher_id", "pitch_type"], how="left")
        self.proj = proj
        w = proj.dropna(subset=["stuff_plus"]).assign(wsp=proj["stuff_plus"] * proj["n"], wn=proj["n"])
        pp = w.groupby(["season", "stadium_id", "pitcher_id"]).agg(wsp=("wsp", "sum"), n=("wn", "sum")).reset_index()
        pp["stuff_plus"] = pp["wsp"] / pp["n"]
        pp = pp.drop(columns="wsp")
        pn = pp[pp.stadium_id != SEA_LEVEL_ID].groupby(["season", "pitcher_id"])["stuff_plus"].mean().rename("stuff_neutral")
        self.pitcher_park = pp.merge(pn.reset_index(), on=["season", "pitcher_id"], how="left")

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

    def _stuff_from_api2(self, proj: pd.DataFrame) -> np.ndarray:
        """Stuff+ de cada pitcher × tipo en cada parque = la columna del nivel de altitud de ese parque.

        Si la tabla no trae la columna de un nivel (p. ej. todavía no hay stuff_plus_media), ese nivel se
        interpola entre nivel del mar y CDMX según la densidad del aire del parque."""
        cfg = self.config["api2"]["columnas"]
        st = self.stuff_table.rename(columns={cfg["pitcher"]: "pitcher_id", cfg["temporada"]: "season",
                                              cfg["tipo"]: "pitch_type"})
        st["pitcher_id"] = st["pitcher_id"].astype(str)
        st["season"] = pd.to_numeric(st["season"], errors="coerce")
        st["pitch_type"] = st["pitch_type"].astype(str).replace({"Sweeper": "Slider"})
        cols = {nivel: c for nivel, c in cfg["stuff_por_nivel"].items() if c in st.columns}
        if "No Altitude" not in cols:
            raise RuntimeError(f"La tabla de Stuff+ del API 2 no trae {cfg['stuff_por_nivel']['No Altitude']}. "
                               f"Columnas recibidas: {list(self.stuff_table.columns)}")
        st = st.groupby(["season", "pitcher_id", "pitch_type"])[list(cols.values())].mean()
        key = pd.MultiIndex.from_frame(proj[["season", "pitcher_id", "pitch_type"]])
        vals = {nivel: st[c].reindex(key).to_numpy() for nivel, c in cols.items()}
        out = np.full(len(proj), np.nan)
        rho_cdmx = self.park_rho(self.config["home_stadium_id"])
        self.levels_interpolated = []
        for sid in proj["stadium_id"].unique():
            m = (proj["stadium_id"] == sid).to_numpy()
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

    def _validation(self, tabla: pd.DataFrame | None):
        """Tabla 'validacion' del API 2 (columnas: nombre, valor y opcionalmente split, tipo) → página Metodología."""
        if tabla is None or not {"nombre", "valor"} <= set(tabla.columns):
            return None
        tipo = tabla["tipo"] if "tipo" in tabla else pd.Series("metrica", index=tabla.index)
        metrics = [{"name": r.nombre, "value": r.valor, "split": getattr(r, "split", None)}
                   for r in tabla[tipo != "submodelo"].itertuples()]
        subs = [{"name": r.nombre, "target": getattr(r, "objetivo", ""), "metric": getattr(r, "metrica", ""),
                 "value": r.valor} for r in tabla[tipo == "submodelo"].itertuples()]
        return {"metrics": metrics, "submodels": subs, "notes": "Métricas subidas por el modelo al API 2."}

    def _model_info(self) -> dict:
        """Qué Stuff+ está sirviendo la app: el del modelo (API 2) o el provisional."""
        if self.stuff_table is None:
            return {"name": "placeholder", "source": "provisional"}
        m = self.api2_meta.get(self.config["api2"]["tabla_stuff"], {})
        version = m.get("version") or "sin versión"
        return {"name": f"{m.get('modelo', 'stuff_plus')} {version}", "source": "api2", "uploaded": m.get("subido")}

    def _build_universe(self) -> None:
        """Latest season per pitcher plus current status (team code or 'FA')."""
        p = self.pitchers.sort_values("season").drop_duplicates("pitcher_id", keep="last").copy()
        status = p["team_code"].where(p["season"] == self.current_season, "FA")
        if self.rosters is not None and len(self.rosters):
            r = self.rosters[self.rosters.season == self.rosters.season.max()].drop_duplicates("pitcher_id", keep="last")
            rmap = dict(zip(r.pitcher_id.astype(str), r.team_code))
            status = pd.Series([rmap.get(pid, s) for pid, s in zip(p.pitcher_id, status)], index=p.index)
        p["status"] = status.fillna("FA")
        if not self.meta.get("capabilities", {}).get("has_teams") and (self.rosters is None or not len(self.rosters)):
            p["status"] = "?"          # datos anonimizados: no se sabe en qué equipo está nadie
        self.universe = p.set_index("pitcher_id")

    # ------------------------------------------------------------------------------------------- lookups
    def team_name(self, code):
        s = self.stadium_by_team.get(code)
        return s["team_name"] if s else None

    def pitcher_row(self, pid: str, season: int | None = None):
        rows = self.pitchers[self.pitchers.pitcher_id == pid]
        if rows.empty:
            return None
        if season is not None and (rows.season == season).any():
            return rows[rows.season == season].iloc[0]
        return rows.sort_values("season").iloc[-1]

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
        u = self.universe.reset_index()
        mask = u["pitcher_id"].map(norm_text).str.contains(nq) | u["name"].astype(str).map(norm_text).str.contains(nq)
        hits = u[mask].head(limit)
        pitchers = [{"pitcher_id": r.pitcher_id, "name": r.name, "status": r.status, "throws": r.throws,
                     "role": r.role, "season": int(r.season)} for r in hits.itertuples()]
        return {"pitchers": pitchers, "stadiums": stadiums[:limit]}
