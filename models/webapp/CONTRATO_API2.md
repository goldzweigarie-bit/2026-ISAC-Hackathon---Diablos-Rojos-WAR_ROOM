# Contrato: qué tiene que subir el modelo al API 2

Este archivo es el acuerdo entre los **modelos** (Stuff+ y BayesBall) y el **traductor** (la web app). Si un modelo sube su tabla con esta forma, la web app la usa sin cambiar código.

| Modelo | Tablas | Si no existen |
|---|---|---|
| Stuff+ (`notebooks/06_StuffPlus.ipynb`, Paso 9) | `stuff_plus_por_pitcher_tipo`, `validacion` | La app usa un Stuff+ provisional y lo dice en el encabezado |
| BayesBall (`notebooks/03_model_stuff_plus.ipynb`, sección 7) | `bayesball_por_pitcher_tipo`, `bayesball_validacion` | La columna de BayesBall no aparece y Metodología dice que está pendiente |

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

Ya está hecho: el **Paso 9** de `notebooks/06_StuffPlus.ipynb` arma esta tabla desde `por_pitcher_tipo` (paso 8a), la sube con `ClienteAPI2` y recarga la web app. Solo hay que tener todo prendido (`bash apis/iniciar_todo.sh`) y correr el notebook completo.

## Tabla `validacion` (opcional: página de Metodología)

| Columna | Ejemplo |
|---|---|
| `nombre` | `Split-half r (Stuff+)` |
| `valor` | `0.82` |
| `split` | `juegos pares vs impares` (opcional) |
| `tipo` | `metrica`, `submodelo` o `nota` (opcional; por defecto `metrica`). Una `nota` es texto libre en `nombre` y se muestra abajo de la tabla |
| `objetivo`, `metrica` | Solo para `tipo = submodelo`, p. ej. `whiff` y `log loss` |

## Tabla `bayesball_por_pitcher_tipo` (BayesBall)

Es `notebooks/03_model_stuff_plus.ipynb` (+ `src/models/bayesian_resolvability.py`): una regresión logística de P(whiff) con un *resolvability score* bayesiano. Un renglón por **pitcher × temporada × tipo de pitcheo**, con las mismas llaves que Stuff+:

| Columna | Tipo | Ejemplo | Notas |
|---|---|---|---|
| `pitcher_anon_id`, `year`, `tipo` | | | Igual que en la tabla de Stuff+ |
| `p_whiff_nivel_mar` | número 0-1 | `0.156` | P(whiff) por pitcheo si se lanzara en "No Altitude" (obligatoria) |
| `p_whiff_media` | número 0-1 | `0.153` | En "Medium Altitude" (opcional) |
| `p_whiff_cdmx` | número 0-1 | `0.151` | En "Extreme Altitude" (opcional) |
| `pitcheos`, `whiff_real`, `penalizacion_cdmx` | | | Informativas; el traductor las ignora |

- **Cómo se calcula:** a cada pitcheo real se le cambia **solo** `altitude_category` (la física medida queda igual), se recalcula la resolvabilidad y se predice. Se promedia por pitcher × temporada × tipo.
- **Escala:** P(whiff) **por pitcheo** (swing y fallo entre todos los pitcheos), regresada a la tasa real de whiff porque el modelo se entrena con `class_weight='balanced'`. La web app la muestra en % junto al Whiff % (que es por swing).
- **Dónde se ve:** en el perfil de cada pitcher, una columna "BayesBall P(whiff)" con nivel del mar → Harp Helú (el nivel del parque de casa, `home_stadium_id`).

## Tabla `bayesball_validacion` (BayesBall, página de Metodología)

Mismas columnas que `validacion` (`nombre`, `valor`, `split`, `tipo`). La sección 7 del notebook sube el AUC, el log loss, el coeficiente de `resolv_x_extreme`, la penalización perceptual promedio y la del slider, y una `nota` con la escala.

### Cómo salen del notebook

Ya está hecho: la **sección 7** de `notebooks/03_model_stuff_plus.ipynb` arma las dos tablas, las sube con `ClienteAPI2` (`modelo="bayesball"`, `VERSION_BAYES`) y recarga la web app.

Los nombres de las tablas y columnas que busca el traductor están en `backend/data/reference/app_config.json` (sección `api2`), por si algún día cambian.
