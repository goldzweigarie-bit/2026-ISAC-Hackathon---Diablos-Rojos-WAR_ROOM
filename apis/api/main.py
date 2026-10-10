"""
API 1 — Datos del proyecto Stuff+ (Diablos Rojos, ISAC 2026)

    API 1 (datos)  →  Modelos (Stuff+, BayesBall)  →  API 2 (resultados)  →  Traductor  →  WebApp
       ↑ este

Este API entrega por HTTP:
  - el dataset de pitcheos (stuff_model_df.parquet; ver convertir_pickle.py)
  - las constantes de carreras de FanGraphs (RunValueEvents.csv), convertidas a carreras

Solo entrega datos de entrada. Lo que producen los modelos se sube al API 2 (carpeta apis/api2/).
El código vive en el repo; los DATOS no (el repo es público): su carpeta se indica con DATOS_DIR en apis/api/.env.

Arrancar (desde la carpeta apis/api/), o todo junto con  bash apis/iniciar_todo.sh :
    python3 -m uvicorn main:app --port 8000
Documentación interactiva:
    http://localhost:8000/docs
"""
import io                                             # para escribir archivos en memoria (sin tocar el disco)
import logging                                        # mensajes en la terminal con hora y nivel
import os                                             # leer variables de entorno
import secrets                                        # comparar llaves de forma segura
from contextlib import asynccontextmanager            # para cargar los datos una sola vez al arrancar
from enum import Enum                                 # listas cerradas de valores válidos (altitud, formato)
from pathlib import Path                              # rutas que funcionan en Mac, Windows y Linux

import polars as pl                                   # tablas
import polars.selectors as cs                         # elegir columnas por tipo (p. ej. todas las float)
from fastapi import FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware    # permite que un navegador (dashboard) llame al API
from fastapi.middleware.gzip import GZipMiddleware    # comprime las respuestas grandes
from fastapi.responses import Response                # para devolver archivos (Parquet, CSV)
from fastapi.security import APIKeyHeader             # lee la llave del encabezado de cada petición

VERSION = "2.0.0"            # 2.0: las rutas /resultados se mudaron al API 2
log = logging.getLogger("api1")                       # nuestro "canal" de mensajes
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


# ==============================================================================================
# 1. CONFIGURACIÓN
# Nada de rutas ni llaves escritas en el código: todo viene del archivo .env (o del sistema).
# Así cada compañero ajusta su máquina sin tocar main.py, y la llave nunca llega a GitHub.
# ==============================================================================================
CARPETA_API = Path(__file__).resolve().parent         # la carpeta donde vive este archivo (api/)


