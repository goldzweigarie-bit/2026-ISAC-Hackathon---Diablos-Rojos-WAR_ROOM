# Stuff+ Model — Diablos Rojos del México (Hackathon ISAC 2026)

Sistema de evaluación pitch-by-pitch que estima la calidad esperada de cada lanzamiento

> **Escala:** `Stuff+ = 100 + 10 × z(score_pitch)` — 100 = promedio LMB ajustado por temporada y estadio.

## Equipo

|Nombre | GitHub |
|---|---|
| Fernando Arellano | @FerArGo56 |
| Arié Goldzweig | @goldzweigarie-bit |
| Mikel Loret | @loretmikel |
| Meyer Hemilson | @Meyer03 |

## Correr todo (APIs + web app)

```bash
bash apis/instalar.sh        # una vez por compu (datos en ~/Desktop/hackathon, FUERA del repo)
bash apis/iniciar_todo.sh    # prende API 1, API 2 y la web app en http://localhost:8002
```

Cada modelo sube sus resultados al API 2 y la web app los toma de ahí. Detalle en [`apis/README.md`](apis/README.md). **El repo es público: datos y llaves nunca se suben.**

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
├── apis/                      ← API 1 (datos), API 2 (resultados) y scripts para correr todo
├── models/webapp/             ← traductor + web app (React ya compilada)
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
