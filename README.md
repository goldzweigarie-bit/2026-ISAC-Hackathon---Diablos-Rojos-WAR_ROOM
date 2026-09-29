# Stuff+ Model — Diablos Rojos del México (Hackathon ISAC 2026)

Sistema de evaluación pitch-by-pitch que estima la calidad esperada de cada lanzamiento
(Stuff+, Location+, Pitching+) ajustado por las condiciones físicas del **Harp Helú (2,240 msnm)**,
el estadio de mayor altitud de la LMB.

> **Escala:** `Stuff+ = 100 + 10 × z(score_pitch)` — 100 = promedio LMB ajustado por temporada y estadio.

## Equipo

| Nombre | GitHub |
|---|---|
|Fernando Arellano | @FerArGo56 |
| Arié Goldzweig | @goldzweigarie-bit |
| Mikel Loret| @loretmikel |
| Meyer Hemilson| @Meyer03/github |

## Los 5 Entregables y dónde vive cada uno

| # | Entregable | Carpeta | Estado |
|---|---|---|---|
| 1 | Stuff+ Scores por Pitch, Pitcher y Arsenal | [`reports/01-stuff-scores/`](reports/01-stuff-scores/) | ⬜ |
| 2 | Perfil Físico Ideal para Diablos Rojos | [`reports/02-perfil-fisico-ideal/`](reports/02-perfil-fisico-ideal/) | ⬜ |
| 3 | Recomendaciones Operativas | [`reports/03-recomendaciones-operativas/`](reports/03-recomendaciones-operativas/) | ⬜ |
| 4 | Dashboard Simulador | [`dashboard/`](dashboard/) | ⬜ |
| 5 | Documento Técnico (6–10 págs.) | [`docs/documento-tecnico/`](docs/documento-tecnico/) | ⬜ |

## Estructura del repositorio

```
stuff-plus-diablos/
├── README.md                  ← este archivo
├── CONTRIBUTING.md            ← flujo de trabajo del equipo (branches, PRs)
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/                   ← datos ISAC (NO subir al repo, ver .gitignore)
│   └── processed/             ← datasets feature-engineered (tampoco se suben)
├── notebooks/
│   ├── 01_eda.ipynb           ← exploración de datos pitch-by-pitch
│   ├── 02_feature_engineering.ipynb
│   ├── 03_model_stuff_plus.ipynb
│   ├── 04_altitude_effect.ipynb   ← cuantificación efecto Harp Helú (H1–H4)
│   └── 05_validation.ipynb        ← pitcher/season/park holdout
├── src/
│   ├── data/                  ← carga y limpieza
│   ├── features/              ← features físicas, de arsenal y de contexto
│   ├── models/                ← entrenamiento Stuff+/Location+/Pitching+
│   ├── evaluation/            ← métricas, calibración, SHAP
│   └── visualization/         ← mapas de movimiento, gráficas de informe
├── dashboard/
│   ├── app.py                 ← Streamlit: simulador Stuff+
│   └── components/            ← inputs del coach, comparador altitud, mapa de movimiento
├── reports/                   ← los 3 entregables escritos + figuras
│   ├── 01-stuff-scores/
│   ├── 02-perfil-fisico-ideal/
│   └── 03-recomendaciones-operativas/
├── docs/
│   └── documento-tecnico/     ← entregable 5 (LaTeX/Markdown → PDF)
└── models/                    ← artefactos .pkl/.json (se suben versionados livianos)
```

## Plan de trabajo sugerido

1. **Semana 1:** EDA (`01`), definición de targets (whiff, chase, weak contact, barrel, xRunValue)
2. **Semana 1–2:** Feature engineering (`02`): features físicas + relacionales de arsenal (`velo_diff_vs_fb`, túnel, uso) + contexto (estadio, altitud, count)
3. **Semana 2–3:** Modelado (`03`): XGBoost/LightGBM multi-objetivo → score → normalización a escala 100
4. **Semana 3:** Validación (`05`): pitcher holdout, season holdout, **park holdout** (clave: 25% de la evaluación)
5. **Semana 3–4:** Efecto altitud (`04`) + redacción de entregables 1–3 + dashboard (`app.py`)
6. **Semana 4:** Documento técnico + ensayo de la entrevista de 10 min con el jurado

## Hipótesis a validar (de la convocatoria)

- **H1:** La baja densidad (~20% menor) reduce el break inducido por spin (Magnus) en Harp Helú.
- **H2:** Pitches basados en diferencial de velocidad (changeup) ganan Stuff+ relativo en altitud.
- **H3:** Groundball pitchers son más valiosos en altitud (menos riesgo de jonrón).
- **H4:** "Shape over label": el movimiento observado importa más que el spin rate aislado.

## Referencias clave

- Tango, Lichtman & Dolphin (2007). *The Book*.
- Huang & Hsu (2021). *Big data analytics in baseball: A review*. SAGE Open.
- SABR. *High Altitude Offense*. Baseball Research Journal.
- Alan Nathan (física del béisbol): efecto Magnus y altitud en Coors Field.

## Aviso legal

Los datos de ISAC/LMB son **solo para la competencia** y no se suben a este repositorio.
Ver Consideraciones Técnicas y Éticas de la convocatoria (prohibido uso para apuestas).