def cargar_env(ruta: Path) -> None:
    """Lee un archivo .env (líneas CLAVE=valor) y lo pasa a variables de entorno.
    Las variables que ya existan en el sistema tienen prioridad (no se sobrescriben)."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:   # vacías, comentarios y basura: se saltan
            continue
        clave, valor = linea.split("=", 1)                           # solo el primer "=" separa
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


cargar_env(CARPETA_API / ".env")

CARPETA_DATOS = Path(os.path.expanduser(os.getenv("DATOS_DIR", str(CARPETA_API.parent))))  # FUERA del repo
ARCHIVO_DATOS = CARPETA_DATOS / os.getenv("PARQUET", "stuff_model_df.parquet")
ARCHIVO_CSV = CARPETA_DATOS / os.getenv("CSV_RUN_VALUES", "RunValueEvents.csv")
API_KEY = os.getenv("API_KEY", "")
LIMITE_JSON = 50_000                                                # máximo de renglones por respuesta JSON

# Columnas de peso wOBA del CSV → nombre del evento que usa el notebook (VALOR_EVENTO)
MAPA_EVENTOS = {"wBB": "Walk", "wHBP": "HitByPitch", "w1B": "Single",
                "w2B": "Double", "w3B": "Triple", "wHR": "HomeRun"}


class Altitud(str, Enum):
    """Valores válidos de altitude_category. FastAPI rechaza cualquier otro con un error 422."""
    no = "No Altitude"
    media = "Medium Altitude"
    extrema = "Extreme Altitude"


class Formato(str, Enum):
    parquet = "parquet"     # binario, comprimido y conserva tipos: el que debe usar el modelo
    csv = "csv"             # texto: para abrir en Excel


DATOS: dict = {}            # memoria del servidor: dataset, constantes y caché de descargas


# ==============================================================================================
# 2. CARGA DE DATOS (una sola vez, al arrancar)
# ==============================================================================================
def cargar_constantes(ruta: Path) -> dict:
    """Lee el CSV de FanGraphs (Guts!) y convierte los pesos wOBA a carreras por evento."""
    tabla = pl.read_csv(ruta)
    faltan = [c for c in ["Season", "wOBAScale", *MAPA_EVENTOS] if c not in tabla.columns]
    if faltan:
        raise RuntimeError(f"Al CSV {ruta.name} le faltan columnas: {faltan}")
    fila = tabla.sort("Season").row(-1, named=True)                   # la temporada más reciente, como dict
    escala = float(fila["wOBAScale"])
    # Un peso wOBA = (carreras por encima de un out) × wOBAScale. Dividir entre la escala lo regresa
    # a carreras. El out vale 0. Error = Single y Sacrifice/FieldersChoice = Out son decisiones nuestras.
    carreras = {evento: round(float(fila[col]) / escala, 4) for col, evento in MAPA_EVENTOS.items()}
    carreras.update({"Error": carreras["Single"], "Out": 0.0, "Strikeout": 0.0,
                     "FieldersChoice": 0.0, "Sacrifice": 0.0})
    return {
        "fuente": "FanGraphs, Guts! wOBA & FIP constants (https://www.fangraphs.com/guts.aspx?type=cn)",
        "temporada": int(fila["Season"]),
        "pesos_woba": {c: float(fila[c]) for c in tabla.columns if c != "Season"},
        "valor_evento": carreras,
        "nota": "valor_evento = peso wOBA / wOBAScale, en carreras respecto a un out",
    }


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Todo lo que está antes del `yield` corre al ARRANCAR; lo de después, al APAGAR.
    Si algo falta, el servidor no arranca y dice exactamente qué: mejor fallar al inicio que a medias."""
    if len(API_KEY) < 12:
        raise RuntimeError("API_KEY falta o es muy corta (mínimo 12 caracteres). Revisa api/.env")
    if not ARCHIVO_DATOS.exists() and ARCHIVO_DATOS.with_suffix(".pkl").exists():
        raise RuntimeError(f"Falta {ARCHIVO_DATOS.name}. Conviértelo UNA vez desde el pickle: "
                           f"python3 convertir_pickle.py")
    for archivo in (ARCHIVO_DATOS, ARCHIVO_CSV):
        if not archivo.exists():
            raise RuntimeError(f"No encuentro {archivo}. Revisa DATOS_DIR en api/.env")

    log.info("Cargando %s ...", ARCHIVO_DATOS.name)
    DATOS["pitcheos"] = pl.read_parquet(ARCHIVO_DATOS)                # ~635 mil renglones en memoria
    DATOS["constantes"] = cargar_constantes(ARCHIVO_CSV)
    DATOS["cache"] = {}                                               # descargas completas ya generadas
    log.info("Listo: %s pitcheos | constantes %s",
             f"{DATOS['pitcheos'].height:,}", DATOS["constantes"]["temporada"])
    yield                                                             # ← aquí el servidor atiende peticiones
    DATOS.clear()                                                     # al apagar, libera la memoria
    log.info("Servidor apagado")


# ==============================================================================================
# 3. LA APLICACIÓN Y SU SEGURIDAD
# ==============================================================================================
app = FastAPI(
    title="API 1 · Datos Stuff+ Diablos Rojos",
    description=("Datos de pitcheos de la LMB 2024–2026 y constantes de carreras de FanGraphs. "
                 "Los resultados de los modelos viven en el API 2.\n\n**Autenticación:** todas las rutas, menos `/salud`, piden el encabezado "
                 "`X-API-Key`. En esta página: botón **Authorize** (arriba a la derecha), pega la llave y listo."),
    version=VERSION,
    lifespan=ciclo_de_vida,
)

# CORS: el navegador bloquea que una página (el dashboard) llame a otro servidor, salvo que ese
# servidor lo autorice. Permitimos cualquier origen porque la protección real es la llave.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
# GZip: comprime respuestas de más de 1 KB si el cliente lo acepta. El JSON se reduce ~7 veces.
app.add_middleware(GZipMiddleware, minimum_size=1000)

