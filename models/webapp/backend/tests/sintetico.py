"""SOLO PARA PRUEBAS: genera pitcheos sintéticos con la misma forma que entrega el API 1.

La app nunca usa estos datos: las pruebas (test_app.py) los pasan al traductor en lugar del API 1.

Generate a synthetic, physically consistent LMB pitch dataset shaped like the final Diablos data.

It mimics the columns of stuff_plus_data_dictionary.csv plus the fields the final (non-anonymized) data should
add: Date, Stadium, PitcherTeam, BatterTeam and Pitcher. Accelerations scale with each park's air density, so the
altitude analysis in the app recovers a real (synthetic) effect. Diablos 2026 games follow the real schedule.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.physics import G_FT_S2, air_density, flight, movement_inches  # noqa: E402

DATA = ROOT / "data"
RNG = np.random.default_rng(2026)
RHO_SL = float(air_density(0, 25))

PITCH_TEMPLATES = {
    # velo mph, IVB in, arm-side HB in, spin rpm (sea level means)
    "Four-Seam": (92.5, 15.5, 7.5, 2250),
    "Sinker": (91.5, 7.5, 14.0, 2150),
    "Cutter": (87.5, 8.0, -2.5, 2350),
    "Slider": (83.5, 1.5, -5.5, 2450),
    "Curveball": (78.0, -9.0, -6.5, 2550),
    "Changeup": (84.0, 6.5, 13.0, 1750),
    "Splitter": (85.0, 3.0, 9.0, 1450),
}


def make_pitchers(stadiums):
    teams = [s["team_code"] for s in stadiums]
    pitchers = []
    pid = 10000
    for team in teams:
        for role, n in (("SP", 6), ("RP", 11)):
            for _ in range(n):
                pid += RNG.integers(1, 40)
                pitchers.append({"pitcher_id": f"pitcher_{pid:05d}", "team_2026": team, "role": role})
    # pitchers who only appear in 2025: they are the free agents of 2026
    for _ in range(45):
        pid += RNG.integers(1, 40)
        pitchers.append({"pitcher_id": f"pitcher_{pid:05d}", "team_2026": "FA",
                         "role": "SP" if RNG.random() < 0.3 else "RP"})
    df = pd.DataFrame(pitchers)
    df["throws"] = np.where(RNG.random(len(df)) < 0.7, "Right", "Left")
    df["talent"] = RNG.normal(0, 1, len(df))
    # 2025 team: most stay, some moved; FAs were on a random team in 2025
    moved = RNG.random(len(df)) < 0.15
    df["team_2025"] = np.where(moved | (df.team_2026 == "FA"), RNG.choice(teams, len(df)), df.team_2026)
    return df


def make_arsenals(pitchers):
    rows = []
    for p in pitchers.itertuples():
        primary = "Four-Seam" if RNG.random() < 0.72 else "Sinker"
        pool = ["Slider", "Changeup", "Curveball", "Cutter", "Splitter"]
        n_sec = RNG.integers(3, 5) if p.role == "SP" else RNG.integers(1, 3)
        secondaries = list(RNG.choice(pool, n_sec, replace=False, p=[0.34, 0.26, 0.18, 0.12, 0.10]))
        types = [primary] + secondaries
        if p.role == "SP" and primary == "Four-Seam" and RNG.random() < 0.35:
            types.append("Sinker")
        usage = RNG.dirichlet(np.ones(len(types)) * 2)
        usage[0] += 0.35
        usage /= usage.sum()
        velo_shift = 0.9 * p.talent + RNG.normal(0, 1.2) + (0.8 if p.role == "RP" else 0)
        for t, u in zip(types, usage):
            v, ivb, hb, spin = PITCH_TEMPLATES[t]
            rows.append({
                "pitcher_id": p.pitcher_id, "pitch_type": t, "usage": u,
                "velo": v + velo_shift + RNG.normal(0, 0.8),
                "ivb": ivb + RNG.normal(0, 2.4) + 0.6 * p.talent * (1 if t == "Four-Seam" else -0.3),
                "hb_arm": hb + RNG.normal(0, 2.6) + 0.4 * p.talent * np.sign(hb),
                "spin": spin + RNG.normal(0, 160) + 60 * p.talent,
            })
    return pd.DataFrame(rows)


def release_profile(pitchers):
    n = len(pitchers)
    side_sign = np.where(pitchers.throws == "Right", -1.0, 1.0)  # x toward 1B from catcher view
    return pd.DataFrame({
        "pitcher_id": pitchers.pitcher_id,
        "rel_height": RNG.normal(5.85, 0.3, n),
        "rel_side": side_sign * np.abs(RNG.normal(1.9, 0.45, n)),
        "extension": RNG.normal(6.3, 0.35, n) + 0.15 * pitchers.talent.to_numpy(),
    })


def build_calendar(season, stadiums, mex_schedule):
    """Games for every team: Diablos follow the real schedule in 2026, everyone else is paired randomly."""
    codes = [s["team_code"] for s in stadiums]
    start, end = (date(2026, 4, 16), date(2026, 8, 6)) if season == 2026 else (date(2025, 4, 11), date(2025, 8, 3))
    games = []
    day = start
    block_pairs = None
    block_day = 0
    while day <= end:
        if day.weekday() == 0:  # Monday off
            day += timedelta(days=1)
            continue
        if block_pairs is None or block_day == 3:
            others = [c for c in codes if not (season == 2026 and c == "MEX")]
            RNG.shuffle(others)
            block_pairs = [(others[i], others[i + 1]) for i in range(0, len(others) - 1, 2)]
            block_day = 0
        for away, home in block_pairs:
            games.append({"date": day, "away": away, "home": home})
        block_day += 1
        day += timedelta(days=1)
    if season == 2026:
        for g in mex_schedule.itertuples():
            if g.status == "Postponed":
                continue
            games.append({"date": date.fromisoformat(g.date), "away": g.away_code, "home": g.home_code})
    return pd.DataFrame(games).sort_values("date").reset_index(drop=True)


def simulate_season(season, pitchers, arsenals, releases, stadiums, calendar):
    by_code = {s["team_code"]: s for s in stadiums}
    team_col = f"team_{season}"
    ars = {pid: g for pid, g in arsenals.groupby("pitcher_id")}
    rel = releases.set_index("pitcher_id")
    staff = {}
    for team, g in pitchers.groupby(team_col):
        if team == "FA":
            continue
        staff[team] = {"SP": list(g[g.role == "SP"].pitcher_id), "RP": list(g[g.role == "RP"].pitcher_id)}
    rotation_idx = {t: 0 for t in staff}
    last_used: dict[str, list[date]] = {}
    throws = pitchers.set_index("pitcher_id").throws
    talent = pitchers.set_index("pitcher_id").talent
    batters = {t: [(f"batter_{abs(hash((t, i, season))) % 90000 + 10000:05d}", "Left" if RNG.random() < 0.38 else "Right")
                   for i in range(13)] for t in staff}

    chunks = []
    for gi, game in enumerate(calendar.itertuples()):
        park = by_code[game.home]
        rho = float(air_density(park["altitude_m"], park["typical_temp_c"] + RNG.normal(0, 2)))
        game_id = f"game_{season % 100:02d}{gi:04d}"
        for pitching_team, batting_team, half in ((game.home, game.away, "Top"), (game.away, game.home, "Bottom")):
            s = staff[pitching_team]
            starter = s["SP"][rotation_idx[pitching_team] % len(s["SP"])]
            rotation_idx[pitching_team] += 1
            plan = [(starter, int(RNG.normal(88, 10)))]
            rested = [p for p in s["RP"] if not (len(last_used.get(p, [])) >= 2
                      and last_used[p][-1] == game.date - timedelta(days=1)
                      and last_used[p][-2] == game.date - timedelta(days=2))]
            RNG.shuffle(rested)
            for p in rested[: RNG.integers(2, 5)]:
                plan.append((p, int(np.clip(RNG.normal(18, 6), 6, 35))))
            inning = 1
            for pid, n in plan:
                last_used.setdefault(pid, []).append(game.date)
                a = ars[pid]
                types = RNG.choice(a.pitch_type.to_numpy(), n, p=a.usage.to_numpy())
                prof = a.set_index("pitch_type").loc[types]
                r = rel.loc[pid]
                arm = -1.0 if throws[pid] == "Right" else 1.0  # arm side in x for this pitcher
                velo = prof.velo.to_numpy() + RNG.normal(0, 0.9, n)
                ivb_sl = prof.ivb.to_numpy() + RNG.normal(0, 1.4, n)
                hb_sl = prof.hb_arm.to_numpy() + RNG.normal(0, 1.5, n)
                spin = prof.spin.to_numpy() + RNG.normal(0, 70, n)
                t_ref = 0.372 * 92 / velo
                k = rho / RHO_SL
                ax_mag = arm * hb_sl / 12 * 2 / t_ref ** 2 * k
                az_mag = ivb_sl / 12 * 2 / t_ref ** 2 * k
                v0_fts = velo * 5280 / 3600
                ay = (0.0045 * v0_fts ** 2) * 0.28 * k  # drag decel, sea level ~ 30 ft/s^2 for 92 mph
                ext = r.extension + RNG.normal(0, 0.08, n)
                y_rel = 60.5 - ext
                x_rel = r.rel_side + RNG.normal(0, 0.1, n)
                z_rel = r.rel_height + RNG.normal(0, 0.08, n)
                # aim at a location, then back out velocities at y = 50 (the 9-parameter reference)
                tx = RNG.normal(0.0, 0.9, n)
                tz = RNG.normal(2.4, 0.85, n)
                vy0 = -v0_fts * 0.995
                ax, az = ax_mag, az_mag - G_FT_S2
                # time from release to y=50 at roughly constant vy
                dt = (y_rel - 50) / -vy0
                t_total = (y_rel - Y_PLATE) / -vy0
                vx_rel = (tx - x_rel - 0.5 * ax * t_total ** 2) / t_total
                vz_rel = (tz - z_rel - 0.5 * az * t_total ** 2) / t_total
                x0 = x_rel + vx_rel * dt + 0.5 * ax * dt ** 2
                z0 = z_rel + vz_rel * dt + 0.5 * az * dt ** 2
                vx0 = vx_rel + ax * dt
                vz0 = vz_rel + az * dt
                vy0_50 = vy0 + ay * dt
                f = flight(x0, 50.0, z0, vx0, vy0_50, vz0, ax, ay, az)
                hb_obs, ivb_obs = movement_inches(ax_mag, az_mag, f["t"])
                px, pz = f["px"], f["pz"]
                in_zone = (np.abs(px) < 0.83) & (pz > 1.5) & (pz < 3.5)
                # outcome model: better stuff at THIS park -> more whiffs
                q = (0.12 * (velo - 88) + 0.05 * (np.abs(hb_obs) + np.abs(ivb_obs - 5) - 12) * 0.5
                     + 0.35 * talent[pid] + RNG.normal(0, 0.5, n))
                batter = [batters[batting_team][i % 13] for i in RNG.integers(0, 13, n)]
                bats = np.array([b[1] for b in batter])
                same_side = bats == throws[pid]
                swing = RNG.random(n) < np.where(in_zone, 0.66, 0.29)
                whiff = swing & (RNG.random(n) < 1 / (1 + np.exp(-(-1.55 + 0.45 * q + 0.15 * same_side))))
                contact = swing & ~whiff
                in_play = contact & (RNG.random(n) < 0.47)
                called = ~swing & in_zone & (RNG.random(n) < 0.92)
                call = np.where(whiff, "StrikeSwinging", np.where(in_play, "InPlay", np.where(contact, "FoulBall",
                                np.where(called, "StrikeCalled", "BallCalled"))))
                gb = in_play & (RNG.random(n) < np.clip(0.44 - 0.012 * ivb_obs, 0.2, 0.7))
                hit_type = np.where(in_play, np.where(gb, "GroundBall", np.where(RNG.random(n) < 0.5, "FlyBall", "LineDrive")), "")
                exit_speed = np.where(in_play, RNG.normal(88, 10, n) - 1.5 * q, np.nan)
                chunk = pd.DataFrame({
                    "year": season, "Date": game.date.isoformat(), "Stadium": park["venue_name"],
                    "PitchUID": [f"{game_id}-{half}-{pid}-{i}" for i in range(n)],
                    "game_anon_id": game_id, "pitcher_anon_id": pid, "Pitcher": pid,
                    "PitcherTeam": pitching_team, "BatterTeam": batting_team,
                    "batter_anon_id": [b[0] for b in batter], "catcher_anon_id": f"catcher_{hash(pitching_team) % 900 + 100:05d}",
                    "PitcherThrows": throws[pid], "BatterSide": bats,
                    "altitude_category": altitude_bucket(park["altitude_m"]),
                    "AutoPitchType": types, "RelSpeed": velo, "ZoneSpeed": f["plate_speed"],
                    "EffectiveVelo": velo + (ext - 6.3) * 1.5, "SpinRate": spin,
                    "SpinAxis": np.degrees(np.arctan2(ivb_obs, hb_obs)) % 360,
                    "RelHeight": z_rel, "RelSide": x_rel, "Extension": ext,
                    "InducedVertBreak": ivb_obs, "HorzBreak": hb_obs,
                    "VertBreak": ivb_obs - 0.5 * G_FT_S2 * f["t"] ** 2 * 12,
                    "VertApprAngle": f["vaa"], "HorzApprAngle": np.degrees(np.arctan2(f["vx"], -f["vy"])),
                    "ZoneTime": f["t"], "SpeedDrop": velo - f["plate_speed"],
                    "x0": x0, "y0": 50.0, "z0": z0, "vx0": vx0, "vy0": vy0_50, "vz0": vz0,
                    "ax0": ax, "ay0": ay, "az0": az,
                    "PlateLocSide": px, "PlateLocHeight": pz, "in_strike_zone": in_zone.astype(int),
                    "PitchCall": call, "is_swing": swing.astype(int), "is_whiff": whiff.astype(int),
                    "is_contact": contact.astype(int), "is_called_strike": called.astype(int),
                    "is_ball_in_play": in_play.astype(int), "hit_type": hit_type, "ExitSpeed": exit_speed,
                    "Inning": inning, "Top/Bottom": half,
                })
                chunks.append(chunk)
                inning = min(inning + max(1, n // 16), 9)
    return pd.concat(chunks, ignore_index=True)


Y_PLATE = 17 / 12


def altitude_bucket(alt):
    """Las mismas categorías que el dataset real."""
    if alt >= 2000:
        return "Extreme Altitude"
    if alt >= 1000:
        return "Medium Altitude"
    return "No Altitude"


def generar(seasons=(2025, 2026)) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(pitcheos con columnas del API 1, roster 2026). Determinista: misma semilla, mismos datos."""
    stadiums = json.loads((DATA / "reference" / "stadiums.json").read_text(encoding="utf-8"))["stadiums"]
    mex = pd.read_csv(DATA / "schedule" / "2026.csv")
    pitchers = make_pitchers(stadiums)
    arsenals = make_arsenals(pitchers)
    releases = release_profile(pitchers)
    frames = [simulate_season(s, pitchers, arsenals, releases, stadiums, build_calendar(s, stadiums, mex))
              for s in seasons]
    roster = pitchers.rename(columns={"team_2026": "team_code"})[["pitcher_id", "team_code", "role"]].copy()
    roster.insert(1, "name", roster.pitcher_id)
    roster["season"] = 2026
    return pd.concat(frames, ignore_index=True), roster
