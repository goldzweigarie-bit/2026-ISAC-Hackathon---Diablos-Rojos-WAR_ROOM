# Contrato: qué tiene que subir el modelo al API 2

Este archivo es el acuerdo entre el **modelo** (Stuff+) y el **traductor** (la web app). Si el modelo sube esta tabla, la web app la usa sin cambiar código. Mientras no exista, la web app muestra un Stuff+ provisional y lo indica en el encabezado.

## Tabla `stuff_plus_por_pitcher_tipo` (obligatoria)

La tabla lleva **un renglón por pitcher × temporada × tipo de pitcheo**.

| Columna | Tipo | Ejemplo | Notas |
|---|---|---|---|
| `pitcher_anon_id` | texto | `pitcher_00386` | El mismo id del API 1 |
| `year` | entero | `2025` | |
| `tipo` | texto | `Slider` | `Four-Seam`, `Sinker`, `Cutter`, `Slider`, `Curveball`, `Changeup`, `Splitter`. Si viene `Sweeper`, se cuenta como `Slider` |
| `pitcheos` | entero | `412` | Opcional, informativo |
| `stuff_plus_nivel_mar` | número | `104.2` | Stuff+ del pitcheo **calificado en "No Altitude"** (escala 100 + 10·z) |
| `stuff_plus_media` | número | `102.9` | Stuff+ **calificado en "Medium Altitude"** |
| `stuff_plus_cdmx` | número | `98.7` | Stuff+ **calificado en "Extreme Altitude"** (CDMX, Puebla) |

- **Cada parque toma la columna de su nivel.** Harp Helú y Serdán (≥ 2000 m) toman `stuff_plus_cdmx`. Los parques entre 1000 y 2000 m toman `stuff_plus_media`, y los demás `stuff_plus_nivel_mar`. Los umbrales se cambian en `niveles_altitud` de `backend/data/reference/app_config.json`.
- **Sin `stuff_plus_media`, la app sigue funcionando.** Interpola cada parque de altitud media entre nivel del mar y CDMX según la densidad del aire, y lo reporta en `/api/methodology` (`levels_interpolated`).
- **Columnas extra:** se pueden agregar las que quieran, como las probabilidades o Location+. El traductor las ignora.

### Cómo sale del notebook

Ya está hecho: el **Paso 9** de `notebooks/03_model_stuff_plus.ipynb` arma esta tabla desde `por_pitcher_tipo` (paso 8a), la sube con `ClienteAPI2` y recarga la web app. Solo hay que tener todo prendido (`bash apis/iniciar_todo.sh`) y correr el notebook completo.

## Tabla `validacion` (opcional: página de Metodología)

| Columna | Ejemplo |
|---|---|
| `nombre` | `Split-half r (Stuff+)` |
| `valor` | `0.82` |
| `split` | `juegos pares vs impares` (opcional) |
| `tipo` | `metrica` o `submodelo` (opcional; por defecto `metrica`) |
| `objetivo`, `metrica` | Solo para `tipo = submodelo`, p. ej. `whiff` y `log loss` |

## BayesBall (pendiente de definir)

Ya se puede **subir** al API 2 igual que Stuff+:

```python
api2.subir("bayesball_<nombre>", tabla, modelo="bayesball", version="v1")
```

Para que la web app lo **muestre** falta acordar qué predice y la forma de su tabla: llaves (`pitcher_anon_id`, `year`, ¿`tipo`?), columnas y en qué pantalla va. Con eso se agrega aquí y se conecta en el traductor (`backend/app/store.py` y `services.py`).
