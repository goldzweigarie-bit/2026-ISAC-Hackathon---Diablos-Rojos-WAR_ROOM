import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.physics import G_FT_S2, aim_velocity, air_density, at_density, flight, movement_inches, to_sea_level


def test_density_drops_with_altitude():
    assert air_density(2232, 19) / air_density(0, 25) == pytest.approx(0.78, abs=0.02)


def test_sea_level_round_trip():
    ax, ay, az = -12.0, 26.0, -15.0
    rho_obs, rho_ref = 0.92, 1.18
    sl = to_sea_level(ax, ay, az, rho_obs, rho_ref)
    back = at_density(*sl, rho_obs, rho_ref)
    assert np.allclose(back, (ax, ay, az))


def test_less_movement_at_altitude():
    t = 0.40
    sl = (-15.0, 25.0, 22.0)  # magnus x, drag, magnus z at reference density
    hb_sea, ivb_sea = movement_inches(sl[0], sl[2], t)
    hb_cdmx, ivb_cdmx = movement_inches(sl[0] * 0.78, sl[2] * 0.78, t)
    assert abs(hb_cdmx) < abs(hb_sea) and ivb_cdmx < ivb_sea


def test_aim_hits_target():
    ax, ay, az = -10.0, 25.0, 15.0 - G_FT_S2
    vx, vz = aim_velocity(-1.5, 50, 5.8, 5, -135, -5, ax, ay, az, 0.3, 2.2)
    f = flight(-1.5, 50, 5.8, vx, -135, vz, ax, ay, az)
    assert f["px"] == pytest.approx(0.3, abs=1e-6) and f["pz"] == pytest.approx(2.2, abs=1e-6)
    assert 0.35 < f["t"] < 0.45


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_api_core(client):
    meta = client.get("/api/meta").json()
    assert meta["our_team_code"] == "MEX"
    stadiums = client.get("/api/stadiums").json()
    assert len(stadiums) == 20
    lb = client.get("/api/stadiums/harp-helu/leaderboard?limit=5").json()
    assert len(lb["rows"]) == 5
    assert lb["rows"][0]["stuff_plus"] >= lb["rows"][-1]["stuff_plus"]
    pid = lb["rows"][0]["pitcher_id"]
    proj = client.get(f"/api/stadiums/harp-helu/pitchers/{pid}?aim_x=0&aim_z=2.5").json()
    p = proj["pitches"][0]
    assert p["sea"]["px"] == pytest.approx(0, abs=1e-3)
    assert abs(p["here"]["ivb"]) <= abs(p["sea"]["ivb"]) + 1e-6
    assert client.get(f"/api/pitchers/{pid}").status_code == 200
    assert client.get("/api/pitchers/nope").status_code == 404


def test_bullpen_and_free_agents(client):
    b = client.get("/api/bullpen?on=2026-06-01").json()
    assert b["available"] and b["opponent_code"] == "LEO"
    slots = [r["slot"] for r in b["relievers"]]
    assert "closer" in slots
    fa = client.get("/api/free-agents?status=fa").json()
    assert all(r["status"] == "FA" for r in fa["rows"])
    signed = client.get("/api/free-agents?status=signed").json()
    assert all(r["status"] not in ("FA", "MEX") for r in signed["rows"])
