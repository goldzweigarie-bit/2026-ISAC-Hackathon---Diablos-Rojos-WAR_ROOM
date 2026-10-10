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
import polars as pl
import polars.selectors as cs

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


def canonicalize(raw: pl.DataFrame, column_map: dict) -> tuple[pl.DataFrame, dict]:
    """Renombra las columnas del API 1 a los nombres internos de la app (según column_map.json)."""
    used = {}
    for canon, candidates in column_map.items():
        if canon.startswith("_"):
            continue
        for c in candidates:
            if c in raw.columns:
                used[canon] = c
                break
    return raw.select([pl.col(c).alias(canon) for canon, c in used.items()]), used


def to_flag(col: str, dtype: pl.DataType) -> pl.Expr:
    """0/1, True/False, "yes"/"no"... → 1.0 / 0.0 (lo demás queda vacío)."""
    if dtype == pl.Boolean:
        return pl.col(col).cast(pl.Float64)
    texto = pl.col(col).cast(pl.String).str.strip_chars().str.to_lowercase()
    return (pl.when(texto.is_in(["1", "true", "t", "yes", "1.0"])).then(1.0)
            .when(texto.is_in(["0", "false", "f", "no", "0.0"])).then(0.0)
            .otherwise(None).alias(col))


def a_fecha(col: str, dtype: pl.DataType) -> pl.Expr:
    """Cualquier columna de fecha (texto, Date o Datetime) → Date. Lo que no se entienda queda vacío."""
    if dtype == pl.Date:
        return pl.col(col)
    if isinstance(dtype, pl.Datetime):
        return pl.col(col).dt.date()
    return pl.col(col).cast(pl.String).str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False)


def mapear(col: str, funcion, valores) -> pl.Expr:
    """Aplica una función de Python a cada valor DISTINTO de una columna (rápido: se calcula una vez por valor)."""
    tabla = {v: funcion(v) for v in valores if v is not None}
    return pl.col(col).cast(pl.String).replace_strict(tabla, default=None)


def moda(col: str) -> pl.Expr:
    """El valor más frecuente (en empate, el menor alfabéticamente), ignorando vacíos."""
    return pl.col(col).drop_nulls().mode().sort().first()


class DatosInvalidos(RuntimeError):
    """Los pitcheos no traen lo mínimo para armar la app (se explica qué falta)."""


