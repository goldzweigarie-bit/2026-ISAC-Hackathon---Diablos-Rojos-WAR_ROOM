"""
API 2 — Resultados de los modelos (Diablos Rojos, ISAC 2026)

    API 1 (datos)  →  Modelos (Stuff+, BayesBall)  →  API 2 (resultados)  →  Traductor  →  WebApp
                                                        ↑ este

Los modelos SUBEN aquí sus tablas de resultados (Stuff+ por pitcheo, por pitcher, lo de BayesBall...)
y el traductor de la web app las LEE. El API no calcula nada: guarda y entrega.

  - Cada tabla se guarda como Parquet en RESULTADOS_DIR, así sobrevive a un reinicio.
  - Cada vez que se sube una tabla, la versión anterior se guarda en RESULTADOS_DIR/historial/.
  - Dos llaves: una de LECTURA (traductor, dashboard) y otra de ESCRITURA (solo los modelos).

Arrancar (desde la carpeta apis/api2/), o todo junto con  bash apis/iniciar_todo.sh :
    python3 -m uvicorn main:app --port 8001
Documentación interactiva:
    http://localhost:8001/docs
"""
import io                                             # leer y escribir archivos en memoria
import json                                           # tablas → JSON y el archivo de metadatos
import logging                                        # mensajes en la terminal con hora y nivel
import os                                             # variables de entorno
import re                                             # validar nombres de tabla
import secrets                                        # comparar llaves de forma segura
from contextlib import asynccontextmanager            # cargar las tablas una sola vez al arrancar
from datetime import datetime, timezone               # fecha de cada subida
from enum import Enum                                 # listas cerradas de valores válidos
from pathlib import Path                              # rutas que funcionan en Mac, Windows y Linux

import polars as pl                                   # tablas
import polars.selectors as cs                         # elegir columnas por tipo
from fastapi import FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware    # permite que un navegador llame al API
from fastapi.middleware.gzip import GZipMiddleware    # comprime las respuestas grandes
from fastapi.responses import Response                # para devolver archivos (Parquet, CSV)
from fastapi.security import APIKeyHeader             # lee la llave del encabezado de cada petición

VERSION = "1.0.0"
log = logging.getLogger("api2")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


# ==============================================================================================
# 1. CONFIGURACIÓN (todo viene de api2/.env, igual que en el API 1)
# ==============================================================================================
CARPETA_API = Path(__file__).resolve().parent


def cargar_env(ruta: Path) -> None:
    """Lee un archivo .env (líneas CLAVE=valor). Las variables que ya existan en el sistema ganan."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


cargar_env(CARPETA_API / ".env")

# Dónde se guardan las tablas: RESULTADOS_DIR, o DATOS_DIR/resultados_api2. Siempre FUERA del repo (es público).
_DATOS = Path(os.path.expanduser(os.getenv("DATOS_DIR", str(CARPETA_API.parent))))
CARPETA_RESULTADOS = Path(os.path.expanduser(os.getenv("RESULTADOS_DIR", str(_DATOS / "resultados_api2"))))
CARPETA_HISTORIAL = CARPETA_RESULTADOS / "historial"
ARCHIVO_META = CARPETA_RESULTADOS / "_metadatos.json"
API_KEY = os.getenv("API_KEY", "")                          # lectura
API_KEY_ESCRITURA = os.getenv("API_KEY_ESCRITURA", "")      # subir y borrar tablas
LIMITE_JSON = 50_000
NOMBRE_VALIDO = re.compile(r"^[a-z0-9_]{1,64}$")            # minúsculas, números y "_": nada de "../"


class Altitud(str, Enum):
    no = "No Altitude"
    media = "Medium Altitude"
    extrema = "Extreme Altitude"


class Formato(str, Enum):
    parquet = "parquet"
    csv = "csv"


DATOS: dict = {"tablas": {}, "meta": {}}    # memoria del servidor: tablas y sus metadatos


# ==============================================================================================
# 2. GUARDAR Y CARGAR TABLAS
# ==============================================================================================
def ruta_tabla(nombre: str) -> Path:
    return CARPETA_RESULTADOS / f"{nombre}.parquet"


def guardar_meta() -> None:
    ARCHIVO_META.write_text(json.dumps(DATOS["meta"], indent=2, ensure_ascii=False), encoding="utf-8")


def validar_nombre(nombre: str) -> str:
    if not NOMBRE_VALIDO.match(nombre):
        raise HTTPException(status_code=422,
                            detail="Nombre de tabla inválido: solo minúsculas, números y '_' (máx. 64)")
    return nombre


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Al arrancar: revisa las llaves y carga a memoria todas las tablas guardadas."""
    for nombre_var, llave in (("API_KEY", API_KEY), ("API_KEY_ESCRITURA", API_KEY_ESCRITURA)):
        if len(llave) < 12:
            raise RuntimeError(f"{nombre_var} falta o es muy corta (mínimo 12 caracteres). Revisa api2/.env")
    if API_KEY == API_KEY_ESCRITURA:
        raise RuntimeError("API_KEY y API_KEY_ESCRITURA deben ser distintas. Revisa api2/.env")
    CARPETA_HISTORIAL.mkdir(parents=True, exist_ok=True)

    DATOS["meta"] = json.loads(ARCHIVO_META.read_text(encoding="utf-8")) if ARCHIVO_META.exists() else {}
    DATOS["tablas"] = {}
    for archivo in sorted(CARPETA_RESULTADOS.glob("*.parquet")):
        DATOS["tablas"][archivo.stem] = pl.read_parquet(archivo)
    log.info("Listo: %d tablas en %s: %s", len(DATOS["tablas"]), CARPETA_RESULTADOS, sorted(DATOS["tablas"]))
    yield
    DATOS["tablas"].clear()
    log.info("Servidor apagado")


