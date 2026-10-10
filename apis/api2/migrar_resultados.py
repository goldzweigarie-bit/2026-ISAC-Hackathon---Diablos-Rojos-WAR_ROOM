"""
Sube al API 2 las tablas que el notebook ya exportó a la carpeta resultados/ (las que antes servía el API 1).
Se corre UNA vez, con el API 2 prendido. Desde la carpeta api2/:

    python3 migrar_resultados.py "../resultados"

Usa la llave de ESCRITURA de api2/.env. Sube cada *.csv y *.parquet de esa carpeta con modelo="stuff_plus".
Los pickles (*.pkl) son de pandas: conviértelos antes con  python3 ../api/convertir_pickle.py ruta/al/archivo.pkl
"""
import os
import sys
from pathlib import Path

import polars as pl

CARPETA_API2 = Path(__file__).resolve().parent
sys.path.insert(0, str(CARPETA_API2.parent / "api"))     # cliente.py vive en api/
from cliente import ClienteAPI2  # noqa: E402

from main import cargar_env  # noqa: E402  (reutiliza el lector de .env del API 2)

cargar_env(CARPETA_API2 / ".env")


def main() -> None:
    datos = Path(os.path.expanduser(os.getenv("DATOS_DIR", str(CARPETA_API2.parent))))
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else datos / "resultados")
    if not carpeta.exists():
        sys.exit(f"No existe {carpeta}")
    api2 = ClienteAPI2(os.getenv("API2_URL", "http://localhost:8001"), os.environ["API_KEY_ESCRITURA"])
    pickles = sorted(carpeta.glob("*.pkl"))
    sin_convertir = [p for p in pickles if not p.with_suffix(".parquet").exists()]
    if sin_convertir:
        sys.exit("Primero convierte estos pickles a Parquet (una vez):\n  python3 ../api/convertir_pickle.py "
                 + " ".join(f'"{p}"' for p in sin_convertir))
    archivos = sorted(carpeta.glob("*.csv")) + sorted(carpeta.glob("*.parquet"))
    if not archivos:
        sys.exit(f"No hay .csv ni .parquet en {carpeta}")
    for archivo in archivos:
        df = pl.read_csv(archivo) if archivo.suffix == ".csv" else pl.read_parquet(archivo)
        nombre = archivo.stem.lower().replace("-", "_").replace(" ", "_")
        r = api2.subir(nombre, df, modelo="stuff_plus", version="migrado_de_api1")
        print(f"✓ {nombre}: {r['renglones']:,} renglones")


if __name__ == "__main__":
    main()
