# API 1; 600,000 pitcheos y run value

```
API 1 (datos)  →  Modelos (Stuff+, BayesBall)  →  API 2 (resultados)  → Traductor → WebApp
   ↑ este
```

Entrega por HTTP el dataset de pitcheos y las constantes de carreras de FanGraphs, para que nadie
dependa de archivos en su computadora. **Solo datos de entrada:** lo que producen los modelos se sube
al API 2 (carpeta `apis/api2/`, puerto 8001).

> **Lo normal es no hacer esto a mano:** `bash apis/instalar.sh` y `bash apis/iniciar_todo.sh` desde la raíz del repo hacen todo (ver [`apis/README.md`](../README.md)). Lo de abajo es el detalle, por si algo falla.


## Archivos

| Archivo | Qué es |
|---|---|
| `main.py` | el API (FastAPI + Polars) |
| `cliente.py` | cómo se conecta el modelo: `ClienteAPI1` (leer datos) y `ClienteAPI2` (subir resultados) |
| `convertir_pickle.py` | pasa `stuff_model_df.pkl` a Parquet **una sola vez** (el único script que usa pandas) |
| `test_api.py` | 10 pruebas automáticas |
| `iniciar.sh` | arranca el servidor |
| `.env.example` | plantilla de configuración (la llave y las rutas) |
| `.env` | tu configuración real — **nunca a GitHub** |
| `requirements.txt` | dependencias |

El API necesita, en la carpeta de datos **fuera del repo** (`DATOS_DIR` en `apis/api/.env`, por defecto
`~/Desktop/hackathon`): `stuff_model_df.parquet` y `RunValueEvents.csv`.

**No usa pandas.** Las tablas son de Polars. El pickle original es un objeto de pandas que Polars no puede
abrir, así que se convierte a Parquet una sola vez (paso 1b) y después pandas ya no hace falta.

## 1. Instalar (una sola vez)

Python 3.11 o superior.

```bash
cd apis/api
python3 -m pip install -r requirements.txt
cp .env.example .env          # pon API_KEY y DATOS_DIR
```

Edita `.env` y pon una `API_KEY` de al menos 12 caracteres. Para generar una:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 1b. Convertir el pickle a Parquet (una sola vez)

```bash
python3 -m pip install "pandas>=3" pyarrow      # solo para esta conversión
python3 convertir_pickle.py
```

Crea `stuff_model_df.parquet` junto al `.pkl` y comprueba que tenga los mismos renglones, columnas y vacíos.
Después puedes desinstalar pandas (`python3 -m pip uninstall pandas pyarrow`). Si el API arranca sin el
Parquet, te dice que corras este paso.

## 2. Arrancar

```bash
./iniciar.sh            # solo esta Mac
./iniciar.sh red        # también otras computadoras de la misma Wi-Fi
```

Espera la línea `Listo: 635,002 pitcheos | constantes 2026` (menos de 1 s con Parquet).
Para detenerlo: `Ctrl+C`.

## 3. Abrirlo

**http://localhost:8000/docs** en el navegador. Ahí ves todas las rutas y las puedes probar:

1. Botón **Authorize** (arriba a la derecha) → pega la `API_KEY` de tu `.env` → **Authorize** → **Close**.
2. Abre una ruta (por ejemplo `GET /pitcheos`) → **Try it out** → llena filtros → **Execute**.
3. Abajo aparece la respuesta, el código (200 = bien) y el comando `curl` equivalente.

## 4. Comprobar que todo está bien

```bash
python3 -m pytest -v
```

Las 10 pruebas deben pasar. Revisan la llave, los filtros, la paginación, los errores y que
lo que entrega el API sea idéntico a los datos cargados.

## 5. Rutas

| Ruta | Devuelve |
|---|---|
| `GET /salud` | estado del servidor (sin llave) |
| `GET /constantes/carreras` | pesos wOBA del CSV y `valor_evento` en carreras |
| `GET /columnas` | columnas del dataset y su tipo |
| `GET /pitcheos/resumen` | pitcheos por temporada y altitud |
| `GET /pitcheos` | pitcheos en JSON, por páginas (`limit`, `offset`) |
| `GET /pitcheos/descargar` | pitcheos como archivo Parquet o CSV (para el modelo) |
| `GET /pitchers` | lista de pitchers |

Las rutas `/resultados` se mudaron al **API 2** (versión 2.0 de este API).

Filtros comunes: `year`, `pitcher`, `tipo`, `altitud` (`No Altitude`, `Medium Altitude`,
`Extreme Altitude`) y `columnas` (separadas por coma).

**¿JSON o descargar?** JSON para consultas chicas (el dashboard). Descargar (Parquet) para
miles de renglones (el modelo): el dataset completo llega en ~8 s.

## 6. Usarlo desde el modelo (Python)

```python
import sys; sys.path.append("../apis/api")         # desde notebooks/ (el Paso 9 del notebook lo busca solo)
from cliente import ClienteAPI1, ClienteAPI2

api = ClienteAPI1("http://localhost:8000", "TU_LLAVE")
df = api.pitcheos()                                 # todo el dataset, como DataFrame de Polars
# df.to_pandas() si el notebook todavía usa pandas; subir() acepta Polars o pandas
VALOR_EVENTO = api.valor_evento()                   # constantes de FanGraphs en carreras
pitcher = api.pitcheos(pitcher="pitcher_00386", year=2025)

# al final del modelo, los resultados van al API 2 (ver api2/README.md)
api2 = ClienteAPI2("http://localhost:8001", "LLAVE_ESCRITURA_API2")
api2.subir("stuff_plus_por_pitcher", por_pitcher, modelo="stuff_plus", version="v3")
```

Para no escribir la llave en el notebook, defínela como variable de entorno (`API1_URL`,
`API1_KEY`) y usa `ClienteAPI1()` sin argumentos.

## 7. Conectarse desde otra computadora

**Misma Wi-Fi:** arranca con `./iniciar.sh red`; imprime la dirección (`http://192.168.x.x:8000`).
Si macOS pregunta si Python puede aceptar conexiones entrantes, responde **Permitir**.

**Desde internet:** túnel con ngrok (`brew install ngrok`, cuenta gratuita):

```bash
ngrok http 8000
```

Da una URL pública `https://....ngrok-free.app` que cambia cada vez que se reinicia (plan gratuito).
La llave sigue protegiendo los datos.

## Notas sobre los datos

- Los vacíos son `null` en Polars (`is_null()`). Los `NaN` de pandas se convirtieron a `null` al pasar a
  Parquet, porque en pandas un `NaN` significa "vacío".
- `valor_evento` = peso wOBA ÷ wOBAScale (carreras respecto a un out). `Error` vale como
  `Single` y `Sacrifice`/`FieldersChoice` como `Out`: decisiones del proyecto.
