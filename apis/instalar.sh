#!/bin/bash
# Instala todo UNA vez (en cada compu del equipo), desde la raíz del repo:
#     bash apis/instalar.sh
# Los datos van FUERA del repo (es público). Por defecto en ~/Desktop/hackathon; para usar otra carpeta:
#     DATOS=/otra/carpeta bash apis/instalar.sh
# Esa carpeta necesita: stuff_model_df.pkl (o .parquet) y RunValueEvents.csv.
#
#   1. revisa que estén los archivos       5. convierte el pickle a Parquet (única vez que se usa pandas)
#   2. elige un Python 3.11 o más nuevo    6. corre las pruebas del API 1 (con los datos reales) y del API 2
#   3. crea el entorno .venv e instala     7. le pasa las llaves al traductor (su .env)
#   4. crea las llaves de los dos APIs
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DATOS="${DATOS:-$HOME/Desktop/hackathon}"
A1="$REPO/apis/api"
A2="$REPO/apis/api2"
T="$REPO/models/webapp/backend"
paso() { echo; echo "== $1"; }
falla() { printf "\n✗ %b\n" "$1"; exit 1; }
llave() { "$PY" -c 'import secrets; print(secrets.token_urlsafe(24))'; }
valor() { [ -f "$1" ] && grep "^$2=" "$1" | head -1 | cut -d= -f2- || true; }

paso "1. Archivos"
[ -d "$DATOS" ] || falla "No existe la carpeta de datos $DATOS (créala o usa DATOS=... bash apis/instalar.sh)"
[ -e "$DATOS/stuff_model_df.pkl" ] || [ -e "$DATOS/stuff_model_df.parquet" ] || falla "Falta $DATOS/stuff_model_df.pkl"
[ -e "$DATOS/RunValueEvents.csv" ] || falla "Falta $DATOS/RunValueEvents.csv"
[ -f "$A1/main.py" ] && [ -f "$A2/main.py" ] && [ -d "$T/app" ] || falla "Este repo no tiene apis/ y models/webapp/: ¿estás en la rama correcta?"
echo "✓ datos en $DATOS; APIs y traductor en el repo"

paso "2. Python"
SISTEMA=""
for p in python3.13 python3.12 python3.11 python3; do
    if command -v "$p" >/dev/null && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
        SISTEMA="$p"; break
    fi
done
[ -n "$SISTEMA" ] || falla "Hace falta Python 3.11 o más nuevo (tienes $(python3 --version 2>&1)). Instálalo de python.org."
echo "✓ $($SISTEMA --version)"

paso "3. Entorno .venv del repo e instalación (tarda 1-2 minutos la primera vez)"
[ -x "$REPO/.venv/bin/python" ] || "$SISTEMA" -m venv "$REPO/.venv"
PY="$REPO/.venv/bin/python"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "$A1/requirements.txt" -r "$T/requirements.txt"
echo "✓ $("$PY" -c 'import polars, fastapi; print("polars", polars.__version__, "· fastapi", fastapi.__version__)')"

paso "4. Llaves y carpetas (los .env NO se suben: el repo es público)"
# Si ya había llaves de una instalación anterior en la carpeta de datos, se reutilizan.
K1=$(valor "$A1/.env" API_KEY); [ -n "$K1" ] || K1=$(valor "$DATOS/api/.env" API_KEY); [ -n "$K1" ] || K1=$(llave)
K2=$(valor "$A2/.env" API_KEY); [ -n "$K2" ] || K2=$(valor "$DATOS/api2/.env" API_KEY); [ -n "$K2" ] || K2=$(llave)
K2W=$(valor "$A2/.env" API_KEY_ESCRITURA); [ -n "$K2W" ] || K2W=$(valor "$DATOS/api2/.env" API_KEY_ESCRITURA); [ -n "$K2W" ] || K2W=$(llave)
printf "API_KEY=%s\nDATOS_DIR=%s\n" "$K1" "$DATOS" > "$A1/.env"
printf "API_KEY=%s\nAPI_KEY_ESCRITURA=%s\nDATOS_DIR=%s\nRESULTADOS_DIR=%s\n" "$K2" "$K2W" "$DATOS" "$DATOS/resultados_api2" > "$A2/.env"
echo "✓ apis/api/.env y apis/api2/.env (datos y resultados en $DATOS)"

paso "5. Pickle → Parquet"
if [ -f "$DATOS/stuff_model_df.parquet" ]; then
    echo "✓ stuff_model_df.parquet ya existe"
else
    "$PY" -m pip install -q "pandas>=3" pyarrow
    "$PY" "$A1/convertir_pickle.py" "$DATOS/stuff_model_df.pkl"
    "$PY" -m pip uninstall -q -y pandas pyarrow          # ya no hace falta: todo lo demás es Polars
    echo "✓ pandas desinstalado del entorno"
fi

paso "6. Pruebas"
(cd "$A1" && "$PY" -m pytest -q -p no:cacheprovider 2>&1 | tail -1)
(cd "$A2" && "$PY" -m pytest -q -p no:cacheprovider 2>&1 | tail -1)

paso "7. Traductor"
printf "API1_URL=http://localhost:8000\nAPI1_KEY=%s\nAPI2_URL=http://localhost:8001\nAPI2_KEY=%s\n" "$K1" "$K2" > "$T/.env"
echo "✓ models/webapp/backend/.env con la llave del API 1 y la de LECTURA del API 2"

paso "Revisión: git no debe ver datos ni llaves"
SUCIO=$(git -C "$REPO" status --porcelain --untracked-files=all | grep -E '\.env$|\.pkl$|\.parquet$|\.venv/|resultados_api2|logs/' || true)
[ -z "$SUCIO" ] || falla "git ve archivos que NO deben subirse:\n$SUCIO"
echo "✓ git ignora los .env, los datos y el .venv"

echo
echo "Listo. Para prender todo:  bash apis/iniciar_todo.sh"
echo "Llave de ESCRITURA del API 2 (el notebook la lee sola): apis/api2/.env"