def preparar(raw: pl.DataFrame, data_dir: Path) -> dict:
    ref = data_dir / "reference"
    config = json.loads((ref / "app_config.json").read_text(encoding="utf-8"))
    column_map = json.loads((ref / "column_map.json").read_text(encoding="utf-8"))
    stadiums = json.loads((ref / "stadiums.json").read_text(encoding="utf-8"))["stadiums"]

    df, used = canonicalize(raw, column_map)
    df = df.rechunk()                          # memoria contigua: si la tabla llegó en pedazos, todo es mucho más lento
    missing_core = [c for c in ("pitcher_id", "pitch_type", "rel_speed", "throws") if c not in df.columns]
    if missing_core:
        raise DatosInvalidos(f"Faltan columnas {missing_core}. Agrega sus nombres a column_map.json.")
    has = lambda c: c in df.columns  # noqa: E731
    capabilities = {
        "has_dates": has("date"),
        "has_stadiums": has("stadium"),
        "has_teams": has("pitcher_team"),
        "has_names": has("pitcher_name"),
        "has_trajectory": all(has(c) for c in ("x0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0")),
    }
    log = []                                   # avisos para la terminal del traductor

    # --- tipos y limpieza ----------------------------------------------------------------------------
    df = df.with_columns(cs.float().fill_nan(None))           # un NaN es un dato vacío (como null)
    tipos = df["pitch_type"].cast(pl.String).unique().to_list()
    df = (df.with_columns(mapear("pitch_type", lambda v: PITCH_TYPE_ALIASES.get(norm_text(v), v), tipos))
            .filter(pl.col("pitch_type").is_in(PITCH_TYPES)))
    df = (df.with_columns(pl.col("throws").cast(pl.String).str.strip_chars().str.to_titlecase()
                          .replace({"R": "Right", "L": "Left"}))
            .filter(pl.col("throws").is_in(["Right", "Left"])))
    numeric = ["rel_speed", "zone_speed", "spin_rate", "spin_axis", "rel_height", "rel_side", "extension", "ivb", "hb",
               "vaa", "zone_time", "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "exit_speed"]
    df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in numeric if has(c)])
    df = df.with_columns([to_flag(c, df.schema[c]) for c in ("is_swing", "is_whiff", "is_called_strike",
                                                             "is_ball_in_play") if has(c)])
    if not has("is_swing") and has("pitch_call"):
        pc = pl.col("pitch_call").cast(pl.String)
        df = df.with_columns(
            is_swing=pc.is_in(["StrikeSwinging", "FoulBall", "InPlay", "FoulBallNotFieldable", "FoulBallFieldable"])
            .fill_null(False).cast(pl.Float64),
            is_whiff=(pc == "StrikeSwinging").fill_null(False).cast(pl.Float64),
            is_called_strike=(pc == "StrikeCalled").fill_null(False).cast(pl.Float64))
    if capabilities["has_dates"]:
        df = df.with_columns(a_fecha("date", df.schema["date"]))
    if has("season"):
        df = df.with_columns(pl.col("season").cast(pl.Float64, strict=False))
    elif capabilities["has_dates"]:
        df = df.with_columns(season=pl.col("date").dt.year())
    else:
        raise DatosInvalidos("Hace falta una columna de temporada (year) o de fecha.")
    df = (df.filter(pl.col("season").is_not_null() & pl.col("rel_speed").is_not_null()
                    & pl.col("pitcher_id").is_not_null())
            .with_columns(pl.col("season").cast(pl.Int64), pl.col("pitcher_id").cast(pl.String)))
    for c in ("bats", "batter_team", "pitcher_team", "pitcher_name", "game_id", "altitude_category", "stadium"):
        if has(c) and df.schema[c] != pl.String:
            df = df.with_columns(pl.col(c).cast(pl.String))   # categóricas → texto

    # --- ambiente: estadio → altitud y temperatura → densidad del aire -------------------------------
    alias_to_id = {}
    for s in stadiums:
        for name in [s["venue_name"], s["id"], s["team_code"], *s.get("aliases", [])]:
            alias_to_id[norm_text(name)] = s["id"]
    st_by_id = {s["id"]: s for s in stadiums}
    if capabilities["has_stadiums"]:
        df = df.with_columns(mapear("stadium", lambda v: alias_to_id.get(norm_text(v)),
                                    df["stadium"].unique().to_list()).alias("stadium_id"))
        unmatched = (df.filter(pl.col("stadium_id").is_null() & pl.col("stadium").is_not_null())["stadium"]
                       .value_counts(sort=True).head(20))
        if unmatched.height:
            log.append("Estadios sin reconocer (agrégalos a aliases en stadiums.json): "
                       + ", ".join(map(str, unmatched["stadium"].to_list())))
    else:
        df = df.with_columns(stadium_id=pl.lit(None, dtype=pl.String))
    alt = pl.col("stadium_id").replace_strict({k: float(v["altitude_m"]) for k, v in st_by_id.items()},
                                              default=None, return_dtype=pl.Float64)
    temp = pl.col("stadium_id").replace_strict({k: float(v["typical_temp_c"]) for k, v in st_by_id.items()},
                                               default=None, return_dtype=pl.Float64)
    df = df.with_columns(_alt=alt, _temp=temp)
    if has("altitude_category"):
        cat_map = {k: float(v) for k, v in config["altitude_category_to_m"].items() if not k.startswith("_")}
        df = df.with_columns(_from_cat=pl.col("altitude_category").replace_strict(cat_map, default=None,
                                                                                    return_dtype=pl.Float64))
        unknown = (df.filter(pl.col("_alt").is_null() & pl.col("_from_cat").is_null())["altitude_category"]
                     .value_counts(sort=True))
        if unknown.height:
            log.append("altitude_category sin altitud en app_config.altitude_category_to_m: "
                       f"{dict(zip(unknown['altitude_category'].to_list(), unknown['count'].to_list()))}")
        df = df.with_columns(_alt=pl.coalesce("_alt", "_from_cat")).drop("_from_cat")
    df = (df.with_columns(altitude_m=pl.col("_alt").fill_null(0.0), temp_c=pl.col("_temp").fill_null(25.0))
            .drop("_alt", "_temp"))
    ref_env = config["sea_level_reference"]
    rho_ref = float(air_density(ref_env["altitude_m"], ref_env["temp_c"]))
    df = df.with_columns(rho=pl.Series(air_density(df["altitude_m"].to_numpy(), df["temp_c"].to_numpy())))

    # --- convención del lado del brazo, detectada con las rectas -------------------------------------
    fb = df.filter(pl.col("pitch_type").is_in(["Four-Seam", "Sinker"]))

    def signo(mano: str, defecto: float) -> float:
        if not has("hb"):
            return defecto
        med = fb.filter(pl.col("throws") == mano)["hb"].median()
        return float(np.sign(med)) if med is not None and np.sign(med) != 0 else defecto

    sign_r = signo("Right", -1.0)
    sign_l = signo("Left", -sign_r) if has("hb") else 1.0
    df = df.with_columns(arm_sign=pl.when(pl.col("throws") == "Right").then(sign_r).otherwise(sign_l))

    # --- aceleraciones a la densidad de referencia (nivel del mar) -----------------------------------
    if not capabilities["has_trajectory"]:
        # Reconstruye una descripción aproximada de 9 parámetros a partir de la salida y el movimiento.
        t = pl.col("zone_time").fill_null(0.40) if has("zone_time") else pl.lit(0.40)
        v = pl.col("rel_speed") * 5280 / 3600
        df = df.with_columns(
            ax0=pl.col("hb") / 12 * 2 / t ** 2, az0=pl.col("ivb") / 12 * 2 / t ** 2 - G_FT_S2,
            ay0=0.0045 * v ** 2 * 0.28 * pl.col("rho") / rho_ref,
            x0=pl.col("rel_side") if has("rel_side") else pl.lit(0.0),
            z0=pl.col("rel_height") if has("rel_height") else pl.lit(6.0),
            vy0=-v, vx0=pl.lit(0.0), vz0=-0.08 * v)
    ax_sl, ay_sl, az_sl = to_sea_level(df["ax0"].to_numpy(), df["ay0"].to_numpy(), df["az0"].to_numpy(),
                                       df["rho"].to_numpy(), rho_ref)
    df = df.with_columns(ax_mag_sl=pl.Series(ax_sl, nan_to_null=True), ay_drag_sl=pl.Series(ay_sl, nan_to_null=True),
                         az_mag_sl=pl.Series(az_sl, nan_to_null=True))
    has = lambda c: c in df.columns  # noqa: E731  (ya hay columnas nuevas)

    # --- tablas --------------------------------------------------------------------------------------
    keys = ["season", "pitcher_id", "pitch_type"]
    medias = ["rel_speed", "spin_rate", "extension", "rel_height", "rel_side", "x0", "z0", "vx0", "vy0", "vz0",
              "ax_mag_sl", "ay_drag_sl", "az_mag_sl"]
    agg = [pl.len().alias("n")] + [pl.col(c).mean() for c in medias if has(c)] + [pl.col("arm_sign").first()]
    agg += [pl.col("spin_axis").median()] if has("spin_axis") else [pl.lit(None, dtype=pl.Float64).alias("spin_axis")]
    if has("is_swing"):
        agg += [pl.col("is_swing").sum().alias("swings"), pl.col("is_whiff").sum().alias("whiffs")]
    arsenal = (df.group_by(keys).agg(agg).sort(keys)
                 .with_columns(usage=pl.col("n") / pl.col("n").sum().over(["season", "pitcher_id"]), y0=pl.lit(50.0)))
    for c in medias:                                           # columnas que no vinieron: vacías
        if c not in arsenal.columns:
            arsenal = arsenal.with_columns(pl.lit(None, dtype=pl.Float64).alias(c))

    # pitchers
    pk = ["season", "pitcher_id"]
    agg = [pl.len().alias("n_pitches"), moda("throws").alias("throws")]
    agg.append(pl.col("pitcher_name").drop_nulls().last().alias("name") if capabilities["has_names"]
               else pl.col("pitcher_id").first().alias("name"))
    agg.append(moda("pitcher_team").alias("team_code") if capabilities["has_teams"]
               else pl.lit(None, dtype=pl.String).alias("team_code"))
    pitchers = df.group_by(pk).agg(agg).sort(pk)
    if has("game_id"):
        pg = (df.filter(pl.col("game_id").is_not_null()).group_by(pk + ["game_id"]).len(name="p")
                .group_by(pk).agg(games=pl.len(), pitches_per_game=pl.col("p").mean()))
        pitchers = (pitchers.join(pg, on=pk, how="left", maintain_order="left")
                    .with_columns(role=pl.when(pl.col("pitches_per_game") >= 50).then(pl.lit("SP")).otherwise(pl.lit("RP"))))
    else:
        pitchers = pitchers.with_columns(games=pl.lit(None, dtype=pl.Float64),
                                         pitches_per_game=pl.lit(None, dtype=pl.Float64), role=pl.lit("RP"))

    # los rosters (si existen) corrigen nombre / equipo / rol y definen a los agentes libres
    carpeta = data_dir / "rosters"
    archivos = sorted(carpeta.glob("*.csv")) if carpeta.exists() else []
    rosters = None
    if archivos:
        rosters = pl.concat([pl.read_csv(f, schema_overrides={"pitcher_id": pl.String, "name": pl.String,
                                                                 "team_code": pl.String, "role": pl.String})
                             for f in archivos], how="diagonal_relaxed")
        rosters = rosters.with_columns(pl.col("season").cast(pl.Int64))
        r = rosters.unique(subset=pk, keep="last", maintain_order=True)
        cols = [c for c in ("name", "team_code", "role") if c in r.columns]
        pitchers = (pitchers.join(r.select(pk + cols).rename({c: f"_r_{c}" for c in cols}), on=pk, how="left",
                                  maintain_order="left")
                    .with_columns([pl.coalesce(f"_r_{c}", c).alias(c) for c in cols])
                    .drop([f"_r_{c}" for c in cols]))

    # whiffs por lado del bateador (para la ventaja de pelotón en el bullpen)
    if has("bats") and has("is_swing"):
        con_lado = df.filter(pl.col("bats").is_not_null())
        lados = sorted(con_lado["bats"].unique().to_list())
        plat = con_lado.group_by(pk).agg(
            [pl.col(v).filter(pl.col("bats") == lado).sum().alias(f"{n}_{lado[0].lower()}")
             for lado in lados for v, n in (("is_swing", "sw"), ("is_whiff", "wh"))])
        pitchers = pitchers.join(plat, on=pk, how="left", maintain_order="left")

    # salidas (cansancio) y % de zurdos por equipo
    appearances = team_hand = None
    if capabilities["has_dates"] and has("game_id"):
        app_cols = pk + ["date", "game_id"] + (["stadium_id"] if capabilities["has_stadiums"] else [])
        appearances = df.group_by(app_cols).len(name="pitches").sort(app_cols, nulls_last=True)
    if has("batter_team") and has("bats"):
        team_hand = (df.filter(pl.col("batter_team").is_not_null())
                       .group_by(["season", "batter_team"])
                       .agg(lhb_share=(pl.col("bats") == "Left").cast(pl.Float64).mean())
                       .sort(["season", "batter_team"]))

    # --- estudio empírico de altitud: ¿la aceleración del spin escala con la densidad del aire? -------
    df = df.with_columns(a_spin_obs=pl.Series(np.hypot(df["ax0"].to_numpy(), df["az0"].to_numpy() + G_FT_S2),
                                              nan_to_null=True),
                         a_drag_obs=pl.col("ay0"))
    df = df.with_columns(
        spin_ratio=pl.col("a_spin_obs") / pl.col("a_spin_obs").mean().over(keys),
        drag_ratio=pl.col("a_drag_obs") / pl.col("a_drag_obs").mean().over(keys),
        rho_ratio=pl.col("rho") / pl.col("rho").mean().over(keys),
    ).with_columns(cs.by_name("spin_ratio", "drag_ratio", "rho_ratio").fill_nan(None))
    group_col = ("stadium_id" if capabilities["has_stadiums"] and df["stadium_id"].null_count() < df.height
                 else "altitude_category")
    study_rows = []
    if has(group_col):
        resumen = (df.filter(pl.col(group_col).is_not_null()).group_by(group_col)
                     .agg(n=pl.len(), altitude_m=pl.col("altitude_m").mean(), rho_ratio=pl.col("rho_ratio").mean(),
                          spin_accel_ratio=pl.col("spin_ratio").mean(), spin_sd=pl.col("spin_ratio").std(),
                          drag_ratio=pl.col("drag_ratio").mean())
                     .sort(group_col))
        for r in resumen.iter_rows(named=True):
            study_rows.append({
                "group": r[group_col], "n": int(r["n"]), "altitude_m": float(r["altitude_m"]),
                "rho_ratio": float(r["rho_ratio"]), "spin_accel_ratio": float(r["spin_accel_ratio"]),
                "spin_accel_se": float(r["spin_sd"] / np.sqrt(r["n"])) if r["spin_sd"] is not None else float("nan"),
                "drag_ratio": float(r["drag_ratio"]),
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
        "seasons": sorted(int(s) for s in df["season"].unique().to_list()),
        "capabilities": capabilities,
        "columns_used": used,
        "rho_ref": rho_ref,
        "rows": df.height,
        "arm_sign": {"Right": float(sign_r), "Left": float(sign_l)},
        "source_files": ["API 1 /pitcheos/descargar"],
        "synthetic": False,
    }
    return {"arsenal": arsenal, "pitchers": pitchers, "appearances": appearances, "team_hand": team_hand,
            "rosters": rosters, "altitude_study": altitude_study, "meta": meta, "log": log}
