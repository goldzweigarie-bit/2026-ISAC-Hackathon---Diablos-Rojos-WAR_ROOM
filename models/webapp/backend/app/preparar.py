"""Convierte los pitcheos que entrega el API 1 en las tablas que usa la web app (todo en memoria).

Recibe el DataFrame tal cual lo da `/pitcheos/descargar` y devuelve:
  arsenal        un renglón por pitcher × temporada × tipo de pitcheo (promedios físicos, aceleraciones a nivel del mar)
  pitchers       un renglón por pitcher × temporada (mano, rol SP/RP, juegos, whiffs por lado del bateador)
  appearances    salidas por fecha (solo si los datos traen fechas: datos de la final)
  team_hand      % de bateadores zurdos por equipo (solo si traen equipos)
  rosters        data/rosters/<temporada>.csv, si existe (nombres, equipos y agentes libres)
  altitude_study la prueba empírica de que el Magnus escala con la densidad del aire
  meta           temporadas, columnas disponibles, densidad de referencia

Los nombres de columna se resuelven con data/reference/column_map.json. Con los datos anonimizados la app
funciona igual: lo que necesita fechas o equipos (cansancio del bullpen, agentes libres) avisa en vez de romperse.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from .physics import G_FT_S2, air_density, to_sea_level

PITCH_TYPES = ["Four-Seam", "Sinker", "Cutter", "Slider", "Curveball", "Changeup", "Splitter"]
PITCH_TYPE_ALIASES = {
    "fourseamfastball": "Four-Seam", "fastball": "Four-Seam", "four-seam": "Four-Seam", "fourseam": "Four-Seam",
    "ff": "Four-Seam", "sinker": "Sinker", "twoseamfastball": "Sinker", "si": "Sinker", "cutter": "Cutter",
    "fc": "Cutter", "slider": "Slider", "sweeper": "Slider", "sl": "Slider", "curveball": "Curveball",
    "cu": "Curveball", "knucklecurve": "Curveball", "changeup": "Changeup", "ch": "Changeup",
    "splitter": "Splitter", "fs": "Splitter", "split-finger": "Splitter",
}


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def canonicalize(raw: pd.DataFrame, column_map: dict) -> tuple[pd.DataFrame, dict]:
    out = pd.DataFrame(index=raw.index)
    used = {}
    for canon, candidates in column_map.items():
        if canon.startswith("_"):
            continue
        for c in candidates:
            if c in raw.columns:
                out[canon] = raw[c]
                used[canon] = c
                break
    return out, used


def to_flag(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.astype(float)
    mapped = s.map(lambda v: 1.0 if str(v).strip().lower() in {"1", "true", "t", "yes", "1.0"}
                   else (0.0 if str(v).strip().lower() in {"0", "false", "f", "no", "0.0"} else np.nan))
    return mapped


class DatosInvalidos(RuntimeError):
    """Los pitcheos no traen lo mínimo para armar la app (se explica qué falta)."""


def preparar(raw: pd.DataFrame, data_dir: Path) -> dict:
    ref = data_dir / "reference"
    config = json.loads((ref / "app_config.json").read_text(encoding="utf-8"))
    column_map = json.loads((ref / "column_map.json").read_text(encoding="utf-8"))
    stadiums = json.loads((ref / "stadiums.json").read_text(encoding="utf-8"))["stadiums"]

    df, used = canonicalize(raw, column_map)
    missing_core = [c for c in ("pitcher_id", "pitch_type", "rel_speed", "throws") if c not in df]
    if missing_core:
        raise DatosInvalidos(f"Faltan columnas {missing_core}. Agrega sus nombres a column_map.json.")
    capabilities = {
        "has_dates": "date" in df,
        "has_stadiums": "stadium" in df,
        "has_teams": "pitcher_team" in df,
        "has_names": "pitcher_name" in df,
        "has_trajectory": all(c in df for c in ("x0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0")),
    }
    log = []                                   # avisos para la terminal del traductor

    # --- types and cleaning --------------------------------------------------------------------------
    df["pitch_type"] = df["pitch_type"].map(lambda v: PITCH_TYPE_ALIASES.get(norm_text(v), v))
    df = df[df["pitch_type"].isin(PITCH_TYPES)].copy()
    df["throws"] = df["throws"].astype(str).str.strip().str.title().replace({"R": "Right", "L": "Left"})
    df = df[df["throws"].isin(["Right", "Left"])]
    numeric = ["rel_speed", "zone_speed", "spin_rate", "spin_axis", "rel_height", "rel_side", "extension", "ivb", "hb",
               "vaa", "zone_time", "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "exit_speed"]
    for c in numeric:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("is_swing", "is_whiff", "is_called_strike", "is_ball_in_play"):
        if c in df:
            df[c] = to_flag(df[c])
    if "is_swing" not in df and "pitch_call" in df:
        pc = df["pitch_call"].astype(str)
        df["is_swing"] = pc.isin(["StrikeSwinging", "FoulBall", "InPlay", "FoulBallNotFieldable", "FoulBallFieldable"]).astype(float)
        df["is_whiff"] = (pc == "StrikeSwinging").astype(float)
        df["is_called_strike"] = (pc == "StrikeCalled").astype(float)
    if capabilities["has_dates"]:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    if "season" in df:
        df["season"] = pd.to_numeric(df["season"], errors="coerce")
    elif capabilities["has_dates"]:
        df["season"] = pd.to_datetime(df["date"]).dt.year
    else:
        raise DatosInvalidos("Hace falta una columna de temporada (year) o de fecha.")
    df = df.dropna(subset=["season", "rel_speed"])
    df["season"] = df["season"].astype(int)
    df["pitcher_id"] = df["pitcher_id"].astype(str)

    # --- environment: stadium -> altitude/temp -> air density -----------------------------------------
    alias_to_id = {}
    for s in stadiums:
        for name in [s["venue_name"], s["id"], s["team_code"], *s.get("aliases", [])]:
            alias_to_id[norm_text(name)] = s["id"]
    st_by_id = {s["id"]: s for s in stadiums}
    if capabilities["has_stadiums"]:
        df["stadium_id"] = df["stadium"].map(lambda v: alias_to_id.get(norm_text(v)))
        unmatched = df.loc[df["stadium_id"].isna(), "stadium"].value_counts()
        if len(unmatched):
            log.append("Estadios sin reconocer (agrégalos a aliases en stadiums.json): "
                       + ", ".join(map(str, unmatched.head(20).index)))
    else:
        df["stadium_id"] = None
    alt = df["stadium_id"].map(lambda i: st_by_id[i]["altitude_m"] if i in st_by_id else np.nan)
    temp = df["stadium_id"].map(lambda i: st_by_id[i]["typical_temp_c"] if i in st_by_id else np.nan)
    if "altitude_category" in df:
        cat_map = {k: v for k, v in config["altitude_category_to_m"].items() if not k.startswith("_")}
        from_cat = df["altitude_category"].astype(str).map(cat_map)
        unknown = df.loc[alt.isna() & from_cat.isna(), "altitude_category"].value_counts()
        if len(unknown):
            log.append(f"altitude_category sin altitud en app_config.altitude_category_to_m: {unknown.to_dict()}")
        alt = alt.fillna(from_cat)
    df["altitude_m"] = alt.fillna(0.0)
    df["temp_c"] = temp.fillna(25.0)
    ref_env = config["sea_level_reference"]
    rho_ref = float(air_density(ref_env["altitude_m"], ref_env["temp_c"]))
    df["rho"] = air_density(df["altitude_m"], df["temp_c"])

    # --- arm-side convention, detected from fastballs ---------------------------------------------------
    fb = df[df.pitch_type.isin(["Four-Seam", "Sinker"])]
    sign_r = np.sign(fb.loc[fb.throws == "Right", "hb"].median()) if "hb" in df else -1.0
    sign_l = np.sign(fb.loc[fb.throws == "Left", "hb"].median()) if "hb" in df else 1.0
    sign_r = sign_r if sign_r != 0 and not np.isnan(sign_r) else -1.0
    sign_l = sign_l if sign_l != 0 and not np.isnan(sign_l) else -sign_r
    df["arm_sign"] = np.where(df.throws == "Right", sign_r, sign_l)

    # --- accelerations at the reference (sea-level) density --------------------------------------------
    if not capabilities["has_trajectory"]:
        # Rebuild an approximate 9-parameter description from release + movement.
        t = df.get("zone_time", pd.Series(0.40, index=df.index)).fillna(0.40)
        v = df["rel_speed"] * 5280 / 3600
        df["ax0"] = df["hb"] / 12 * 2 / t ** 2
        df["az0"] = df["ivb"] / 12 * 2 / t ** 2 - G_FT_S2
        df["ay0"] = 0.0045 * v ** 2 * 0.28 * df["rho"] / rho_ref
        df["x0"] = df.get("rel_side", 0.0)
        df["z0"] = df.get("rel_height", 6.0)
        df["vy0"] = -v
        df["vx0"] = 0.0
        df["vz0"] = -0.08 * v
    ax_sl, ay_sl, az_sl = to_sea_level(df["ax0"], df["ay0"], df["az0"], df["rho"], rho_ref)
    df["ax_mag_sl"], df["ay_drag_sl"], df["az_mag_sl"] = ax_sl, ay_sl, az_sl

    # --- tables --------------------------------------------------------------------------------------
    keys = ["season", "pitcher_id", "pitch_type"]
    agg = {
        "n": ("rel_speed", "size"), "rel_speed": ("rel_speed", "mean"), "spin_rate": ("spin_rate", "mean"),
        "extension": ("extension", "mean"), "rel_height": ("rel_height", "mean"), "rel_side": ("rel_side", "mean"),
        "x0": ("x0", "mean"), "z0": ("z0", "mean"), "vx0": ("vx0", "mean"), "vy0": ("vy0", "mean"),
        "vz0": ("vz0", "mean"), "ax_mag_sl": ("ax_mag_sl", "mean"), "ay_drag_sl": ("ay_drag_sl", "mean"),
        "az_mag_sl": ("az_mag_sl", "mean"), "arm_sign": ("arm_sign", "first"),
    }
    if "spin_axis" in df:
        agg["spin_axis"] = ("spin_axis", "median")
    if "is_swing" in df:
        agg["swings"] = ("is_swing", "sum")
        agg["whiffs"] = ("is_whiff", "sum")
    arsenal = df.groupby(keys).agg(**agg).reset_index()
    if "spin_axis" not in arsenal:
        arsenal["spin_axis"] = np.nan
    totals = arsenal.groupby(["season", "pitcher_id"])["n"].transform("sum")
    arsenal["usage"] = arsenal["n"] / totals
    arsenal["y0"] = 50.0

    # pitchers
    grp = df.groupby(["season", "pitcher_id"])
    pitchers = grp.agg(n_pitches=("rel_speed", "size"), throws=("throws", lambda s: s.mode().iat[0])).reset_index()
    if capabilities["has_names"]:
        pitchers = pitchers.merge(grp["pitcher_name"].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else None)
                                  .rename("name").reset_index(), on=["season", "pitcher_id"])
    else:
        pitchers["name"] = pitchers["pitcher_id"]
    if capabilities["has_teams"]:
        pitchers = pitchers.merge(grp["pitcher_team"].agg(lambda s: s.mode().iat[0] if s.notna().any() else None)
                                  .rename("team_code").reset_index(), on=["season", "pitcher_id"])
    else:
        pitchers["team_code"] = None
    if "game_id" in df:
        per_game = df.groupby(["season", "pitcher_id", "game_id"]).size().rename("p").reset_index()
        pg = per_game.groupby(["season", "pitcher_id"]).agg(games=("p", "size"), pitches_per_game=("p", "mean")).reset_index()
        pitchers = pitchers.merge(pg, on=["season", "pitcher_id"], how="left")
        pitchers["role"] = np.where(pitchers["pitches_per_game"] >= 50, "SP", "RP")
    else:
        pitchers["games"] = np.nan
        pitchers["pitches_per_game"] = np.nan
        pitchers["role"] = "RP"

    # rosters override name / team / role and define free agents
    roster_frames = [pd.read_csv(f) for f in sorted((data_dir / "rosters").glob("*.csv"))] if (data_dir / "rosters").exists() else []
    rosters = pd.concat(roster_frames, ignore_index=True) if roster_frames else pd.DataFrame(
        columns=["season", "pitcher_id", "name", "team_code", "role"])
    if len(rosters):
        rosters["pitcher_id"] = rosters["pitcher_id"].astype(str)
        r = rosters.drop_duplicates(["season", "pitcher_id"], keep="last").set_index(["season", "pitcher_id"])
        idx = pd.MultiIndex.from_frame(pitchers[["season", "pitcher_id"]])
        for col in ("name", "team_code", "role"):
            if col in r:
                override = r[col].reindex(idx).to_numpy()
                pitchers[col] = np.where(pd.notna(override), override, pitchers[col])

    # platoon whiff rates
    if "bats" in df and "is_swing" in df:
        plat = df.groupby(["season", "pitcher_id", "bats"]).agg(sw=("is_swing", "sum"), wh=("is_whiff", "sum")).reset_index()
        plat = plat.pivot_table(index=["season", "pitcher_id"], columns="bats", values=["sw", "wh"], fill_value=0)
        plat.columns = [f"{a}_{b[0].lower()}" for a, b in plat.columns]
        pitchers = pitchers.merge(plat.reset_index(), on=["season", "pitcher_id"], how="left")

    # appearances (workload) and team batting handedness
    appearances = team_hand = None
    if capabilities["has_dates"] and "game_id" in df:
        app_cols = ["season", "pitcher_id", "date", "game_id"] + (["stadium_id"] if capabilities["has_stadiums"] else [])
        appearances = df.groupby(app_cols, dropna=False).size().rename("pitches").reset_index()
        appearances["date"] = pd.to_datetime(appearances["date"])
    if "batter_team" in df and "bats" in df:
        team_hand = (df.assign(is_l=(df["bats"] == "Left").astype(float))
               .groupby(["season", "batter_team"])["is_l"].mean().rename("lhb_share").reset_index())

    # --- empirical altitude study: does spin-induced acceleration scale with air density? --------------
    df["a_spin_obs"] = np.hypot(df["ax0"], df["az0"] + G_FT_S2)
    df["a_drag_obs"] = df["ay0"]
    base = df.groupby(keys)[["a_spin_obs", "a_drag_obs", "rho"]].transform("mean")
    df["spin_ratio"] = df["a_spin_obs"] / base["a_spin_obs"]
    df["drag_ratio"] = df["a_drag_obs"] / base["a_drag_obs"]
    df["rho_ratio"] = df["rho"] / base["rho"]
    group_col = "stadium_id" if capabilities["has_stadiums"] and df["stadium_id"].notna().any() else "altitude_category"
    study_rows = []
    if group_col in df:
        for key, g in df.dropna(subset=[group_col]).groupby(group_col):
            study_rows.append({
                "group": key, "n": int(len(g)), "altitude_m": float(g["altitude_m"].mean()),
                "rho_ratio": float(g["rho_ratio"].mean()),
                "spin_accel_ratio": float(g["spin_ratio"].mean()),
                "spin_accel_se": float(g["spin_ratio"].std() / np.sqrt(len(g))),
                "drag_ratio": float(g["drag_ratio"].mean()),
            })
    slope = None
    if len(study_rows) >= 3:
        x = np.array([r["rho_ratio"] for r in study_rows]) - 1
        y = np.array([r["spin_accel_ratio"] for r in study_rows]) - 1
        w = np.array([r["n"] for r in study_rows], dtype=float)
        slope = float(np.sum(w * x * y) / np.sum(w * x * x)) if np.sum(w * x * x) > 0 else None
    altitude_study = {"grouped_by": group_col, "rows": study_rows, "elasticity_spin_vs_density": slope,
                      "note": "Elasticity 1.0 means Magnus acceleration scales one-for-one with air density, as physics predicts."}

    meta = {
        "seasons": sorted(int(s) for s in df["season"].unique()),
        "capabilities": capabilities,
        "columns_used": used,
        "rho_ref": rho_ref,
        "rows": int(len(df)),
        "arm_sign": {"Right": float(sign_r), "Left": float(sign_l)},
        "source_files": ["API 1 /pitcheos/descargar"],
        "synthetic": False,
    }
    return {"arsenal": arsenal, "pitchers": pitchers, "appearances": appearances, "team_hand": team_hand,
            "rosters": rosters if len(rosters) else None, "altitude_study": altitude_study, "meta": meta, "log": log}
