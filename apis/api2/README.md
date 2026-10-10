# API 2; resultados de Stuff+ y BayesBall

```
API 1 (datos)  →  Modelos (Stuff+, BayesBall)  →  API 2 (resultados)  → Traductor → WebApp
                                                    ↑ este
```

Los modelos **suben** aquí sus tablas de resultados y el traductor de la web app las **lee**.
No calcula nada: guarda y entrega. Corre en el puerto **8001** (el API 1 usa el 8000).

## Archivos

| Archivo | Qué es |
|---|---|
| `main.py` | el API (FastAPI + Polars, sin pandas) |
| `migrar_resultados.py` | sube una sola vez las tablas que ya estaban en `resultados/` |
| `test_api.py` | 13 pruebas automáticas |
| `iniciar.sh` | arranca el servidor |
| `.env.example` | plantilla de configuración (las dos llaves) |
| `.env` | tu configuración real — **nunca a GitHub** |
| `requirements.txt` | dependencias (las mismas que el API 1) |

El cliente para Python (`ClienteAPI2`) vive en `apis/api/cliente.py`, junto al del API 1.

> **Lo normal es no hacer esto a mano:** `bash apis/instalar.sh` y `bash apis/iniciar_todo.sh` desde la raíz del repo hacen todo (ver [`apis/README.md`](../README.md)). Lo de abajo es el detalle, por si algo falla.

## Dos llaves

| Llave | Quién la usa | Qué puede hacer |
|---|---|---|
| `API_KEY` (lectura) | el traductor, quien consulta | leer tablas |
| `API_KEY_ESCRITURA` | los notebooks de los modelos | leer, **subir y borrar** tablas |

Así el traductor no puede borrar ni pisar resultados por error. Las dos van en el encabezado
`X-API-Key`, igual que en el API 1, y deben ser distintas.

## 1. Instalar (una sola vez)

```bash
cd apis/api2
python3 -m pip install -r requirements.txt
cp .env.example .env          # pon las dos llaves y las carpetas
```

Edita `.env` y pon las dos llaves (mínimo 12 caracteres cada una). Para generar una:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

## 2. Arrancar

```bash
./iniciar.sh            # solo esta Mac
./iniciar.sh red        # también otras computadoras de la misma Wi-Fi
```

Espera la línea `Listo: N tablas en ...`. Para detenerlo: `Ctrl+C`.
Los dos APIs se corren a la vez, cada uno en su ventana de Terminal.

## 3. Pasar los resultados que ya existen (una sola vez)

Con el API 2 prendido:

```bash
python3 migrar_resultados.py ~/Desktop/hackathon/resultados
```

Sube cada `.csv` y `.parquet` de esa carpeta con `modelo="stuff_plus"`. Si hay pickles (`.pkl`), el script te
pide convertirlos antes con `python3 ../api/convertir_pickle.py <archivo.pkl>`.

## 4. Subir resultados desde un modelo

```python
import sys; sys.path.append("../apis/api")         # desde notebooks/
from cliente import ClienteAPI2

api2 = ClienteAPI2("http://localhost:8001", "LLAVE_DE_ESCRITURA")
api2.subir("stuff_plus_por_pitcher", por_pitcher, modelo="stuff_plus", version="v3")   # Polars o pandas
api2.subir("bayesball_pitchers", tabla_bayes, modelo="bayesball", version="v1")
api2.tablas()          # qué hay, quién lo subió, versión y fecha
```

- **Nombre de tabla:** solo minúsculas, números y `_`.
- **Subir con un nombre que ya existe la reemplaza,** y la versión anterior queda en
  `resultados_api2/historial/` con su fecha y versión. Nada se pierde.
- **`version`** es libre: `v3`, el commit de git, la fecha. Sirve para saber qué versión del modelo está sirviendo.

## 5. Rutas

| Ruta | Llave | Devuelve |
|---|---|---|
| `GET /salud` | ninguna | estado y lista de tablas |
| `GET /resultados` | lectura | tablas con renglones, columnas, modelo, versión y fecha |
| `GET /resultados/{tabla}` | lectura | una tabla en JSON, por páginas (`limit`, `offset`) |
| `GET /resultados/{tabla}/descargar` | lectura | una tabla como Parquet o CSV |
| `POST /resultados/{tabla}?modelo=...&version=...` | escritura | sube o reemplaza una tabla (cuerpo: Parquet) |
| `DELETE /resultados/{tabla}` | escritura | deja de servirla; el archivo se mueve a `historial/` |

Filtros de lectura, iguales que en el API 1: `year`, `pitcher`, `tipo`, `altitud`, `columnas`.

## 6. Comprobar que todo está bien

```bash
python3 -m pytest -v
```

Las 13 pruebas usan una carpeta temporal y llaves de prueba: no tocan tus resultados ni tu `.env`.

## Dónde se guardan las tablas

En `RESULTADOS_DIR` de `apis/api2/.env` (por defecto `~/Desktop/hackathon/resultados_api2`), **fuera del repo**.
Cada tabla es un `.parquet`, y `_metadatos.json` dice quién la subió y cuándo.
Si apagas y prendes el API, todo sigue ahí.