llave_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Llave definida en api/.env")


def verificar_llave(llave: str | None = Security(llave_header)) -> None:
    """Se ejecuta antes de cada ruta protegida. Llave ausente o incorrecta → 401 y no se entrega nada.
    secrets.compare_digest tarda lo mismo acierte o falle, así no se puede adivinar la llave midiendo tiempos."""
    if not llave or not secrets.compare_digest(llave, API_KEY):
        raise HTTPException(status_code=401, detail="Llave inválida o ausente (encabezado X-API-Key)")


PROTEGIDA = [Security(verificar_llave)]          # se agrega a cada ruta que pide llave


# ==============================================================================================
# 4. FUNCIONES DE APOYO (filtrar, paginar, convertir)
# ==============================================================================================
def a_json(tabla: pl.DataFrame) -> list:
    """DataFrame → lista de diccionarios. Los NaN se vuelven null, porque JSON no acepta NaN."""
    return tabla.with_columns(cs.float().fill_nan(None)).to_dicts()


def separar_columnas(texto: str | None) -> list | None:
    """'a, b,c' → ['a', 'b', 'c']. Vacío → None (todas las columnas)."""
    return [c.strip() for c in texto.split(",") if c.strip()] if texto else None


def filtrar(tabla: pl.DataFrame, year=None, pitcher=None, tipo=None, altitud=None) -> pl.DataFrame:
    """Aplica solo los filtros que vengan y que existan como columna en la tabla."""
    columnas = tabla.columns
    condiciones = []
    if year is not None and "year" in columnas:
        condiciones.append(pl.col("year") == year)
    if pitcher is not None and "pitcher_anon_id" in columnas:
        condiciones.append(pl.col("pitcher_anon_id") == pitcher)
    col_tipo = next((c for c in ("tipo", "AutoPitchType") if c in columnas), None)
    if tipo is not None and col_tipo:
        condiciones.append(pl.col(col_tipo).cast(pl.String) == tipo)        # cast: puede ser categórica
    if altitud is not None and "altitude_category" in columnas:
        condiciones.append(pl.col("altitude_category").cast(pl.String) == altitud.value)
    return tabla.filter(*condiciones) if condiciones else tabla


def elegir_columnas(tabla: pl.DataFrame, columnas: list | None) -> pl.DataFrame:
    """Se queda con las columnas pedidas; si alguna no existe → 400 con la lista de las que faltan."""
    if not columnas:
        return tabla
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        raise HTTPException(status_code=400, detail=f"Columnas inexistentes: {faltan}. Consulta /columnas")
    return tabla.select(columnas)


def paginar(tabla: pl.DataFrame, limit: int, offset: int) -> dict:
    """Un pedazo de la tabla en JSON, más el total, para que el cliente sepa cuántas páginas hay."""
    pedazo = tabla.slice(offset, limit)
    return {"total": tabla.height, "offset": offset, "n": pedazo.height, "registros": a_json(pedazo)}


def archivo(tabla: pl.DataFrame, formato: Formato, nombre: str) -> Response:
    """Convierte la tabla en un archivo Parquet o CSV en memoria y lo devuelve como descarga."""
    buffer = io.BytesIO()
    if formato == Formato.parquet:
        tabla.write_parquet(buffer)
        tipo_mime = "application/vnd.apache.parquet"
    else:
        tabla.write_csv(buffer)
        tipo_mime = "text/csv"
    return Response(content=buffer.getvalue(), media_type=tipo_mime,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}.{formato.value}"'})


# Filtros comunes (se repiten en varias rutas; aquí se definen una vez con su descripción)
F_YEAR = Query(None, description="Temporada, p. ej. 2025")
F_PITCHER = Query(None, description="pitcher_anon_id, p. ej. pitcher_00386")
F_TIPO = Query(None, description="Tipo de pitcheo, p. ej. Slider")
F_ALTITUD = Query(None, description="Nivel de altitud")
F_COLUMNAS = Query(None, description="Columnas separadas por coma; vacío = todas")


# ==============================================================================================
# 5. RUTAS (ENDPOINTS)
# ==============================================================================================
@app.get("/salud", tags=["sistema"], summary="¿Está vivo el servidor?")
def salud():
    """No pide llave. Sirve para comprobar que el API responde y qué tiene cargado."""
    return {"ok": True, "version": VERSION, "pitcheos": DATOS["pitcheos"].height if "pitcheos" in DATOS else 0,
            "constantes_temporada": DATOS.get("constantes", {}).get("temporada")}


