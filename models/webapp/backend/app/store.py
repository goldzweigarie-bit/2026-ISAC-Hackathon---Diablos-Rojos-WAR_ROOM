"""In-memory data store: loads the processed tables and precomputes projected Stuff+ at every park."""
from __future__ import annotations

import json
import os
import unicodedata
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .model import FEATURE_COLUMNS, load_model, stuff_plus
from .physics import air_density, at_density, flight, movement_inches

DATA_DIR = Path(os.environ.get("STUFFPLUS_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
SEA_LEVEL_ID = "sea-level"


def norm_text(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.load()

    # ------------------------------------------------------------------------------------------ loading
    def load(self) -> None:
        ref = self.data_dir / "reference"
        proc = self.data_dir / "processed"
        if not (proc / "arsenal.parquet").exists():
            raise RuntimeError("No processed data. Run scripts/ingest.py first (see README).")
        self.config = _read_json(ref / "app_config.json")
        self.stadiums = _read_json(ref / "stadiums.json")["stadiums"]
        self.stadium_by_id = {s["id"]: s for s in self.stadiums}
        self.stadium_by_team = {s["team_code"]: s for s in self.stadiums}
        self.meta = _read_json(proc / "ingest_meta.json", {})
        self.altitude_study = _read_json(proc / "altitude_study.json", {})
        self.validation = _read_json(proc / "validation_metrics.json")
        self.arsenal = pd.read_parquet(proc / "arsenal.parquet")
        self.pitchers = pd.read_parquet(proc / "pitchers.parquet")
        self.appearances = pd.read_parquet(proc / "appearances.parquet") if (proc / "appearances.parquet").exists() else None
        self.team_hand = pd.read_parquet(proc / "team_handedness.parquet") if (proc / "team_handedness.parquet").exists() else None
        self.rosters = pd.read_parquet(proc / "rosters.parquet") if (proc / "rosters.parquet").exists() else None
        self.schedules = {}
        for f in sorted((self.data_dir / "schedule").glob("*.csv")):
            sched = pd.read_csv(f, dtype={"stadium_id": str})
            if "stadium_id" not in sched:
                sched["stadium_id"] = ""
            sched["stadium_id"] = [s if isinstance(s, str) and s else self.stadium_by_team[h]["id"]
                                   for s, h in zip(sched["stadium_id"].fillna(""), sched["home_code"])]
            self.schedules[int(f.stem)] = sched
        self.model = load_model(proc)
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
        proj["raw"] = self.model.predict(proj[FEATURE_COLUMNS])
        groups = (proj["season"].astype(str) + "|" + proj["stadium_id"]).to_numpy()
        proj["stuff_plus"] = stuff_plus(proj["raw"].to_numpy(), proj["n"].to_numpy(dtype=float), groups)
        parks_only = proj[proj.stadium_id != SEA_LEVEL_ID]
        neutral = parks_only.groupby(["season", "pitcher_id", "pitch_type"])["stuff_plus"].mean().rename("stuff_neutral")
        proj = proj.merge(neutral.reset_index(), on=["season", "pitcher_id", "pitch_type"], how="left")
        self.proj = proj
        w = proj.assign(wsp=proj["stuff_plus"] * proj["n"], wn=proj["n"])
        pp = w.groupby(["season", "stadium_id", "pitcher_id"]).agg(wsp=("wsp", "sum"), n=("wn", "sum")).reset_index()
        pp["stuff_plus"] = pp["wsp"] / pp["n"]
        pp = pp.drop(columns="wsp")
        pn = pp[pp.stadium_id != SEA_LEVEL_ID].groupby(["season", "pitcher_id"])["stuff_plus"].mean().rename("stuff_neutral")
        self.pitcher_park = pp.merge(pn.reset_index(), on=["season", "pitcher_id"], how="left")

    def _build_universe(self) -> None:
        """Latest season per pitcher plus current status (team code or 'FA')."""
        p = self.pitchers.sort_values("season").drop_duplicates("pitcher_id", keep="last").copy()
        status = p["team_code"].where(p["season"] == self.current_season, "FA")
        if self.rosters is not None and len(self.rosters):
            r = self.rosters[self.rosters.season == self.rosters.season.max()].drop_duplicates("pitcher_id", keep="last")
            rmap = dict(zip(r.pitcher_id.astype(str), r.team_code))
            status = pd.Series([rmap.get(pid, s) for pid, s in zip(p.pitcher_id, status)], index=p.index)
        p["status"] = status.fillna("FA")
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