# ==============================================================================================
# 3. LA APLICACIÓN Y SU SEGURIDAD
# ==============================================================================================
app = FastAPI(
    title="API 2 · Resultados Stuff+ y BayesBall",
    description=("Tablas de resultados que suben los modelos. **Leer** pide la llave de lectura; **subir o "
                 "borrar** pide la llave de escritura. Ambas van en el encabezado `X-API-Key`. "
                 "En esta página: botón **Authorize** (arriba a la derecha)."),
    version=VERSION,
    lifespan=ciclo_de_vida,
)
# El navegador solo puede LEER; subir se hace desde Python (el notebook), que no pasa por CORS.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

llave_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                            description="Llave de lectura o de escritura definida en api2/.env")


def puede_leer(llave: str | None = Security(llave_header)) -> None:
    """Para leer sirve cualquiera de las dos llaves."""
    if not llave or not (secrets.compare_digest(llave, API_KEY) or secrets.compare_digest(llave, API_KEY_ESCRITURA)):
        raise HTTPException(status_code=401, detail="Llave inválida o ausente (encabezado X-API-Key)")


def puede_escribir(llave: str | None = Security(llave_header)) -> None:
    """Para subir o borrar solo sirve la llave de escritura."""
    if not llave or not secrets.compare_digest(llave, API_KEY_ESCRITURA):
        raise HTTPException(status_code=403, detail="Se necesita la llave de ESCRITURA para modificar tablas")


LECTURA = [Security(puede_leer)]
ESCRITURA = [Security(puede_escribir)]


# ==============================================================================================
# 4. FUNCIONES DE APOYO (las mismas que en el API 1)
# ==============================================================================================
def a_json(tabla: pl.DataFrame) -> list:
    """DataFrame → lista de diccionarios. Los NaN se vuelven null, porque JSON no acepta NaN."""
    return tabla.with_columns(cs.float().fill_nan(None)).to_dicts()


def separar_columnas(texto: str | None) -> list | None:
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
        condiciones.append(pl.col(col_tipo).cast(pl.String) == tipo)
    if altitud is not None and "altitude_category" in columnas:
        condiciones.append(pl.col("altitude_category").cast(pl.String) == altitud.value)
    return tabla.filter(*condiciones) if condiciones else tabla


def elegir_columnas(tabla: pl.DataFrame, columnas: list | None) -> pl.DataFrame:
    if not columnas:
        return tabla
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        raise HTTPException(status_code=400, detail=f"Columnas inexistentes: {faltan}")
    return tabla.select(columnas)


def paginar(tabla: pl.DataFrame, limit: int, offset: int) -> dict:
    pedazo = tabla.slice(offset, limit)
    return {"total": tabla.height, "offset": offset, "n": pedazo.height, "registros": a_json(pedazo)}


def archivo(tabla: pl.DataFrame, formato: Formato, nombre: str) -> Response:
    buffer = io.BytesIO()
    if formato == Formato.parquet:
        tabla.write_parquet(buffer)
        tipo_mime = "application/vnd.apache.parquet"
    else:
        tabla.write_csv(buffer)
        tipo_mime = "text/csv"
    return Response(content=buffer.getvalue(), media_type=tipo_mime,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}.{formato.value}"'})


def tabla_existente(nombre: str) -> pl.DataFrame:
    if nombre not in DATOS["tablas"]:
        raise HTTPException(status_code=404, detail=f"No existe '{nombre}'. Disponibles: {sorted(DATOS['tablas'])}")
    return DATOS["tablas"][nombre]


F_YEAR = Query(None, description="Temporada, p. ej. 2025")
F_PITCHER = Query(None, description="pitcher_anon_id, p. ej. pitcher_00386")
F_TIPO = Query(None, description="Tipo de pitcheo, p. ej. Slider")
F_ALTITUD = Query(None, description="Nivel de altitud")
F_COLUMNAS = Query(None, description="Columnas separadas por coma; vacío = todas")