# ---- Constantes --------------------------------------------------------------------------------
@app.get("/constantes/carreras", tags=["constantes"], dependencies=PROTEGIDA,
         summary="Valor en carreras de cada evento (FanGraphs)")
def constantes_carreras():
    """Pesos wOBA del CSV y `valor_evento`: el diccionario listo para usar como VALOR_EVENTO en el modelo."""
    return DATOS["constantes"]


# ---- Pitcheos ----------------------------------------------------------------------------------
@app.get("/columnas", tags=["pitcheos"], dependencies=PROTEGIDA, summary="Columnas del dataset y su tipo")
def columnas():
    return {c: str(t) for c, t in DATOS["pitcheos"].schema.items()}


@app.get("/pitcheos/resumen", tags=["pitcheos"], dependencies=PROTEGIDA,
         summary="Pitcheos por temporada y altitud")
def pitcheos_resumen():
    t = (DATOS["pitcheos"].with_columns(pl.col("altitude_category").cast(pl.String))
         .group_by(["year", "altitude_category"]).len(name="n").sort(["year", "altitude_category"]))
    return a_json(t)


@app.get("/pitcheos", tags=["pitcheos"], dependencies=PROTEGIDA, summary="Pitcheos en JSON (por páginas)")
def pitcheos(year: int | None = F_YEAR, pitcher: str | None = F_PITCHER, tipo: str | None = F_TIPO,
             altitud: Altitud | None = F_ALTITUD, columnas: str | None = F_COLUMNAS,
             limit: int = Query(1000, ge=1, le=LIMITE_JSON, description="Renglones por página"),
             offset: int = Query(0, ge=0, description="Desde qué renglón empezar")):
    """Para consultas chicas (un pitcher, un juego) y para el dashboard.
    Para traer miles de pitcheos usa `/pitcheos/descargar`: es mucho más rápido."""
    tabla = filtrar(DATOS["pitcheos"], year, pitcher, tipo, altitud)
    return paginar(elegir_columnas(tabla, separar_columnas(columnas)), limit, offset)


@app.get("/pitcheos/descargar", tags=["pitcheos"], dependencies=PROTEGIDA,
         summary="Pitcheos como archivo Parquet o CSV")
def pitcheos_descargar(year: int | None = F_YEAR, pitcher: str | None = F_PITCHER, tipo: str | None = F_TIPO,
                       altitud: Altitud | None = F_ALTITUD, columnas: str | None = F_COLUMNAS,
                       formato: Formato = Query(Formato.parquet, description="parquet (para el modelo) o csv")):
    """Todos los pitcheos que cumplan los filtros, en un solo archivo. Es lo que usa el modelo para entrenar.
    La descarga completa sin filtros se genera una vez y se guarda en memoria para las siguientes."""
    cols = separar_columnas(columnas)
    sin_filtros = all(v is None for v in (year, pitcher, tipo, altitud, cols))
    llave_cache = f"pitcheos.{formato.value}"
    if sin_filtros and llave_cache in DATOS["cache"]:
        log.info("Descarga completa servida desde caché")
        return DATOS["cache"][llave_cache]
    tabla = elegir_columnas(filtrar(DATOS["pitcheos"], year, pitcher, tipo, altitud), cols)
    respuesta = archivo(tabla, formato, "pitcheos")
    if sin_filtros:
        DATOS["cache"][llave_cache] = respuesta
    return respuesta


@app.get("/pitchers", tags=["pitcheos"], dependencies=PROTEGIDA, summary="Lista de pitchers")
def pitchers(min_pitcheos: int = Query(0, ge=0, description="Solo pitchers con al menos este número de pitcheos")):
    t = (DATOS["pitcheos"].filter(pl.col("pitcher_anon_id").is_not_null())
         .group_by("pitcher_anon_id")
         .agg(pitcheos=pl.len(), mano=pl.col("PitcherThrows").drop_nulls().first().cast(pl.String),
              temporadas=pl.col("year").unique().sort().cast(pl.Int64))
         .filter(pl.col("pitcheos") >= min_pitcheos)
         .sort("pitcher_anon_id"))
    return a_json(t)
