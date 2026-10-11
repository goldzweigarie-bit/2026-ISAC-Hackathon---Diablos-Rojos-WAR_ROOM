# Cómo correr todo (APIs + web app)

```
API 1 :8000 (pitcheos) ───────────────────────────────┐
                                                      ├──→ traductor :8002 ──→ web app (navegador)
Stuff+ / BayesBall ──→ API 2 :8001 (resultados) ──────┘
```

| Carpeta | Qué es |
|---|---|
| `apis/api/` | **API 1**: entrega los pitcheos y las constantes de carreras ([README](api/README.md)) |
| `apis/api2/` | **API 2**: guarda los resultados que suben los modelos ([README](api2/README.md)) |
| `models/webapp/` | **Traductor + web app** ([README](../models/webapp/README.md)) |
| `notebooks/06_StuffPlus.ipynb` | El modelo Stuff+ (XGBoost, Polars). Su **Paso 9** sube los resultados al API 2 |
| `notebooks/03_model_stuff_plus.ipynb` | El modelo bayesiano de resolvabilidad (BayesBall), con `src/models/bayesian_resolvability.py` |
| `apis/instalar.sh` · `apis/iniciar_todo.sh` | Instalar una vez · prender todo |
| `apis/correr_modelos.sh` | Correr los dos modelos con los datos reales y subir sus resultados, sin abrir Jupyter |

## ⚠️ El repo es público

**Los datos y las llaves nunca se suben.** Viven en tu compu, fuera del repo, y el `.gitignore` los bloquea: `*.pkl`, `*.parquet`, `*.csv`, `.env`, `.venv/`, `resultados_api2/`, `logs/`. `instalar.sh` revisa al final que git no vea ninguno.

## 1. Preparar los datos (una vez por compu)

Crea `~/Desktop/hackathon` (fuera del repo) con:

```
~/Desktop/hackathon/
├── stuff_model_df.pkl      ← el dataset de la competencia
└── RunValueEvents.csv      ← constantes wOBA de FanGraphs (Guts!)
```

Si prefieres otra carpeta: `DATOS=/otra/carpeta bash apis/instalar.sh`. El notebook también lee los datos de `~/Desktop/hackathon` (variable `CARPETA` del Paso 0).

## 2. Instalar (una vez por compu, 1-2 minutos)

Desde la raíz del repo:

```bash
bash apis/instalar.sh
```

Hace lo siguiente:
- Crea el entorno `.venv` con Python 3.11 o más nuevo.
- Genera las llaves de los dos APIs.
- Convierte el pickle a Parquet. Es el único paso que usa pandas, y después lo desinstala.
- Corre las pruebas con tus datos.
- Le pasa las llaves al traductor.

## 3. Prender todo

```bash
bash apis/iniciar_todo.sh
```

Prende el API 1, el API 2 y la web app, y abre **http://localhost:8002**. **Ctrl+C** apaga los tres. Si algo falla, los mensajes están en `apis/logs/`.

Mientras ningún modelo haya subido resultados, la web app usa un **Stuff+ provisional** y lo dice en el encabezado.

## 4. Correr los modelos y subir sus resultados

**Lo más fácil:** con todo prendido (`iniciar_todo.sh` en una Terminal), en **otra** Terminal desde la raíz del repo:

```bash
bash apis/correr_modelos.sh        # los dos: Stuff+ (06) y BayesBall (03)
bash apis/correr_modelos.sh 03     # solo uno
```

- Instala lo que necesitan los notebooks (`apis/requirements-modelos.txt`, la primera vez tarda 1-2 minutos).
- Corre cada notebook completo, y cada uno sube sus tablas al API 2 y recarga la web app.
- No modifica los notebooks del repo. La copia con salidas queda en `apis/logs/`, que git ignora.
- La primera vez, Stuff+ entrena su prueba por temporada (`modelos/season_holdout.csv`, que git ignora), así que tarda más. Las siguientes la reutiliza.
- Si en Mac sale "xgboost no carga", falta OpenMP: `brew install libomp` y vuelve a correrlo.

Los resultados quedan guardados en `~/Desktop/hackathon/resultados_api2`. Al volver a prender la app ya no hace falta correr los modelos otra vez.

También se puede a mano desde Jupyter:

### Stuff+

1. Con todo prendido, corre `notebooks/06_StuffPlus.ipynb` completo. Los modelos ya entrenados están en `modelos/` del repo, así que no vuelve a entrenar salvo que pongas `REENTRENAR = True`.
2. El **Paso 9** sube dos tablas al API 2:
   - `stuff_plus_por_pitcher_tipo` (el Stuff+ en los 3 niveles de altitud).
   - `validacion` (las métricas de los pasos 6a, 6b y 6c).
3. Al final recarga la web app, que pasa de "provisional" al modelo sin reiniciar nada.

Para una versión nueva del modelo, cambia `VERSION_MODELO` en el Paso 9. La anterior queda en el historial del API 2.

El Paso 9 necesita `requests` en el Python del notebook (Polars ya lo usa el notebook). Si falta: `%pip install requests`.

### BayesBall

1. Con todo prendido, corre `notebooks/03_model_stuff_plus.ipynb` completo (menos de un minuto de entrenamiento).
2. La **sección 7** sube dos tablas al API 2:
   - `bayesball_por_pitcher_tipo` (la P(whiff) de cada pitcher × temporada × tipo en los 3 niveles de altitud).
   - `bayesball_validacion` (AUC, coeficiente de la interacción y penalización perceptual).
3. Al final recarga la web app: el perfil de cada pitcher muestra su P(whiff) a nivel del mar → Harp Helú, y Metodología muestra las métricas.

Para una versión nueva, cambia `VERSION_BAYES` en la sección 7. Necesita scikit-learn y `requests` en el Python del notebook.

El formato exacto de lo que la web app espera de cada modelo está en [`CONTRATO_API2.md`](../models/webapp/CONTRATO_API2.md).

## Flujo de git del equipo

- Cada quien trabaja en su rama y abre un PR a `main` (`main` pide aprobación).
- Stuff+ se versiona en `notebooks/06_StuffPlus.ipynb` y BayesBall en `notebooks/03_model_stuff_plus.ipynb`. **Antes de hacer commit, limpia las salidas** (Kernel → Restart & Clear Output), porque muestran tablas sacadas de los datos.
- Los notebooks encuentran los datos solos: `~/Desktop/hackathon` (o `DATOS_DIR`), o `data/raw/` del repo. Nada de rutas con `/Users/<nombre>`.
- Si un modelo nuevo vive en otro archivo, que también suba sus resultados con `ClienteAPI2` (`apis/api/cliente.py`).
