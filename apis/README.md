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
| `notebooks/03_model_stuff_plus.ipynb` | El modelo Stuff+. Su **Paso 9** sube los resultados al API 2 |
| `apis/instalar.sh` · `apis/iniciar_todo.sh` | Instalar una vez · prender todo |

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

## 4. Subir un modelo

### Stuff+

1. Con todo prendido, corre `notebooks/03_model_stuff_plus.ipynb` completo.
2. El **Paso 9** sube dos tablas al API 2:
   - `stuff_plus_por_pitcher_tipo` (el Stuff+ en los 3 niveles de altitud).
   - `validacion` (las métricas de los pasos 6a, 6b y 6c).
3. Al final recarga la web app, que pasa de "provisional" al modelo sin reiniciar nada.

Para una versión nueva del modelo, cambia `VERSION_MODELO` en el Paso 9. La anterior queda en el historial del API 2.

El Python del notebook necesita `polars pyarrow requests` para el Paso 9. Si falta alguno: `%pip install polars pyarrow requests`.

### BayesBall

Se sube igual: `ClienteAPI2.subir("bayesball_<nombre>", tabla, modelo="bayesball", version="v1")`. Para que la web app lo **muestre**, hay que acordar su tabla en [`CONTRATO_API2.md`](../models/webapp/CONTRATO_API2.md) y conectarla en el traductor.

El formato exacto de lo que la web app espera de cada modelo está en [`CONTRATO_API2.md`](../models/webapp/CONTRATO_API2.md).

## Flujo de git del equipo

- Cada quien trabaja en su rama y abre un PR a `main` (`main` pide aprobación).
- El modelo Stuff+ se versiona en `notebooks/03_model_stuff_plus.ipynb`. **Antes de hacer commit, limpia las salidas** (Kernel → Restart & Clear Output), porque muestran tablas sacadas de los datos.
- Si un modelo nuevo vive en otro archivo, que también suba sus resultados con `ClienteAPI2` (`apis/api/cliente.py`).
