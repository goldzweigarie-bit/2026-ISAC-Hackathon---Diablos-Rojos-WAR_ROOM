# Diablos Stuff+ · web app

Web app del hackathon Diablos Rojos: Stuff+ ajustado por altitud en cada parque de la LMB.

```
API 1 :8000 (pitcheos) ──────────────────────────────┐
                                                     ├──→ traductor :8002 ──→ frontend (navegador)
Stuff+ / BayesBall ──→ API 2 :8001 (resultados) ─────┘
```

Esta carpeta tiene dos piezas:

- **`backend/`, el traductor (Python + Polars, sin pandas).** No tiene datos ni modelo propios. Pide los pitcheos al API 1 y el Stuff+ al API 2, y los convierte en las respuestas que necesita cada pantalla.
- **`frontend/`, lo que se ve.** Un React ya compilado en `frontend/dist`, que el traductor sirve directamente.

## Pantallas

- **Inicio**: mapa de los 20 parques, buscador, calendario de los Diablos, el diablo (bullpen para la siguiente serie) y agentes libres.
- **Parque**: zona de strike vista desde el cátcher. Muestra dónde cae cada pitcheo del pitcher elegido a nivel del mar contra este parque con la misma salida. También tiene la gráfica de movimiento y la corona: el ranking de pitchers por Stuff+ en ese parque.
- **Pitcher**: arsenal, Stuff+ en los 20 parques y cargas de trabajo.
- **Agentes libres** y **Metodología**: la segunda incluye el estudio de altitud, las métricas de validación y el link al paper.
- Botón ES / EN en todas las pantallas.

## Correrlo

**Lo normal:** desde la raíz del repo, `bash apis/instalar.sh` (una vez) y `bash apis/iniciar_todo.sh`, que prende los dos APIs y esta app juntos. Ver [`apis/README.md`](../../apis/README.md).

A mano (necesitas Python 3.10 o superior; Node no hace falta para la demo):

```bash
cd models/webapp/backend
python3 -m pip install -r requirements.txt
cp .env.example .env          # pon las llaves (ver abajo)
python3 -m uvicorn app.main:app --port 8002
```

Abre **http://localhost:8002**. El API 1 y el API 2 tienen que estar prendidos, cada uno en su propia Terminal.

### `.env`

| Variable | Valor |
|---|---|
| `API1_URL` / `API1_KEY` | `http://localhost:8000` y la misma llave que `apis/api/.env` |
| `API2_URL` / `API2_KEY` | `http://localhost:8001` y la llave de **lectura** del API 2 (`API_KEY` de `apis/api2/.env`), no la de escritura |
| `PAPER_URL` | opcional: link al paper para la página de Metodología |

El `.env` nunca va a GitHub, porque ya está en `.gitignore`.

### Qué pasa si algo está apagado

| Situación | Qué hace el traductor |
|---|---|
| API 2 sin la tabla de Stuff+ (los modelos no han terminado) | Usa un **Stuff+ provisional** con pesos a mano, sin entrenar. El encabezado dice "Modelo provisional" |
| El modelo sube su tabla al API 2 | `POST http://localhost:8002/api/admin/reload` (o reiniciar) y la app pasa a usar el modelo |
| API 1 apagado al arrancar | Usa la última copia guardada en `backend/data/cache/`, que se crea sola la primera vez y nunca va a GitHub |

## Cómo se conecta el modelo

El traductor busca en el API 2 la tabla **`stuff_plus_por_pitcher_tipo`**. El formato exacto está en **[CONTRATO_API2.md](CONTRATO_API2.md)**. En resumen:
- Un renglón por pitcher × temporada × tipo de pitcheo.
- El Stuff+ va en tres niveles de altitud: `stuff_plus_nivel_mar`, `stuff_plus_media` y `stuff_plus_cdmx`.

Cada parque toma la columna de su nivel. Por ejemplo, Harp Helú y Serdán toman `stuff_plus_cdmx`. Los umbrales están en `niveles_altitud` de `data/reference/app_config.json`.

## Para editar el diseño (frontend)

Necesitas Node 18 o superior. Deja el traductor prendido en el puerto 8002 y, en otra Terminal:

```bash
cd models/webapp/frontend
npm install
npm run dev          # http://localhost:5173, con recarga en vivo (pide /api al :8002)
```

- Los estilos están en `src/styles.css`, los textos ES/EN en `src/i18n.tsx` y las pantallas en `src/pages/`.
- Al terminar, corre **`npm run build`**. Eso actualiza `frontend/dist`, que es lo que se ve en la demo.

## Archivos del traductor (`backend/app/`)

Están en el orden en que fluyen los datos:

| Archivo | Qué hace |
|---|---|
| `fuentes.py` | Habla con el API 1 y el API 2, y guarda la copia local de los pitcheos |
| `preparar.py` | Convierte los pitcheos en tablas: arsenal por pitcher y tipo, rol SP/RP, estudio de altitud |
| `store.py` | Junta todo en memoria: la física de cada pitcheo en cada parque y el Stuff+ del API 2 por nivel |
| `physics.py` | Densidad del aire, Magnus y drag, y trayectorias |
| `services.py` | Arma la respuesta de cada pantalla |
| `bullpen.py` | La recomendación del diablo |
| `main.py` | Recibe las preguntas del frontend (`/api/...`) y sirve `frontend/dist` |
| `model.py` | Stuff+ provisional: solo se usa mientras no exista la tabla en el API 2 |

## Datos de la final y temporada 2027

- **Datos de la final** (con nombres, equipos, fechas y estadios): el API 1 los entrega y el traductor los reconoce solo. Se encienden el cansancio del bullpen y los agentes libres. Si alguna columna trae otro nombre, agrégalo en `data/reference/column_map.json`.
- **Rosters** (opcional): `backend/data/rosters/<temporada>.csv` con `season,pitcher_id,name,team_code,role`. `team_code` es un código de `stadiums.json` (MEX, PUE…) o `FA`.
- **2027**: corre `python3 scripts/fetch_schedule.py --season 2027` para bajar el calendario de la API pública de MLB.

## Notas

- **Datos anonimizados:** no traen equipos ni fechas. Por eso:
  - Los pitchers aparecen como "Equipo ?".
  - El diablo explica que todavía no puede saber quién es del staff.
  - El estudio de altitud se agrupa por `altitude_category`.
- **Calendario 2026:** viene de la API de MLB (sportId 23), que lista 97 juegos (68-29). El conteo oficial es 93 (64-29). Hay que compararlo antes de presentar.
- **Altitudes:** Harp Helú (2,232 m) y Serdán (2,192 m) son oficiales de la LMB. Las demás son aproximadas y están en `stadiums.json`.
- **Física:** el Magnus y el drag escalan con la densidad del aire, y la humedad se ignora.

## Pruebas

```bash
cd models/webapp/backend && python3 -m pytest
```

Las 11 pruebas (unos 10 s) simulan el API 1 y el API 2 con datos sintéticos (`tests/sintetico.py`), así que no necesitan que haya nada prendido. Cubren cuatro casos:
- API 2 vacío.
- API 2 con la tabla del modelo.
- La tabla sin la columna `stuff_plus_media`.
- Datos anonimizados como los reales.

