"""FastAPI app: JSON API under /api, and the built frontend (frontend/dist) served at / when present."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import bullpen, services
from .store import Store

app = FastAPI(title="Diablos Stuff+ API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
store = Store()


def _season(season: int | None) -> int:
    if season is None:
        return store.current_season
    if season not in store.seasons and season not in store.schedules:
        raise HTTPException(404, f"Season {season} not loaded")
    return season


def _stadium(sid: str) -> str:
    if sid not in store.stadium_by_id:
        raise HTTPException(404, f"Unknown stadium {sid}")
    return sid


@app.get("/api/meta")
def meta():
    model_name = getattr(store.model, "name", "trained")
    return {
        "our_team_code": store.config["our_team_code"], "our_team_name": store.team_name(store.config["our_team_code"]),
        "home_stadium_id": store.config["home_stadium_id"], "seasons": store.seasons,
        "schedule_seasons": sorted(store.schedules), "current_season": store.current_season,
        "paper_url": os.environ.get("PAPER_URL") or store.config.get("paper_url") or None,
        "model": model_name, "synthetic": bool(store.meta.get("synthetic")),
        "capabilities": store.meta.get("capabilities", {}),
    }


@app.get("/api/stadiums")
def stadiums():
    return services.list_stadiums(store)


@app.get("/api/stadiums/{sid}")
def stadium(sid: str, season: int | None = None):
    return services.stadium_detail(store, _stadium(sid), _season(season))


@app.get("/api/stadiums/{sid}/leaderboard")
def stadium_leaderboard(sid: str, season: int | None = None, role: str | None = None,
                        limit: int = Query(50, le=500), min_pitches: int | None = None):
    return services.leaderboard(store, _stadium(sid), _season(season), role, limit, min_pitches)


@app.get("/api/stadiums/{sid}/pitchers/{pid}")
def stadium_projection(sid: str, pid: str, season: int | None = None, aim_x: float = 0.0, aim_z: float = 2.5):
    head = services.pitcher_header(store, pid, season)
    if head is None:
        raise HTTPException(404, "Unknown pitcher")
    out = services.projection(store, _stadium(sid), pid, head["season"], aim_x, aim_z)
    if out is None:
        raise HTTPException(404, "Not enough pitches for this pitcher")
    return out


@app.get("/api/pitchers/{pid}")
def pitcher(pid: str, season: int | None = None):
    out = services.pitcher_profile(store, pid, season)
    if out is None:
        raise HTTPException(404, "Unknown pitcher")
    return out


@app.get("/api/search")
def search(q: str = "", limit: int = 8):
    return store.search(q, limit)


@app.get("/api/schedule")
def schedule(season: int | None = None):
    s = season or (max(store.schedules) if store.schedules else store.current_season)
    return services.schedule(store, s)


@app.get("/api/bullpen")
def bullpen_recs(on: date | None = None, season: int | None = None):
    s = season or (max(store.schedules) if store.schedules else store.current_season)
    if on is None:
        sched = store.schedules.get(s)
        today = date.today()
        on = today if sched is None or str(today) <= sched["date"].max() else date.fromisoformat(sched["date"].max())
    return bullpen.recommend(store, on, s)


@app.get("/api/free-agents")
def free_agents(status: str = "all", role: str | None = None, throws: str | None = None,
                sort: str = "home", limit: int = Query(50, le=500)):
    return services.free_agents(store, status, role, throws, sort, limit)


@app.get("/api/methodology")
def methodology():
    return {
        "model": getattr(store.model, "name", "trained"),
        "validation": store.validation, "altitude_study": store.altitude_study,
        "paper_url": os.environ.get("PAPER_URL") or store.config.get("paper_url") or None,
        "data": {k: store.meta.get(k) for k in ("seasons", "rows", "capabilities", "synthetic", "source_files")},
        "rho_ref": store.rho_ref,
    }


@app.post("/api/admin/reload")
def reload_data():
    store.load()
    return {"ok": True, "seasons": store.seasons, "schedule_seasons": sorted(store.schedules)}


# ------------------------------------------------------------------------------ built frontend (optional)
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        f = DIST / full_path
        return FileResponse(f if full_path and f.is_file() else DIST / "index.html")
