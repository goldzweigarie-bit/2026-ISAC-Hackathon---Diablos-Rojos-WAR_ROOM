"""Read-side queries used by the API. Every function returns plain JSON-able dicts."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .physics import aim_velocity, at_density, flight
from .store import SEA_LEVEL_ID, Store


def _f(x, nd=1):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(x), nd)


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
    here = store.proj[(store.proj.stadium_id == sid) & (store.proj.season == season)]
    sea = store.proj[(store.proj.stadium_id == SEA_LEVEL_ID) & (store.proj.season == season)]
    by_type = []
    for pt in ["Four-Seam", "Sinker", "Cutter", "Slider", "Curveball", "Changeup", "Splitter"]:
        h = here[here.pitch_type == pt]
        z = sea[sea.pitch_type == pt]
        if h.empty:
            continue
        w = h["n"].to_numpy(float)
        by_type.append({
            "pitch_type": pt,
            "ivb_here": _f(np.average(h.ivb, weights=w)), "ivb_sea": _f(np.average(z.ivb, weights=z["n"])),
            "hb_here": _f(np.average(np.abs(h.hb), weights=w)), "hb_sea": _f(np.average(np.abs(z.hb), weights=z["n"])),
            "plate_speed_here": _f(np.average(h.plate_speed, weights=w)),
            "plate_speed_sea": _f(np.average(z.plate_speed, weights=z["n"])),
        })
    out["league_by_pitch_type"] = by_type
    games = []
    sched = store.schedules.get(season)
    if sched is not None:
        g = sched[sched.stadium_id == sid]
        games = [{"date": r.date, "away_code": r.away_code, "home_code": r.home_code} for r in g.itertuples()]
    out["our_games_here"] = games
    return out


def leaderboard(store: Store, sid: str, season: int, role: str | None, limit: int, min_pitches: int | None):
    min_pitches = min_pitches if min_pitches is not None else store.config.get("min_pitches_leaderboard", 100)
    pp = store.pitcher_park[(store.pitcher_park.stadium_id == sid) & (store.pitcher_park.season == season)]
    pp = pp.merge(store.pitchers[store.pitchers.season == season][["pitcher_id", "name", "team_code", "role", "throws", "n_pitches"]],
                  on="pitcher_id", how="left")
    pp = pp[pp["n_pitches"] >= min_pitches]
    if role in ("SP", "RP"):
        pp = pp[pp.role == role]
    pp = pp.sort_values("stuff_plus", ascending=False)
    status = store.universe["status"]
    best = (store.proj[(store.proj.stadium_id == sid) & (store.proj.season == season)]
            .sort_values("stuff_plus", ascending=False).drop_duplicates("pitcher_id").set_index("pitcher_id"))
    rows = []
    for rank, r in enumerate(pp.head(limit).itertuples(), start=1):
        rows.append({
            "rank": rank, "pitcher_id": r.pitcher_id, "name": r.name, "team_code": r.team_code,
            "status": status.get(r.pitcher_id), "role": r.role, "throws": r.throws, "n_pitches": int(r.n_pitches),
            "stuff_plus": _f(r.stuff_plus), "stuff_neutral": _f(r.stuff_neutral),
            "altitude_delta": _f(r.stuff_plus - r.stuff_neutral),
            "best_pitch": best.loc[r.pitcher_id, "pitch_type"] if r.pitcher_id in best.index else None,
        })
    return {"stadium_id": sid, "season": season, "min_pitches": min_pitches, "total": int(len(pp)), "rows": rows}


def projection(store: Store, sid: str, pid: str, season: int, aim_x: float, aim_z: float):
    ars = store.arsenal[(store.arsenal.pitcher_id == pid) & (store.arsenal.season == season)]
    ars = ars[ars["n"] >= store.config.get("min_pitches_pitch_type", 20)].sort_values("n", ascending=False)
    if ars.empty:
        return None
    rho_sea, rho_here = store.rho_ref, store.park_rho(sid)
    ax_s, ay_s, az_s = at_density(ars.ax_mag_sl, ars.ay_drag_sl, ars.az_mag_sl, rho_sea, store.rho_ref)
    vx, vz = aim_velocity(ars.x0, ars.y0, ars.z0, ars.vx0, ars.vy0, ars.vz0, ax_s, ay_s, az_s, aim_x, aim_z)
    ax_h, ay_h, az_h = at_density(ars.ax_mag_sl, ars.ay_drag_sl, ars.az_mag_sl, rho_here, store.rho_ref)
    vx, vz, ax_s, ay_s, az_s, ax_h, ay_h, az_h = (np.asarray(v, dtype=float) for v in (vx, vz, ax_s, ay_s, az_s, ax_h, ay_h, az_h))
    f_sea = flight(ars.x0, ars.y0, ars.z0, vx, ars.vy0, vz, ax_s, ay_s, az_s)
    f_here = flight(ars.x0, ars.y0, ars.z0, vx, ars.vy0, vz, ax_h, ay_h, az_h)
    pr = store.proj[(store.proj.pitcher_id == pid) & (store.proj.season == season)]
    here_p = pr[pr.stadium_id == sid].set_index("pitch_type")
    sea_p = pr[pr.stadium_id == SEA_LEVEL_ID].set_index("pitch_type")

    def path(fl_x0, fl_z0, vx0, vy0, vz0, ax, ay, az, t_end, steps=24):
        ts = np.linspace(0, t_end, steps)
        y = 50 + vy0 * ts + 0.5 * ay * ts * ts
        return [{"y": _f(yy, 2), "x": _f(fl_x0 + vx0 * t + 0.5 * ax * t * t, 3), "z": _f(fl_z0 + vz0 * t + 0.5 * az * t * t, 3)}
                for t, yy in zip(ts, y)]

    pitches = []
    for i, r in enumerate(ars.itertuples()):
        pt = r.pitch_type
        hp = here_p.loc[pt] if pt in here_p.index else None
        sp = sea_p.loc[pt] if pt in sea_p.index else None
        pitches.append({
            "pitch_type": pt, "n": int(r.n), "usage": _f(100 * r.usage),
            "rel_speed": _f(r.rel_speed), "spin_rate": _f(r.spin_rate, 0), "spin_axis": _f(r.spin_axis, 0),
            "whiff_pct": _f(100 * r.whiffs / r.swings) if getattr(r, "swings", 0) else None,
            "sea": {"px": _f(f_sea["px"][i], 3), "pz": _f(f_sea["pz"][i], 3), "plate_speed": _f(f_sea["plate_speed"][i]),
                    "ivb": _f(sp["ivb"]) if sp is not None else None, "hb": _f(sp["hb"]) if sp is not None else None,
                    "vaa": _f(f_sea["vaa"][i], 2), "stuff_plus": _f(sp["stuff_plus"]) if sp is not None else None,
                    "path": path(r.x0, r.z0, vx[i], r.vy0, vz[i], ax_s[i], ay_s[i], az_s[i], f_sea["t"][i])},
            "here": {"px": _f(f_here["px"][i], 3), "pz": _f(f_here["pz"][i], 3), "plate_speed": _f(f_here["plate_speed"][i]),
                     "ivb": _f(hp["ivb"]) if hp is not None else None, "hb": _f(hp["hb"]) if hp is not None else None,
                     "vaa": _f(f_here["vaa"][i], 2), "stuff_plus": _f(hp["stuff_plus"]) if hp is not None else None,
                     "path": path(r.x0, r.z0, vx[i], r.vy0, vz[i], ax_h[i], ay_h[i], az_h[i], f_here["t"][i])},
            "stuff_neutral": _f(hp["stuff_neutral"]) if hp is not None else None,
            "miss_inches": _f(12 * math.hypot(f_here["px"][i] - f_sea["px"][i], f_here["pz"][i] - f_sea["pz"][i])),
        })
    info = pitcher_header(store, pid, season)
    pp = store.pitcher_park[(store.pitcher_park.pitcher_id == pid) & (store.pitcher_park.season == season)].set_index("stadium_id")
    info["stuff_here"] = _f(pp.loc[sid, "stuff_plus"]) if sid in pp.index else None
    info["stuff_sea"] = _f(pp.loc[SEA_LEVEL_ID, "stuff_plus"]) if SEA_LEVEL_ID in pp.index else None
    return {"stadium": stadium_summary(store, store.stadium_by_id[sid]), "pitcher": info,
            "aim": {"x": aim_x, "z": aim_z}, "pitches": pitches}


def pitcher_header(store: Store, pid: str, season: int | None) -> dict | None:
    row = store.pitcher_row(pid, season)
    if row is None:
        return None
    u = store.universe.loc[pid] if pid in store.universe.index else None
    return {
        "pitcher_id": pid, "name": row["name"], "season": int(row["season"]), "throws": row["throws"],
        "role": row["role"], "team_code": row["team_code"], "team_name": store.team_name(row["team_code"]),
        "status": u["status"] if u is not None else None, "n_pitches": int(row["n_pitches"]),
        "games": None if pd.isna(row.get("games")) else int(row["games"]),
        "is_ours": (u is not None and u["status"] == store.config["our_team_code"]),
        "seasons": sorted(int(s) for s in store.pitchers[store.pitchers.pitcher_id == pid].season.unique()),
    }


def pitcher_profile(store: Store, pid: str, season: int | None):
    head = pitcher_header(store, pid, season)
    if head is None:
        return None
    season = head["season"]
    pr = store.proj[(store.proj.pitcher_id == pid) & (store.proj.season == season)]
    ars = store.arsenal[(store.arsenal.pitcher_id == pid) & (store.arsenal.season == season)].set_index("pitch_type")
    neutral = pr[pr.stadium_id != SEA_LEVEL_ID].groupby("pitch_type").agg(
        stuff_neutral=("stuff_plus", "mean"), best=("stuff_plus", "max"), worst=("stuff_plus", "min"))
    sea = pr[pr.stadium_id == SEA_LEVEL_ID].set_index("pitch_type")
    arsenal = []
    for pt in pr.sort_values("n", ascending=False).pitch_type.unique():
        a = ars.loc[pt]
        arsenal.append({
            "pitch_type": pt, "n": int(a["n"]), "usage": _f(100 * a["usage"]), "rel_speed": _f(a["rel_speed"]),
            "spin_rate": _f(a["spin_rate"], 0), "extension": _f(a["extension"], 2),
            "ivb_sea": _f(sea.loc[pt, "ivb"]), "hb_sea": _f(sea.loc[pt, "hb"]),
            "whiff_pct": _f(100 * a["whiffs"] / a["swings"]) if "swings" in a and a["swings"] else None,
            "stuff_neutral": _f(neutral.loc[pt, "stuff_neutral"]),
            "stuff_best_park": _f(neutral.loc[pt, "best"]), "stuff_worst_park": _f(neutral.loc[pt, "worst"]),
        })
    pp = store.pitcher_park[(store.pitcher_park.pitcher_id == pid) & (store.pitcher_park.season == season)]
    by_park = []
    for s in sorted(store.stadiums, key=lambda s: -s["altitude_m"]):
        r = pp[pp.stadium_id == s["id"]]
        if r.empty:
            continue
        by_park.append({"stadium_id": s["id"], "venue_name": s["venue_name"], "team_code": s["team_code"],
                        "altitude_m": s["altitude_m"], "stuff_plus": _f(r.stuff_plus.iat[0])})
    overall = pp[pp.stadium_id != SEA_LEVEL_ID]
    head["stuff_neutral"] = _f(overall.stuff_plus.mean()) if len(overall) else None
    home = store.config["home_stadium_id"]
    head["stuff_home"] = _f(pp[pp.stadium_id == home].stuff_plus.iat[0]) if (pp.stadium_id == home).any() else None
    workload = []
    if store.appearances is not None:
        a = store.appearances[(store.appearances.pitcher_id == pid) & (store.appearances.season == season)].sort_values("date")
        workload = [{"date": d.date().isoformat(), "pitches": int(p),
                     "stadium_id": getattr(r, "stadium_id", None)} for r, d, p in zip(a.itertuples(), a.date, a.pitches)]
    return {"pitcher": head, "arsenal": arsenal, "by_park": by_park, "workload": workload[-30:]}


def schedule(store: Store, season: int) -> dict:
    sched = store.schedules.get(season)
    if sched is None:
        return {"season": season, "games": [], "record": None}
    ours = store.config["our_team_code"]
    games, w, l = [], 0, 0
    for r in sched.itertuples():
        home = r.home_code == ours
        opp = r.away_code if home else r.home_code
        rs = r.home_score if home else r.away_score
        ra = r.away_score if home else r.home_score
        result = None
        if not (pd.isna(rs) or pd.isna(ra)) and str(r.status).lower() not in ("postponed", "cancelled"):
            result = "W" if rs > ra else "L"
            w += result == "W"
            l += result == "L"
        s = store.stadium_by_id[r.stadium_id]
        games.append({"date": r.date, "home": bool(home), "opponent_code": opp, "opponent_name": store.team_name(opp),
                      "stadium_id": r.stadium_id, "venue_name": s["venue_name"], "altitude_m": s["altitude_m"],
                      "runs_for": None if pd.isna(rs) else int(rs), "runs_against": None if pd.isna(ra) else int(ra),
                      "result": result, "status": r.status})
    return {"season": season, "team_code": ours, "games": games, "record": {"w": int(w), "l": int(l)}}


def free_agents(store: Store, status: str, role: str | None, throws: str | None, sort: str, limit: int) -> dict:
    ours = store.config["our_team_code"]
    home = store.config["home_stadium_id"]
    u = store.universe.reset_index()
    u = u[u.status != ours]
    if status == "fa":
        u = u[u.status == "FA"]
    elif status == "signed":
        u = u[~u.status.isin(["FA", "?"])]
    if role in ("SP", "RP"):
        u = u[u.role == role]
    if throws in ("Right", "Left"):
        u = u[u.throws == throws]
    pp = store.pitcher_park
    key = pd.MultiIndex.from_frame(u[["season", "pitcher_id"]])
    home_pp = pp[pp.stadium_id == home].set_index(["season", "pitcher_id"])
    u = u.assign(stuff_home=home_pp["stuff_plus"].reindex(key).to_numpy(),
                 stuff_neutral=home_pp["stuff_neutral"].reindex(key).to_numpy())
    u = u.dropna(subset=["stuff_home"])
    # our current staff by role, for the "fit" comparison
    cur = store.current_season
    our_ids = store.universe.index[store.universe.status == ours]
    ours_pp = home_pp.reindex(pd.MultiIndex.from_arrays([[cur] * len(our_ids), our_ids])).dropna(subset=["stuff_plus"])
    our_roles = store.pitchers[(store.pitchers.season == cur) & (store.pitchers.pitcher_id.isin(our_ids))].set_index("pitcher_id")["role"]
    medians = {}
    for rl in ("SP", "RP"):
        ids = our_roles.index[our_roles == rl]
        vals = ours_pp.loc[ours_pp.index.get_level_values(1).isin(ids), "stuff_plus"]
        medians[rl] = float(vals.median()) if len(vals) else None
    u["fit"] = [None if medians.get(r) is None else sh - medians[r] for sh, r in zip(u.stuff_home, u.role)]
    sort_col = {"home": "stuff_home", "neutral": "stuff_neutral", "fit": "fit"}.get(sort, "stuff_home")
    u = u.sort_values(sort_col, ascending=False)
    best = store.proj[store.proj.stadium_id == home].sort_values("stuff_plus", ascending=False).drop_duplicates(["season", "pitcher_id"])
    best = best.set_index(["season", "pitcher_id"])
    rows = []
    for r in u.head(limit).itertuples():
        k = (r.season, r.pitcher_id)
        rows.append({
            "pitcher_id": r.pitcher_id, "name": r.name, "status": r.status,
            "team_name": store.team_name(r.status) if r.status != "FA" else None,
            "role": r.role, "throws": r.throws, "last_season": int(r.season), "n_pitches": int(r.n_pitches),
            "stuff_home": _f(r.stuff_home), "stuff_neutral": _f(r.stuff_neutral),
            "altitude_delta": _f(r.stuff_home - r.stuff_neutral), "fit": _f(r.fit),
            "best_pitch": best.loc[k, "pitch_type"] if k in best.index else None,
            "best_pitch_stuff": _f(best.loc[k, "stuff_plus"]) if k in best.index else None,
        })
    return {"home_stadium_id": home, "our_medians": {k: _f(v) for k, v in medians.items()}, "total": int(len(u)), "rows": rows}
