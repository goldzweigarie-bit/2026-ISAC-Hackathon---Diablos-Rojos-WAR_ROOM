"""Arma la respuesta de cada pantalla. Cada función devuelve dicts listos para JSON."""
from __future__ import annotations

import math

import numpy as np
import polars as pl

from .physics import aim_velocity, at_density, flight
from .store import SEA_LEVEL_ID, Store

PITCH_ORDER = ["Four-Seam", "Sinker", "Cutter", "Slider", "Curveball", "Changeup", "Splitter"]


def _f(x, nd=1):
    """Número redondeado para JSON; vacío, NaN o infinito → None."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, nd)


def _por(df: pl.DataFrame, columna: str) -> dict:
    """Tabla → {valor de la columna: renglón como dict} (si un valor se repite, gana el primero)."""
    out = {}
    for r in df.iter_rows(named=True):
        out.setdefault(r[columna], r)
    return out


def stadium_summary(store: Store, s: dict) -> dict:
    rho = store.park_rho(s["id"])
    ratio = rho / store.rho_ref
    return {
        "id": s["id"], "venue_name": s["venue_name"], "city": s["city"], "state": s["state"], "zone": s["zone"],
        "team_code": s["team_code"], "team_name": s["team_name"], "lat": s["lat"], "lon": s["lon"],
        "altitude_m": s["altitude_m"], "typical_temp_c": s["typical_temp_c"],
        "air_density": _f(rho, 3), "density_vs_sea_level": _f(ratio, 3),
        "movement_retained_pct": _f(100 * ratio, 1),
        "is_home": s["id"] == store.config["home_stadium_id"],
    }


def list_stadiums(store: Store) -> list[dict]:
    return [stadium_summary(store, s) for s in store.stadiums]


def stadium_detail(store: Store, sid: str, season: int) -> dict:
    s = store.stadium_by_id[sid]
    out = stadium_summary(store, s)
    temporada = store.proj.filter(pl.col("season") == season)
    here = temporada.filter(pl.col("stadium_id") == sid)
    sea = temporada.filter(pl.col("stadium_id") == SEA_LEVEL_ID)
    by_type = []
    for pt in PITCH_ORDER:
        h = here.filter(pl.col("pitch_type") == pt)
        z = sea.filter(pl.col("pitch_type") == pt)
        if h.is_empty():
            continue
        w, wz = h["n"].to_numpy().astype(float), z["n"].to_numpy().astype(float)
        avg = lambda d, c, pesos, absoluto=False: np.average(  # noqa: E731
            np.abs(d[c].to_numpy()) if absoluto else d[c].to_numpy(), weights=pesos)
        by_type.append({
            "pitch_type": pt,
            "ivb_here": _f(avg(h, "ivb", w)), "ivb_sea": _f(avg(z, "ivb", wz)),
            "hb_here": _f(avg(h, "hb", w, True)), "hb_sea": _f(avg(z, "hb", wz, True)),
            "plate_speed_here": _f(avg(h, "plate_speed", w)), "plate_speed_sea": _f(avg(z, "plate_speed", wz)),
        })
    out["league_by_pitch_type"] = by_type
    games = []
    sched = store.schedules.get(season)
    if sched is not None:
        games = [{"date": r["date"], "away_code": r["away_code"], "home_code": r["home_code"]}
                 for r in sched.filter(pl.col("stadium_id") == sid).iter_rows(named=True)]
    out["our_games_here"] = games
    return out


def _mejor_pitcheo(store: Store, sid: str, season: int | None = None) -> dict:
    """{(temporada, pitcher): renglón de su pitcheo con más Stuff+ en ese parque}."""
    d = store.proj.filter(pl.col("stadium_id") == sid)
    if season is not None:
        d = d.filter(pl.col("season") == season)
    d = (d.sort("stuff_plus", descending=True, nulls_last=True, maintain_order=True)
          .unique(["season", "pitcher_id"], keep="first", maintain_order=True))
    return {(r["season"], r["pitcher_id"]): r for r in d.iter_rows(named=True)}


def leaderboard(store: Store, sid: str, season: int, role: str | None, limit: int, min_pitches: int | None):
    min_pitches = min_pitches if min_pitches is not None else store.config.get("min_pitches_leaderboard", 100)
    info = store.pitchers.filter(pl.col("season") == season).select(
        "pitcher_id", "name", "team_code", "role", "throws", "n_pitches")
    pp = (store.pitcher_park.filter((pl.col("stadium_id") == sid) & (pl.col("season") == season))
               .join(info, on="pitcher_id", how="left", maintain_order="left")
               .filter(pl.col("n_pitches") >= min_pitches))
    if role in ("SP", "RP"):
        pp = pp.filter(pl.col("role") == role)
    pp = pp.sort("stuff_plus", descending=True, nulls_last=True, maintain_order=True)
    best = _mejor_pitcheo(store, sid, season)
    rows = []
    for rank, r in enumerate(pp.head(limit).iter_rows(named=True), start=1):
        b = best.get((season, r["pitcher_id"]))
        rows.append({
            "rank": rank, "pitcher_id": r["pitcher_id"], "name": r["name"], "team_code": r["team_code"],
            "status": store.status_by_id.get(r["pitcher_id"]), "role": r["role"], "throws": r["throws"],
            "n_pitches": int(r["n_pitches"]),
            "stuff_plus": _f(r["stuff_plus"]), "stuff_neutral": _f(r["stuff_neutral"]),
            "altitude_delta": _f(r["stuff_plus"] - r["stuff_neutral"]),
            "best_pitch": b["pitch_type"] if b else None,
        })
    return {"stadium_id": sid, "season": season, "min_pitches": min_pitches, "total": pp.height, "rows": rows}


def projection(store: Store, sid: str, pid: str, season: int, aim_x: float, aim_z: float):
    ars = (store.arsenal.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season)
                                & (pl.col("n") >= store.config.get("min_pitches_pitch_type", 20)))
                .sort("n", descending=True, maintain_order=True))
    if ars.is_empty():
        return None
    a = {c: ars[c].to_numpy().astype(float) for c in ("ax_mag_sl", "ay_drag_sl", "az_mag_sl", "x0", "y0", "z0",
                                                       "vx0", "vy0", "vz0")}
    rho_sea, rho_here = store.rho_ref, store.park_rho(sid)
    ax_s, ay_s, az_s = at_density(a["ax_mag_sl"], a["ay_drag_sl"], a["az_mag_sl"], rho_sea, store.rho_ref)
    vx, vz = aim_velocity(a["x0"], a["y0"], a["z0"], a["vx0"], a["vy0"], a["vz0"], ax_s, ay_s, az_s, aim_x, aim_z)
    ax_h, ay_h, az_h = at_density(a["ax_mag_sl"], a["ay_drag_sl"], a["az_mag_sl"], rho_here, store.rho_ref)
    vx, vz, ax_s, ay_s, az_s, ax_h, ay_h, az_h = (np.asarray(v, dtype=float) for v in (vx, vz, ax_s, ay_s, az_s, ax_h, ay_h, az_h))
    f_sea = flight(a["x0"], a["y0"], a["z0"], vx, a["vy0"], vz, ax_s, ay_s, az_s)
    f_here = flight(a["x0"], a["y0"], a["z0"], vx, a["vy0"], vz, ax_h, ay_h, az_h)
    pr = store.proj.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season))
    here_p = _por(pr.filter(pl.col("stadium_id") == sid), "pitch_type")
    sea_p = _por(pr.filter(pl.col("stadium_id") == SEA_LEVEL_ID), "pitch_type")

    def path(fl_x0, fl_z0, vx0, vy0, vz0, ax, ay, az, t_end, steps=24):
        ts = np.linspace(0, t_end, steps)
        y = 50 + vy0 * ts + 0.5 * ay * ts * ts
        return [{"y": _f(yy, 2), "x": _f(fl_x0 + vx0 * t + 0.5 * ax * t * t, 3), "z": _f(fl_z0 + vz0 * t + 0.5 * az * t * t, 3)}
                for t, yy in zip(ts, y)]

    def lado(f, p, i, vx_i, vz_i, ax, ay, az):
        return {"px": _f(f["px"][i], 3), "pz": _f(f["pz"][i], 3), "plate_speed": _f(f["plate_speed"][i]),
                "ivb": _f(p["ivb"]) if p else None, "hb": _f(p["hb"]) if p else None,
                "vaa": _f(f["vaa"][i], 2), "stuff_plus": _f(p["stuff_plus"]) if p else None,
                "path": path(a["x0"][i], a["z0"][i], vx_i, a["vy0"][i], vz_i, ax, ay, az, f["t"][i])}

    pitches = []
    for i, r in enumerate(ars.iter_rows(named=True)):
        pt = r["pitch_type"]
        hp, sp = here_p.get(pt), sea_p.get(pt)
        swings = r.get("swings")
        pitches.append({
            "pitch_type": pt, "n": int(r["n"]), "usage": _f(100 * r["usage"]),
            "rel_speed": _f(r["rel_speed"]), "spin_rate": _f(r["spin_rate"], 0), "spin_axis": _f(r["spin_axis"], 0),
            "whiff_pct": _f(100 * r["whiffs"] / swings) if swings else None,
            "sea": lado(f_sea, sp, i, vx[i], vz[i], ax_s[i], ay_s[i], az_s[i]),
            "here": lado(f_here, hp, i, vx[i], vz[i], ax_h[i], ay_h[i], az_h[i]),
            "stuff_neutral": _f(hp["stuff_neutral"]) if hp else None,
            "miss_inches": _f(12 * math.hypot(f_here["px"][i] - f_sea["px"][i], f_here["pz"][i] - f_sea["pz"][i])),
        })
    info = pitcher_header(store, pid, season)
    pp = _por(store.pitcher_park.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season)), "stadium_id")
    info["stuff_here"] = _f(pp[sid]["stuff_plus"]) if sid in pp else None
    info["stuff_sea"] = _f(pp[SEA_LEVEL_ID]["stuff_plus"]) if SEA_LEVEL_ID in pp else None
    return {"stadium": stadium_summary(store, store.stadium_by_id[sid]), "pitcher": info,
            "aim": {"x": aim_x, "z": aim_z}, "pitches": pitches}


def pitcher_header(store: Store, pid: str, season: int | None) -> dict | None:
    row = store.pitcher_row(pid, season)
    if row is None:
        return None
    status = store.status_by_id.get(pid)
    games = row.get("games")
    return {
        "pitcher_id": pid, "name": row["name"], "season": int(row["season"]), "throws": row["throws"],
        "role": row["role"], "team_code": row["team_code"], "team_name": store.team_name(row["team_code"]),
        "status": status, "n_pitches": int(row["n_pitches"]),
        "games": None if games is None or (isinstance(games, float) and math.isnan(games)) else int(games),
        "is_ours": status is not None and status == store.config["our_team_code"],
        "seasons": sorted(store.pitchers.filter(pl.col("pitcher_id") == pid)["season"].unique().to_list()),
    }


def pitcher_profile(store: Store, pid: str, season: int | None):
    head = pitcher_header(store, pid, season)
    if head is None:
        return None
    season = head["season"]
    pr = store.proj.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season))
    ars = _por(store.arsenal.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season)), "pitch_type")
    neutral = _por(pr.filter(pl.col("stadium_id") != SEA_LEVEL_ID).group_by("pitch_type").agg(
        stuff_neutral=pl.col("stuff_plus").mean(), best=pl.col("stuff_plus").max(), worst=pl.col("stuff_plus").min()),
        "pitch_type")
    sea = _por(pr.filter(pl.col("stadium_id") == SEA_LEVEL_ID), "pitch_type")
    arsenal = []
    for pt in pr.sort("n", descending=True, maintain_order=True)["pitch_type"].unique(maintain_order=True):
        a, nt, sp = ars[pt], neutral.get(pt, {}), sea.get(pt, {})
        swings = a.get("swings")
        arsenal.append({
            "pitch_type": pt, "n": int(a["n"]), "usage": _f(100 * a["usage"]), "rel_speed": _f(a["rel_speed"]),
            "spin_rate": _f(a["spin_rate"], 0), "extension": _f(a["extension"], 2),
            "ivb_sea": _f(sp.get("ivb")), "hb_sea": _f(sp.get("hb")),
            "whiff_pct": _f(100 * a["whiffs"] / swings) if swings else None,
            "stuff_neutral": _f(nt.get("stuff_neutral")),
            "stuff_best_park": _f(nt.get("best")), "stuff_worst_park": _f(nt.get("worst")),
        })
    pp = _por(store.pitcher_park.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season)), "stadium_id")
    by_park = []
    for s in sorted(store.stadiums, key=lambda s: -s["altitude_m"]):
        if s["id"] not in pp:
            continue
        by_park.append({"stadium_id": s["id"], "venue_name": s["venue_name"], "team_code": s["team_code"],
                        "altitude_m": s["altitude_m"], "stuff_plus": _f(pp[s["id"]]["stuff_plus"])})
    parques = [r["stuff_plus"] for k, r in pp.items() if k != SEA_LEVEL_ID]
    head["stuff_neutral"] = _f(float(np.mean(parques))) if parques else None
    home = store.config["home_stadium_id"]
    head["stuff_home"] = _f(pp[home]["stuff_plus"]) if home in pp else None
    workload = []
    if store.appearances is not None:
        a = (store.appearances.filter((pl.col("pitcher_id") == pid) & (pl.col("season") == season))
                              .sort("date", maintain_order=True))
        workload = [{"date": r["date"].isoformat(), "pitches": int(r["pitches"]), "stadium_id": r.get("stadium_id")}
                    for r in a.iter_rows(named=True)]
    return {"pitcher": head, "arsenal": arsenal, "by_park": by_park, "workload": workload[-30:]}


def schedule(store: Store, season: int) -> dict:
    sched = store.schedules.get(season)
    if sched is None:
        return {"season": season, "games": [], "record": None}
    ours = store.config["our_team_code"]
    games, w, l = [], 0, 0
    for r in sched.iter_rows(named=True):
        home = r["home_code"] == ours
        opp = r["away_code"] if home else r["home_code"]
        rs = r["home_score"] if home else r["away_score"]
        ra = r["away_score"] if home else r["home_score"]
        result = None
        if rs is not None and ra is not None and str(r["status"]).lower() not in ("postponed", "cancelled"):
            result = "W" if rs > ra else "L"
            w += result == "W"
            l += result == "L"
        s = store.stadium_by_id[r["stadium_id"]]
        games.append({"date": r["date"], "home": bool(home), "opponent_code": opp, "opponent_name": store.team_name(opp),
                      "stadium_id": r["stadium_id"], "venue_name": s["venue_name"], "altitude_m": s["altitude_m"],
                      "runs_for": None if rs is None else int(rs), "runs_against": None if ra is None else int(ra),
                      "result": result, "status": r["status"]})
    return {"season": season, "team_code": ours, "games": games, "record": {"w": int(w), "l": int(l)}}


def free_agents(store: Store, status: str, role: str | None, throws: str | None, sort: str, limit: int) -> dict:
    ours = store.config["our_team_code"]
    home = store.config["home_stadium_id"]
    u = store.universe.filter(pl.col("status") != ours)
    if status == "fa":
        u = u.filter(pl.col("status") == "FA")
    elif status == "signed":
        u = u.filter(~pl.col("status").is_in(["FA", "?"]))
    if role in ("SP", "RP"):
        u = u.filter(pl.col("role") == role)
    if throws in ("Right", "Left"):
        u = u.filter(pl.col("throws") == throws)
    home_pp = store.pitcher_park.filter(pl.col("stadium_id") == home)
    u = (u.join(home_pp.select("season", "pitcher_id", pl.col("stuff_plus").alias("stuff_home"), "stuff_neutral"),
                on=["season", "pitcher_id"], how="left", maintain_order="left")
          .filter(pl.col("stuff_home").is_not_null()))
    # nuestro staff actual por rol, para la comparación "fit"
    cur = store.current_season
    our_ids = store.universe.filter(pl.col("status") == ours)["pitcher_id"]
    ours_pp = (home_pp.filter((pl.col("season") == cur) & pl.col("pitcher_id").is_in(our_ids.to_list())
                              & pl.col("stuff_plus").is_not_null())
                      .join(store.pitchers.filter(pl.col("season") == cur).select("pitcher_id", "role"),
                            on="pitcher_id", how="left"))
    medians = {}
    for rl in ("SP", "RP"):
        vals = ours_pp.filter(pl.col("role") == rl)["stuff_plus"]
        medians[rl] = float(vals.median()) if vals.len() else None
    u = u.with_columns(fit=pl.col("stuff_home") - pl.col("role").replace_strict(
        {k: v for k, v in medians.items() if v is not None}, default=None, return_dtype=pl.Float64))
    sort_col = {"home": "stuff_home", "neutral": "stuff_neutral", "fit": "fit"}.get(sort, "stuff_home")
    u = u.sort(sort_col, descending=True, nulls_last=True, maintain_order=True)
    best = _mejor_pitcheo(store, home)
    rows = []
    for r in u.head(limit).iter_rows(named=True):
        b = best.get((r["season"], r["pitcher_id"]))
        rows.append({
            "pitcher_id": r["pitcher_id"], "name": r["name"], "status": r["status"],
            "team_name": store.team_name(r["status"]) if r["status"] != "FA" else None,
            "role": r["role"], "throws": r["throws"], "last_season": int(r["season"]), "n_pitches": int(r["n_pitches"]),
            "stuff_home": _f(r["stuff_home"]), "stuff_neutral": _f(r["stuff_neutral"]),
            "altitude_delta": _f(r["stuff_home"] - r["stuff_neutral"]), "fit": _f(r["fit"]),
            "best_pitch": b["pitch_type"] if b else None,
            "best_pitch_stuff": _f(b["stuff_plus"]) if b else None,
        })
    return {"home_stadium_id": home, "our_medians": {k: _f(v) for k, v in medians.items()}, "total": u.height, "rows": rows}
