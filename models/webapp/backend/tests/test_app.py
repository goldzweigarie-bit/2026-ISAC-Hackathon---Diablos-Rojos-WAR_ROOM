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
def client(app_main):
    return TestClient(app_main.app)


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


# ------------------------------------------------------------------ traductor: de dónde sale el Stuff+
from conftest import API2, tabla_stuff_falsa  # noqa: E402


def _recargar(client, tabla):
    API2["stuff_plus_por_pitcher_tipo"] = tabla
    r = client.post("/api/admin/reload")
    assert r.status_code == 200
    return r.json()


def test_sin_tabla_en_api2_usa_provisional(client):
    out = _recargar(client, None)
    assert out["model"]["source"] == "provisional"
    assert client.get("/api/meta").json()["model"] == "placeholder"


def test_con_tabla_en_api2_usa_el_modelo_por_nivel(client, app_main):
    out = _recargar(client, tabla_stuff_falsa())
    assert out["model"]["source"] == "api2" and "v-prueba" in out["model"]["name"]
    meta = client.get("/api/meta").json()
    assert meta["model"] != "placeholder"
    # cada parque toma la columna de su nivel: CDMX ~110, Monterrey (530 m) ~100, Chihuahua (1440 m) ~105
    def nivel_medio(sid):
        rows = client.get(f"/api/stadiums/{sid}/leaderboard?limit=500&min_pitches=0").json()["rows"]
        return np.mean([r["stuff_plus"] for r in rows])
    assert nivel_medio("harp-helu") == pytest.approx(110, abs=1)
    assert nivel_medio("monterrey") == pytest.approx(100, abs=1)
    assert nivel_medio("chihuahua") == pytest.approx(105, abs=1)
    assert app_main.store.levels_interpolated == []


def test_sin_columna_media_interpola_por_densidad(client, app_main):
    _recargar(client, tabla_stuff_falsa(con_media=False))
    assert app_main.store.levels_interpolated == ["Medium Altitude"]
    rows = client.get("/api/stadiums/chihuahua/leaderboard?limit=500&min_pitches=0").json()["rows"]
    assert 100 < np.mean([r["stuff_plus"] for r in rows]) < 110


def test_pantallas_responden_con_el_modelo(client):
    _recargar(client, tabla_stuff_falsa())
    pid = client.get("/api/stadiums/harp-helu/leaderboard?limit=1").json()["rows"][0]["pitcher_id"]
    prof = client.get(f"/api/pitchers/{pid}").json()
    assert len(prof["by_park"]) == 20 and prof["arsenal"]
    proj = client.get(f"/api/stadiums/harp-helu/pitchers/{pid}").json()
    assert proj["pitches"][0]["here"]["stuff_plus"] is not None
    assert client.get("/api/bullpen?on=2026-06-01").json()["available"]
    assert client.get("/api/free-agents?status=fa").json()["rows"]
    meth = client.get("/api/methodology").json()
    assert meth["altitude_levels"]["harp-helu"] == "Extreme Altitude"


def test_datos_anonimizados_como_el_api1_real(tmp_path):
    """El API 1 real no trae fecha, estadio, equipos ni nombres: la app debe arrancar y responder igual."""
    import shutil
    from app.store import Store
    from conftest import DATA_PRUEBA, PITCHEOS
    from fastapi.testclient import TestClient

    anon = PITCHEOS.drop(["Date", "Stadium", "PitcherTeam", "BatterTeam", "Pitcher"])
    for carpeta in ("reference", "schedule"):
        shutil.copytree(DATA_PRUEBA / carpeta, tmp_path / carpeta)

    class FuentesAnon:
        estado: dict = {}
        def pitcheos(self): return anon
        def tabla_api2(self, nombre): return tabla_stuff_falsa() if nombre == "stuff_plus_por_pitcher_tipo" else None
        def metadatos_api2(self): return {}

    from app import main
    original = main.store
    main.store = Store(tmp_path, fuentes=FuentesAnon())
    try:
        c = TestClient(main.app)
        meta = c.get("/api/meta").json()
        assert meta["capabilities"]["has_dates"] is False and meta["capabilities"]["has_teams"] is False
        lb = c.get("/api/stadiums/harp-helu/leaderboard?limit=5").json()["rows"]
        assert len(lb) == 5
        pid = lb[0]["pitcher_id"]
        assert c.get(f"/api/pitchers/{pid}").status_code == 200
        assert c.get(f"/api/stadiums/harp-helu/pitchers/{pid}").status_code == 200
        assert c.get("/api/bullpen?on=2026-06-01").status_code == 200
        assert c.get("/api/free-agents").status_code == 200
        study = c.get("/api/methodology").json()["altitude_study"]
        assert study["grouped_by"] == "altitude_category" and len(study["rows"]) == 3
    finally:
        main.store = original
