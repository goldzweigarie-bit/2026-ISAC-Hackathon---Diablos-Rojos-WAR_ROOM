#!/bin/bash
# Corre los modelos oficiales con los datos reales y sube sus resultados al API 2 (de ahí los toma la web app):
#   06  notebooks/06_StuffPlus.ipynb        Stuff+ con los XGBoost ya entrenados de modelos/  (Paso 9 sube)
#   03  notebooks/03_model_stuff_plus.ipynb BayesBall                                         (sección 7 sube)
#
# Antes, en OTRA Terminal:   bash apis/iniciar_todo.sh        (el API 2 tiene que estar prendido)
# Luego, desde la raíz:      bash apis/correr_modelos.sh      (los dos)
#                            bash apis/correr_modelos.sh 03   (solo uno)
#
# Los notebooks del repo NO se modifican: la copia con salidas queda en apis/logs/ (git la ignora).
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
LOGS="$REPO/apis/logs"
KERNEL="diablos-venv"
falla() { printf "\n✗ %b\n" "$1"; exit 1; }

[ -x "$PY" ] && [ -f "$REPO/apis/api2/.env" ] || falla "Primero corre: bash apis/instalar.sh"
curl -s -o /dev/null http://localhost:8001/salud || falla "El API 2 está apagado. En otra Terminal: bash apis/iniciar_todo.sh"
mkdir -p "$LOGS"

echo "== Librerías de los notebooks (la primera vez tarda 1-2 minutos)"
"$PY" -m pip install -q -r "$REPO/apis/requirements-modelos.txt"
"$PY" -c 'import xgboost' 2>/dev/null \
    || falla "xgboost no carga. En Mac casi siempre falta OpenMP. Instálalo con:  brew install libomp\n  y vuelve a correr:  bash apis/correr_modelos.sh"
# Un kernel de Jupyter dentro del .venv, para que los notebooks usen ESTE Python (y no otro de la compu)
"$PY" -m ipykernel install --prefix "$REPO/.venv" --name "$KERNEL" --display-name "Diablos (.venv)" >/dev/null 2>&1
echo "✓ $("$PY" -c 'import xgboost, sklearn, polars; print("xgboost", xgboost.__version__, "· scikit-learn", sklearn.__version__, "· polars", polars.__version__)')"

for n in ${@:-06 03}; do
    case "$n" in
        06) nb=06_StuffPlus.ipynb; que="Stuff+ (la primera vez entrena la prueba por temporada: puede tardar)" ;;
        03) nb=03_model_stuff_plus.ipynb; que="BayesBall" ;;
        *)  falla "No conozco el notebook '$n'. Usa 06 o 03." ;;
    esac
    echo; echo "== $nb · $que"
    (cd "$REPO/notebooks" && MPLBACKEND=Agg PATH="$REPO/.venv/bin:$PATH" \
        "$PY" "$REPO/apis/correr_notebook.py" "$nb" "$LOGS/${nb%.ipynb}_ejecutado.ipynb" "$KERNEL") \
        || falla "$nb falló (el error está arriba). La copia con todas las salidas: apis/logs/${nb%.ipynb}_ejecutado.ipynb"
done

echo
"$PY" - <<'FIN'
import json, urllib.request
try:
    m = json.load(urllib.request.urlopen("http://localhost:8002/api/meta", timeout=60))
except OSError:
    print("Listo. La web app no está prendida: con  bash apis/iniciar_todo.sh  ya usará los resultados nuevos.")
else:
    print("Listo. Web app: http://localhost:8002")
    print("   Stuff+:   ", m["model"] if m["model"] != "placeholder" else "PROVISIONAL (no se subió la tabla)")
    print("   BayesBall:", "sí" if m["sources"].get("bayesball") == "api2" else "no se subió la tabla")
FIN
