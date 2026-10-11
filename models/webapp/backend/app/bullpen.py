"""Recomendación de bullpen para la siguiente serie de los Diablos: cansancio + Stuff+ en ese parque + zurdos del rival."""
from __future__ import annotations

from datetime import date, timedelta

import math

import polars as pl

from .services import _f, stadium_summary
from .store import Store

LEAGUE_SHRINK_SWINGS = 60


def _num(x) -> float:
    """Vacío → NaN, para que la aritmética no truene (igual que un dato faltante)."""
    return float("nan") if x is None else float(x)


def _next_series(sched: pl.DataFrame, as_of: date, ours: str):
    """Los juegos de la siguiente serie a partir de `as_of` (mismo rival y mismo parque, días seguidos)."""
    games = (sched.filter(~pl.col("status").cast(pl.String).fill_null("nan").str.to_lowercase()
                          .is_in(["postponed", "cancelled"]))
                  .with_columns(d=pl.col("date").str.to_date("%Y-%m-%d")))
    upcoming = games.filter(pl.col("d") >= as_of).sort("d", maintain_order=True)
    if upcoming.is_empty():  # temporada terminada: se muestra la última serie
        upcoming = games.filter(pl.col("d") == games["d"].max())
    rows = list(upcoming.iter_rows(named=True))
    first = rows[0]
    opp = lambda r: r["away_code"] if r["home_code"] == ours else r["home_code"]  # noqa: E731
    series = [first]
    for r in rows[1:]:
        if opp(r) == opp(first) and r["stadium_id"] == first["stadium_id"] and (r["d"] - series[-1]["d"]).days <= 2:
            series.append(r)
        else:
            break
    return series, opp(first)


