"""Bullpen recommendations for the next Diablos series: workload + park-projected Stuff+ + opponent handedness."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .services import _f, stadium_summary
from .store import Store

LEAGUE_SHRINK_SWINGS = 60


def _next_series(sched: pd.DataFrame, as_of: date, ours: str):
    games = sched[~sched.status.astype(str).str.lower().isin(["postponed", "cancelled"])].copy()
    games["d"] = pd.to_datetime(games["date"]).dt.date
    upcoming = games[games.d >= as_of].sort_values("d")
    if upcoming.empty:  # season over: show the final series
        upcoming = games[games.d == games.d.max()]
    first = upcoming.iloc[0]
    opp = lambda r: r.away_code if r.home_code == ours else r.home_code  # noqa: E731
    series = [first]
    for r in upcoming.iloc[1:].itertuples(index=False):
        if opp(r) == opp(first) and r.stadium_id == first.stadium_id and (r.d - series[-1].d).days <= 2:
            series.append(pd.Series(r._asdict()))
        else:
            break
    return series, opp(first)


def recommend(store: Store, as_of: date, season: int) -> dict:
    ours = store.config["our_team_code"]
    rules = store.config.get("bullpen", {})
    sched = store.schedules.get(season)
    if sched is None or sched.empty:
        return {"available": False, "reason": "no_schedule"}
    series, opp = _next_series(sched, as_of, ours)
    game_day = series[0]["d"]
    sid = series[0]["stadium_id"]
    staff_season = season if (store.pitchers.season == season).any() else store.current_season
    staff = store.pitchers[(store.pitchers.season == staff_season) & (store.pitchers.team_code == ours)]
    pp = store.pitcher_park[(store.pitcher_park.season == staff_season) & (store.pitcher_park.stadium_id == sid)].set_index("pitcher_id")

    # league platoon baseline
    sw = store.pitchers[store.pitchers.season == staff_season]
    league_l = sw.wh_l.sum() / max(sw.sw_l.sum(), 1) if "wh_l" in sw else np.nan
    league_r = sw.wh_r.sum() / max(sw.sw_r.sum(), 1) if "wh_r" in sw else np.nan
    lhb = None
    if store.team_hand is not None:
        th = store.team_hand[store.team_hand.batter_team == opp]
        if len(th):
            lhb = float(th.sort_values("season").lhb_share.iat[-1])
    lhb_share = lhb if lhb is not None else 0.38

    apps = None
    if store.appearances is not None:
        apps = store.appearances[(store.appearances.date < pd.Timestamp(game_day))
                                 & (store.appearances.date >= pd.Timestamp(game_day - timedelta(days=7)))]

    rows = []
    for p in staff.itertuples():
        sp_here = pp.loc[p.pitcher_id, "stuff_plus"] if p.pitcher_id in pp.index else np.nan
        neutral = pp.loc[p.pitcher_id, "stuff_neutral"] if p.pitcher_id in pp.index else np.nan
        if np.isnan(sp_here):
            continue
        reasons = []
        status = "available"
        last1 = last3 = last7 = 0
        pitched_yday = pitched_2d = False
        if apps is not None:
            a = apps[apps.pitcher_id == p.pitcher_id]
            days_ago = (pd.Timestamp(game_day) - a.date).dt.days
            last1 = int(a.pitches[days_ago == 1].sum())
            last3 = int(a.pitches[days_ago <= 3].sum())
            last7 = int(a.pitches.sum())
            pitched_yday = bool((days_ago == 1).any())
            pitched_2d = pitched_yday and bool((days_ago == 2).any())
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
            if p.role == "SP" and last7 > 0:
                status = "rest"
                reasons.append({"code": "starter_in_rotation"})
        # platoon: shrunk whiff rates vs L / R, mixed by the opponent's lineup
        edge = 0.0
        if "wh_l" in staff:
            wl = (p.wh_l + LEAGUE_SHRINK_SWINGS * league_l) / (p.sw_l + LEAGUE_SHRINK_SWINGS)
            wr = (p.wh_r + LEAGUE_SHRINK_SWINGS * league_r) / (p.sw_r + LEAGUE_SHRINK_SWINGS)
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
            "pitcher_id": p.pitcher_id, "name": p.name, "throws": p.throws, "role": p.role,
            "stuff_here": _f(sp_here), "stuff_neutral": _f(neutral), "platoon_edge": _f(edge),
            "score": _f(score * mult), "status": status, "reasons": reasons,
            "pitches_last_1d": last1, "pitches_last_3d": last3, "pitches_last_7d": last7,
            "pitches_per_game": _f(p.pitches_per_game),
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
