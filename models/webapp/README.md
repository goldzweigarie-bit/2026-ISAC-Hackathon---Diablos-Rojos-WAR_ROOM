# Diablos Stuff+

Web app for the Diablos Rojos hackathon: altitude-adjusted Stuff+ for every LMB ballpark.

- **Home**: map of the 20 LMB parks (click one), search by pitcher ID or park name, the Diablos schedule calendar, the little diablo (bullpen recommendation for the selected date's series), and a free-agent lookup.
- **Ballpark page**: strike zone (catcher's view) showing where each pitch of the chosen pitcher ends up at sea level vs. this park when thrown with the identical release (click the zone to move the aim point), movement plot, and the crown: every pitcher ranked by projected Stuff+ at that altitude.
- **Pitcher profile**: arsenal, Stuff+ at each of the 20 parks, recent workload. Reached from search or by clicking any ranking row.
- **Free agents**: pitchers not on the Diablos, marked as free agent or on another team, ranked by projected Stuff+ at Harp Helú and by how much they'd improve our staff.
- **Methodology**: model pipeline, validation (from your training pipeline), the empirical altitude study, and a button to the paper.
- ES / EN toggle everywhere.

## Run it

**Without Node** (the built page is in `frontend/dist`): run only the backend steps and open http://localhost:8000. On a Mac use `python3` instead of `python`.

```bash
# backend (Python 3.10+)
cd models/webapp/backend
pip install -r requirements.txt
python scripts/generate_synthetic.py   # only while there is no real data
python scripts/ingest.py
uvicorn app.main:app --reload --port 8000

# frontend (Node 18+), in another terminal
cd models/webapp/frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

For a single server: `cd models/webapp/frontend && npm run build`, then uvicorn serves the built app at http://localhost:8000.

## Swapping in the real data

1. Delete `backend/data/raw/synthetic_*.parquet` and `backend/data/rosters/2026.csv`, put the real pitch files (CSV or Parquet, any number of seasons) in `backend/data/raw/`.
2. If a column has a different name, add it to `backend/data/reference/column_map.json`. Nothing else changes.
3. If stadium names don't match, `ingest.py` prints them; add them to `aliases` in `backend/data/reference/stadiums.json`.
4. Replace the keys in `altitude_category_to_m` (in `app_config.json`) with the real `altitude_category` values. Only used for pitches without a stadium.
5. Run `python scripts/ingest.py`, then restart the server (or `POST /api/admin/reload`).

**Anonymized hackathon file**: works as is. Without `Date`, `Stadium`, team or name columns the map, parks, rankings, profiles and altitude study all run; the bullpen workload and team-based features wait for the final data. A roster file fixes that too.

**Rosters / free agents**: `backend/data/rosters/<season>.csv` with `season,pitcher_id,name,team_code,role`. `team_code` is a code from `stadiums.json` (MEX, PUE, …) or `FA`. The latest season's roster decides who is a free agent.

## Plugging in the trained model

Save any object with `predict(DataFrame) -> array` (sklearn Pipeline, or a wrapper that combines the four sub-models) to `backend/data/processed/stuff_model.joblib`. It receives the columns in `FEATURE_COLUMNS` (`backend/app/model.py`), evaluated at each park's air density, and should return higher = better. The app converts that to 100 + 10·z per park and season. Until the file exists a hand-weighted placeholder runs and the header says so.

Validation metrics: write `backend/data/processed/validation_metrics.json`:

```json
{"metrics": [{"name": "Stuff+ vs next-season RV/100 (r)", "value": 0.41, "split": "temporal holdout 2026"}],
 "submodels": [{"name": "Whiff", "target": "is_whiff | swing", "metric": "AUC", "value": 0.71}],
 "notes": "GroupKFold by pitcher, 5 folds."}
```

Paper link: set `paper_url` in `app_config.json` (or the `PAPER_URL` environment variable).

## 2027 season

```bash
python scripts/fetch_schedule.py --season 2027   # pulls from the MLB Stats API, which carries the LMB
```
Add 2027 pitch files to `data/raw/`, a 2027 roster, re-run `ingest.py`. The calendar, bullpen and rankings pick up the newest season automatically.

## Data notes

- The 2026 Diablos schedule comes from the MLB Stats API (sportId 23). It lists 97 games (68-29) while the league's official count is 93 (64-29), probably resumed or duplicated games. Check it against the official calendar before presenting.
- Harp Helú (2,232 m) and Hermanos Serdán (2,192 m) altitudes come from the LMB's published list; the other altitudes, coordinates and game temperatures are approximate. All live in `stadiums.json`.
- Physics: Magnus and drag accelerations scale with air density (`backend/app/physics.py`). Every pitch is converted to a sea-level equivalent and projected to each park. Humidity is ignored.
- Coordinates assume x points to the first-base side from the catcher's view; the fastball arm-side sign is detected from the data.
- Map: Natural Earth admin-1 (public domain).

## Tests

```bash
cd models/webapp/backend && python -m pytest
```
