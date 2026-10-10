"""
Convierte stuff_model_df.pkl a stuff_model_df.parquet. Se corre UNA sola vez, desde la carpeta api/:

    python3 convertir_pickle.py                       # el pickle de DATOS_DIR (apis/api/.env)
    python3 convertir_pickle.py ruta/a/otro.pkl ...   # cualquier otro pickle (p. ej. resultados viejos)

Un pickle de pandas solo lo puede abrir pandas, así que este es el ÚNICO lugar del proyecto donde se
usa pandas. Después de convertir, los APIs y el traductor leen el Parquet con Polars y pandas ya no hace
falta (puedes desinstalarlo).

Necesita, solo para esta corrida:  python3 -m pip install "pandas>=3" pyarrow polars
"""
import os
import sys
from pathlib import Path

CARPETA_API = Path(__file__).resolve().parent


def carpeta_datos() -> Path:
    """DATOS_DIR de apis/api/.env (o del sistema); si no hay, la carpeta de arriba."""
    if "DATOS_DIR" not in os.environ and (CARPETA_API / ".env").exists():
        for linea in (CARPETA_API / ".env").read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith("DATOS_DIR="):
                return Path(os.path.expanduser(linea.split("=", 1)[1].strip().strip('"').strip("'")))
    return Path(os.path.expanduser(os.getenv("DATOS_DIR", str(CARPETA_API.parent))))


def convertir(origen: Path) -> Path:
    try:
        import pandas as pd
    except ImportError:
        sys.exit('Este script necesita pandas una sola vez:  python3 -m pip install "pandas>=3" pyarrow')
    import polars as pl

    destino = origen.with_suffix(".parquet")
    original = pd.read_pickle(origen)
    # nan_to_null: en pandas un NaN significa "vacío"; en Polars eso es null (NaN queda solo para float de verdad)
    tabla = pl.from_pandas(original, nan_to_null=True)
    tabla.write_parquet(destino)

    # Comprobación: mismo número de renglones y columnas, mismos nombres, y releer el archivo funciona
    releido = pl.read_parquet(destino)
    assert releido.shape == original.shape, f"forma distinta: {releido.shape} vs {original.shape}"
    assert releido.columns == [str(c) for c in original.columns], "columnas distintas"
    for col in original.columns:                                       # mismos vacíos en cada columna
        assert releido[str(col)].null_count() == int(original[col].isna().sum()), f"vacíos distintos en {col}"
    print(f"✓ {origen.name} → {destino.name}: {releido.height:,} renglones × {releido.width} columnas")
    return destino


def main() -> None:
    rutas = [Path(p) for p in sys.argv[1:]] or [carpeta_datos() / "stuff_model_df.pkl"]
    for ruta in rutas:
        if not ruta.exists():
            sys.exit(f"No existe {ruta}")
        convertir(ruta)


if __name__ == "__main__":
    main()