def recommend(store: Store, as_of: date, season: int) -> dict:
    ours = store.config["our_team_code"]
    rules = store.config.get("bullpen", {})
    sched = store.schedules.get(season)
    if sched is None or sched.is_empty():
        return {"available": False, "reason": "no_schedule"}
    series, opp = _next_series(sched, as_of, ours)
    game_day = series[0]["d"]
    sid = series[0]["stadium_id"]
    staff_season = season if (store.pitchers["season"] == season).any() else store.current_season
    sw = store.pitchers.filter(pl.col("season") == staff_season)
    staff = sw.filter(pl.col("team_code") == ours)
    pp = {r["pitcher_id"]: r for r in store.pitcher_park.filter(
        (pl.col("season") == staff_season) & (pl.col("stadium_id") == sid)).iter_rows(named=True)}

    # línea base de la liga para el pelotón (whiffs contra zurdos / derechos)
    league_l = sw["wh_l"].sum() / max(sw["sw_l"].sum(), 1) if "wh_l" in sw.columns else float("nan")
    league_r = sw["wh_r"].sum() / max(sw["sw_r"].sum(), 1) if "wh_r" in sw.columns else float("nan")
    lhb = None
    if store.team_hand is not None:
        th = store.team_hand.filter(pl.col("batter_team") == opp)
        if th.height:
            lhb = float(th.sort("season")["lhb_share"][-1])
    lhb_share = lhb if lhb is not None else 0.38

    apps = None
    if store.appearances is not None:
        apps = store.appearances.filter((pl.col("date") < game_day)
                                        & (pl.col("date") >= game_day - timedelta(days=7)))

    rows = []
    for p in staff.iter_rows(named=True):
        park = pp.get(p["pitcher_id"], {})
        sp_here, neutral = _num(park.get("stuff_plus")), _num(park.get("stuff_neutral"))
        if math.isnan(sp_here):
            continue
        reasons = []
        status = "available"
        last1 = last3 = last7 = 0
        pitched_yday = pitched_2d = False
        if apps is not None:
            salidas = [((game_day - r["date"]).days, r["pitches"])
                       for r in apps.filter(pl.col("pitcher_id") == p["pitcher_id"]).iter_rows(named=True)]
            last1 = int(sum(n for d, n in salidas if d == 1))
            last3 = int(sum(n for d, n in salidas if d <= 3))
            last7 = int(sum(n for _, n in salidas))
            pitched_yday = any(d == 1 for d, _ in salidas)
            pitched_2d = pitched_yday and any(d == 2 for d, _ in salidas)
            if (rules.get("rest_if_pitched_both_last_2_days", True) and pitched_2d):
                status = "rest"
                reasons.append({"code": "back_to_back"})
            elif last1 > rules.get("rest_if_pitches_last_day_over", 30):
                status = "rest"
                reasons.append({"code": "heavy_yesterday", "value": last1})
            elif last3 > rules.get("rest_if_pitches_last_3_days_over", 55):
                status = "rest"
                reasons.append({"code": "heavy_3d", "value": last3})
            elif rules.get("limited_if_pitched_yesterday", True) and pitched_yday:
                status = "limited"
                reasons.append({"code": "pitched_yesterday", "value": last1})
            elif last3 > rules.get("limited_if_pitches_last_3_days_over", 30):
                status = "limited"
                reasons.append({"code": "busy_3d", "value": last3})
            if p["role"] == "SP" and last7 > 0:
                status = "rest"
                reasons.append({"code": "starter_in_rotation"})
        # platoon: shrunk whiff rates vs L / R, mixed by the opponent's lineup
        edge = 0.0
        if "wh_l" in staff.columns:
            wl = (_num(p["wh_l"]) + LEAGUE_SHRINK_SWINGS * league_l) / (_num(p["sw_l"]) + LEAGUE_SHRINK_SWINGS)
            wr = (_num(p["wh_r"]) + LEAGUE_SHRINK_SWINGS * league_r) / (_num(p["sw_r"]) + LEAGUE_SHRINK_SWINGS)
            exp = lhb_share * wl + (1 - lhb_share) * wr
            base = lhb_share * league_l + (1 - lhb_share) * league_r
            edge = 100 * (exp - base)
            if abs(edge) >= 1.5:
                reasons.append({"code": "platoon_plus" if edge > 0 else "platoon_minus", "value": _f(edge)})
        delta = sp_here - neutral
        if abs(delta) >= 1.5:
            reasons.append({"code": "park_plus" if delta > 0 else "park_minus", "value": _f(delta)})
        score = sp_here + 1.0 * edge
        mult = {"available": 1.0, "limited": 0.85, "rest": 0.0}[status]
        rows.append({
            "pitcher_id": p["pitcher_id"], "name": p["name"], "throws": p["throws"], "role": p["role"],
            "stuff_here": _f(sp_here), "stuff_neutral": _f(neutral), "platoon_edge": _f(edge),
            "score": _f(score * mult), "status": status, "reasons": reasons,
            "pitches_last_1d": last1, "pitches_last_3d": last3, "pitches_last_7d": last7,
            "pitches_per_game": _f(p["pitches_per_game"]),
        })

    relievers = [r for r in rows if r["role"] == "RP"]
    avail = sorted([r for r in relievers if r["status"] != "rest"], key=lambda r: -r["score"])
    roles = {}
    order = ["closer", "setup", "setup", "middle", "middle"]
    for slot, r in zip(order, avail):
        roles.setdefault(slot, []).append(r["pitcher_id"])
    used = {pid for ids in roles.values() for pid in ids}
    long_pool = sorted([r for r in avail if r["pitcher_id"] not in used],
                       key=lambda r: -((r["pitches_per_game"] or 0) + 0.2 * r["score"]))
    if long_pool:
        roles["long"] = [long_pool[0]["pitcher_id"]]
    for r in relievers:
        r["slot"] = next((k for k, ids in roles.items() if r["pitcher_id"] in ids), "rest" if r["status"] == "rest" else "depth")

    games = [{"date": str(g["d"]), "home": g["home_code"] == ours, "opponent_code": opp,
              "opponent_name": store.team_name(opp)} for g in series]
    return {
        "available": True, "as_of": str(as_of), "season": season, "staff_season": int(staff_season),
        "stadium": stadium_summary(store, store.stadium_by_id[sid]), "opponent_code": opp,
        "opponent_name": store.team_name(opp), "opponent_lhb_share": _f(100 * lhb_share) if lhb is not None else None,
        "games": games, "workload_known": apps is not None,
        "relievers": sorted(relievers, key=lambda r: (["closer", "setup", "middle", "long", "depth", "rest"].index(r["slot"]), -(r["score"] or 0))),
        "starters": sorted([r for r in rows if r["role"] == "SP"], key=lambda r: -(r["stuff_here"] or 0)),
    }
