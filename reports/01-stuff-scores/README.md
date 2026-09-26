# Entregable 1 — Stuff+ Scores por Pitch, Pitcher y Arsenal

## Contenido requerido (checklist)

- [ ] Score Stuff+ individualizado por lanzamiento (Stuff+, Location+, Pitching+)
- [ ] Agregación por pitcher y por repertorio: ¿qué arsenal produce el Stuff+ más alto en Harp Helú?
- [ ] Comparación de Stuff+ estimado en CDMX vs. otros estadios de la LMB (cuantificación del efecto altitud)

## Archivos

| Archivo | Descripción |
|---|---|
| `pitcher_scores.csv` | Tabla: pitcher × pitch_type → Stuff+, Location+, Pitching+, N pitches |
| `arsenal_ranking.md` | Ranking de arsenales con mejor Stuff+ en Harp Helú + figuras |
| `altitude_delta.csv` | Delta Stuff+ estimado por pitch shape: Harp Helú vs. nivel del mar |
| `fig1_top_pitches.png` | Distribución de Stuff+ por tipo de pitch |
| `fig2_arsenal_stuff.png` | Heatmap arsenal × Stuff+ |
| `fig3_altitude_effect.png` | Delta Stuff+ por estadio/pitch shape |

## Fuente de los números
- `notebooks/03_model_stuff_plus.ipynb` (scores)
- `notebooks/04_altitude_effect.ipynb` (deltas por estadio)
