"""
Clientes de los dos APIs. Es lo que usan los notebooks de los modelos (y el traductor de la web app).

    ClienteAPI1  → LEE los datos (pitcheos y constantes)          puerto 8000
    ClienteAPI2  → SUBE y LEE los resultados de los modelos       puerto 8001

Las tablas son DataFrames de Polars. Si un notebook sigue en pandas: df.to_pandas() para recibir, y
subir() acepta también un DataFrame de pandas (lo detecta solo, sin que este archivo importe pandas).

Uso desde un modelo:
    from cliente import ClienteAPI1, ClienteAPI2
    api1 = ClienteAPI1("http://localhost:8000", "LLAVE_API1")
    api2 = ClienteAPI2("http://localhost:8001", "LLAVE_ESCRITURA_API2")
    df = api1.pitcheos()                                        # todo el dataset como DataFrame
    VALOR_EVENTO = api1.valor_evento()
    ...                                                         # entrenar, predecir
    api2.subir("stuff_plus_por_pitcher", por_pitcher, modelo="stuff_plus", version="v3")

Si no les pasas URL y llave, las toman de las variables de entorno API1_URL / API1_KEY
y API2_URL / API2_KEY.
"""
import io
import os

import polars as pl
import requests


class ClienteAPI1:
    def __init__(self, url: str | None = None, llave: str | None = None, timeout: int = 300):
        self.url = (url or os.getenv("API1_URL", "http://localhost:8000")).rstrip("/")   # sin "/" al final
        llave = llave or os.getenv("API1_KEY")
        if not llave:
            raise ValueError("Falta la llave: pásala como argumento o define la variable API1_KEY")
        self.sesion = requests.Session()                      # reutiliza la conexión entre peticiones
        self.sesion.headers["X-API-Key"] = llave              # la llave va en TODAS las peticiones
        self.timeout = timeout                                # segundos máximos de espera por respuesta

    # ---- utilidades internas ------------------------------------------------------------------
    def _get(self, ruta: str, **params) -> requests.Response:
        """GET a una ruta. Quita los filtros vacíos y convierte errores HTTP en mensajes claros."""
        params = {k: v for k, v in params.items() if v is not None}
        if isinstance(params.get("columnas"), (list, tuple)):
            params["columnas"] = ",".join(params["columnas"])
        r = self.sesion.get(f"{self.url}{ruta}", params=params, timeout=self.timeout,
                            headers={"Accept-Encoding": "identity"} if ruta.endswith("descargar") else None)
        if r.status_code != 200:
            detalle = r.json().get("detail") if "json" in r.headers.get("content-type", "") else r.text
            raise RuntimeError(f"API 1 respondió {r.status_code} en {ruta}: {detalle}")
        return r

    # ---- lo que usa el modelo -----------------------------------------------------------------
    def salud(self) -> dict:
        return self._get("/salud").json()

    def constantes(self) -> dict:
        """Pesos wOBA de FanGraphs, la temporada y la fuente."""
        return self._get("/constantes/carreras").json()

    def valor_evento(self) -> dict:
        """Diccionario evento → carreras, listo para usar como VALOR_EVENTO."""
        return self.constantes()["valor_evento"]

    def pitcheos(self, year=None, pitcher=None, tipo=None, altitud=None, columnas=None) -> pl.DataFrame:
        """Descarga los pitcheos (Parquet) y los devuelve como DataFrame de Polars. Sin filtros = todo el dataset."""
        r = self._get("/pitcheos/descargar", year=year, pitcher=pitcher, tipo=tipo,
                      altitud=altitud, columnas=columnas, formato="parquet")
        return pl.read_parquet(io.BytesIO(r.content))


class ClienteAPI2:
    """Sube y lee las tablas de resultados del API 2.
    Para SUBIR hace falta la llave de escritura; para solo leer (traductor) basta la de lectura."""

    def __init__(self, url: str | None = None, llave: str | None = None, timeout: int = 300):
        self.url = (url or os.getenv("API2_URL", "http://localhost:8001")).rstrip("/")
        llave = llave or os.getenv("API2_KEY")
        if not llave:
            raise ValueError("Falta la llave: pásala como argumento o define la variable API2_KEY")
        self.sesion = requests.Session()
        self.sesion.headers["X-API-Key"] = llave
        self.timeout = timeout

    def _revisar(self, r: requests.Response, ruta: str) -> requests.Response:
        if r.status_code != 200:
            detalle = r.json().get("detail") if "json" in r.headers.get("content-type", "") else r.text
            raise RuntimeError(f"API 2 respondió {r.status_code} en {ruta}: {detalle}")
        return r

    def salud(self) -> dict:
        return self._revisar(self.sesion.get(f"{self.url}/salud", timeout=self.timeout), "/salud").json()

    def tablas(self) -> dict:
        """Qué tablas hay, quién las subió, su versión y cuándo."""
        ruta = "/resultados"
        return self._revisar(self.sesion.get(f"{self.url}{ruta}", timeout=self.timeout), ruta).json()

    def subir(self, tabla: str, df, modelo: str, version: str = "") -> dict:
        """Sube (o reemplaza) una tabla. La versión anterior queda guardada en el historial del API 2.
        tabla: solo minúsculas, números y "_", p. ej. 'stuff_plus_por_pitcher'.
        df: DataFrame de Polars (o de pandas, si el notebook todavía lo usa)."""
        buffer = io.BytesIO()
        if isinstance(df, pl.DataFrame):
            df.write_parquet(buffer)
        else:                                                   # pandas: tiene su propio to_parquet
            df.to_parquet(buffer, index=False)
        ruta = f"/resultados/{tabla}"
        r = self.sesion.post(f"{self.url}{ruta}", params={"modelo": modelo, "version": version},
                             data=buffer.getvalue(), timeout=self.timeout,
                             headers={"Content-Type": "application/vnd.apache.parquet"})
        return self._revisar(r, ruta).json()

    def leer(self, tabla: str, **filtros) -> pl.DataFrame:
        """Una tabla como DataFrame. Filtros opcionales: year, pitcher, tipo, altitud, columnas."""
        filtros = {k: v for k, v in filtros.items() if v is not None}
        if isinstance(filtros.get("columnas"), (list, tuple)):
            filtros["columnas"] = ",".join(filtros["columnas"])
        ruta = f"/resultados/{tabla}/descargar"
        r = self.sesion.get(f"{self.url}{ruta}", params={**filtros, "formato": "parquet"}, timeout=self.timeout,
                            headers={"Accept-Encoding": "identity"})
        return pl.read_parquet(io.BytesIO(self._revisar(r, ruta).content))
