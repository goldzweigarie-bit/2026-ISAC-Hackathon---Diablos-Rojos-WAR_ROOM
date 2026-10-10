"""Download a season's schedule for our team from the MLB Stats API (which carries the LMB, sportId=23).

Usage:
    python scripts/fetch_schedule.py --season 2027
    python scripts/fetch_schedule.py --season 2027 --team MEX

Writes data/schedule/<season>.csv in the format the app reads. Run it again during the season to refresh
scores; the app picks the file up on restart or after POST /api/admin/reload.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--team", default=None, help="Team code from stadiums.json (default: our team)")
    args = parser.parse_args()

    stadiums = json.loads((DATA / "reference" / "stadiums.json").read_text(encoding="utf-8"))["stadiums"]
    config = json.loads((DATA / "reference" / "app_config.json").read_text(encoding="utf-8"))
    team_code = args.team or config["our_team_code"]
    by_code = {s["team_code"]: s for s in stadiums}
    by_team_id = {s["statsapi_team_id"]: s for s in stadiums}
    by_venue_id = {s["statsapi_venue_id"]: s for s in stadiums}
    if team_code not in by_code:
        sys.exit(f"Unknown team code {team_code}")

    url = (
        "https://statsapi.mlb.com/api/v1/schedule?sportId=23&gameType=R"
        f"&season={args.season}&teamId={by_code[team_code]['statsapi_team_id']}"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        payload = json.load(resp)

    rows = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            away = by_team_id.get(game["teams"]["away"]["team"]["id"])
            home = by_team_id.get(game["teams"]["home"]["team"]["id"])
            if not away or not home:
                print("Skipping game with unknown team:", game.get("gamePk"), file=sys.stderr)
                continue
            venue = by_venue_id.get(game.get("venue", {}).get("id"))
            rows.append({
                "season": args.season,
                "date": day["date"],
                "away_code": away["team_code"],
                "home_code": home["team_code"],
                "away_score": game["teams"]["away"].get("score", ""),
                "home_score": game["teams"]["home"].get("score", ""),
                "status": game.get("status", {}).get("detailedState", ""),
                "stadium_id": venue["id"] if venue and venue["id"] != home["id"] else "",
            })

    out = DATA / "schedule" / f"{args.season}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["season"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} games to {out}")


if __name__ == "__main__":
    main()