# ==============================================================================================
# 5. RUTAS
# ==============================================================================================
@app.get("/salud", tags=["sistema"], summary="¿Está vivo el servidor?")
def salud():
    """No pide llave."""
    return {"ok": True, "version": VERSION, "tablas": sorted(DATOS["tablas"])}


# ---- Leer (traductor, dashboard, notebook) -----------------------------------------------------
@app.get("/resultados", tags=["leer"], dependencies=LECTURA, summary="Tablas disponibles y sus metadatos")
def resultados_disponibles():
    """Para cada tabla: renglones, columnas, qué modelo la subió, su versión y cuándo."""
    return {n: {"renglones": t.height, "columnas": t.columns, **DATOS["meta"].get(n, {})}
            for n, t in DATOS["tablas"].items()}


@app.get("/resultados/{tabla}", tags=["leer"], dependencies=LECTURA, summary="Una tabla en JSON (por páginas)")
def resultados(tabla: str, year: int | None = F_YEAR, pitcher: str | None = F_PITCHER, tipo: str | None = F_TIPO,
               altitud: Altitud | None = F_ALTITUD, columnas: str | None = F_COLUMNAS,
               limit: int = Query(5000, ge=1, le=LIMITE_JSON), offset: int = Query(0, ge=0)):
    t = filtrar(tabla_existente(tabla), year, pitcher, tipo, altitud)
    return paginar(elegir_columnas(t, separar_columnas(columnas)), limit, offset)


@app.get("/resultados/{tabla}/descargar", tags=["leer"], dependencies=LECTURA, summary="Una tabla como archivo")
def resultados_descargar(tabla: str, year: int | None = F_YEAR, pitcher: str | None = F_PITCHER,
                         tipo: str | None = F_TIPO, altitud: Altitud | None = F_ALTITUD,
                         columnas: str | None = F_COLUMNAS, formato: Formato = Formato.parquet):
    t = filtrar(tabla_existente(tabla), year, pitcher, tipo, altitud)
    return archivo(elegir_columnas(t, separar_columnas(columnas)), formato, tabla)


# ---- Escribir (solo los modelos) ---------------------------------------------------------------
@app.post("/resultados/{tabla}", tags=["escribir"], dependencies=ESCRITURA,
          summary="Subir (o reemplazar) una tabla en Parquet")
async def subir(request: Request, tabla: str,
                modelo: str = Query(..., description="Quién la produce: stuff_plus, bayesball..."),
                version: str = Query("", description="Versión del modelo, p. ej. v3 o el commit")):
    """El cuerpo de la petición es el archivo Parquet. Si la tabla ya existía, la anterior se guarda
    en historial/ antes de reemplazarla. Lo más fácil es usar `ClienteAPI2.subir()` de cliente.py."""
    validar_nombre(tabla)
    cuerpo = await request.body()
    if not cuerpo:
        raise HTTPException(status_code=400, detail="Cuerpo vacío: manda la tabla como Parquet")
    try:
        nueva = pl.read_parquet(io.BytesIO(cuerpo))
    except Exception as e:  # noqa: BLE001 — cualquier archivo ilegible es culpa de quien lo manda
        raise HTTPException(status_code=400, detail=f"El cuerpo no es un Parquet válido: {e}") from e

    ahora = datetime.now(timezone.utc)
    destino = ruta_tabla(tabla)
    if destino.exists():                                              # guarda la versión anterior
        anterior = DATOS["meta"].get(tabla, {})
        sello = anterior.get("subido", ahora.isoformat()).replace(":", "").replace("-", "")[:15]
        etiqueta = re.sub(r"[^A-Za-z0-9_.-]", "_", anterior.get("version") or "sin_version")   # seguro como nombre
        destino.replace(CARPETA_HISTORIAL / f"{tabla}__{sello}__{etiqueta}.parquet")
    nueva.write_parquet(destino)

    DATOS["tablas"][tabla] = nueva
    DATOS["meta"][tabla] = {"modelo": modelo, "version": version, "subido": ahora.isoformat(timespec="seconds"),
                            "renglones": nueva.height}
    guardar_meta()
    log.info("Subida '%s' (%s %s): %s renglones", tabla, modelo, version, f"{nueva.height:,}")
    return {"ok": True, "tabla": tabla, **DATOS["meta"][tabla]}


@app.delete("/resultados/{tabla}", tags=["escribir"], dependencies=ESCRITURA, summary="Borrar una tabla")
def borrar(tabla: str):
    """La tabla deja de servirse, pero el archivo se mueve a historial/: nada se pierde."""
    validar_nombre(tabla)
    tabla_existente(tabla)
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    ruta_tabla(tabla).replace(CARPETA_HISTORIAL / f"{tabla}__{sello}__borrada.parquet")
    del DATOS["tablas"][tabla]
    DATOS["meta"].pop(tabla, None)
    guardar_meta()
    log.info("Borrada '%s'", tabla)
    return {"ok": True, "tabla": tabla}
