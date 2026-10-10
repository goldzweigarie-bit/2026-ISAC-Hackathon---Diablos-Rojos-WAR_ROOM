#!/bin/bash
# Prende API 1 (:8000), API 2 (:8001) y el traductor con la web app (:8002), y abre el navegador.
# Desde la raíz del repo:   bash apis/iniciar_todo.sh        Ctrl+C apaga los tres.
# Los mensajes de cada uno quedan en apis/logs/ (git los ignora).
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
LOGS="$REPO/apis/logs"
[ -x "$PY" ] && [ -f "$REPO/apis/api/.env" ] || { echo "Primero corre: bash apis/instalar.sh"; exit 1; }
mkdir -p "$LOGS"

apagar() { echo; echo "Apagando..."; kill $(jobs -p) 2>/dev/null; wait 2>/dev/null; exit "${1:-0}"; }
trap apagar INT TERM
esperar() {                     # espera a que una dirección responda (máx. 120 s)
    for _ in $(seq 1 120); do curl -s -o /dev/null "$1" && return 0; sleep 1; done; return 1
}
fallo() { echo "✗ $1 no arrancó. Últimas líneas de apis/logs/$2:"; tail -20 "$LOGS/$2"; apagar 1; }
for puerto in 8000 8001 8002; do
    if curl -s -o /dev/null "http://localhost:$puerto"; then
        echo "✗ El puerto $puerto ya está ocupado (¿quedó algo prendido en otra Terminal?)."; exit 1
    fi
done

(cd "$REPO/apis/api" && exec "$PY" -m uvicorn main:app --port 8000 > "$LOGS/api1.log" 2>&1) &
(cd "$REPO/apis/api2" && exec "$PY" -m uvicorn main:app --port 8001 > "$LOGS/api2.log" 2>&1) &
esperar http://localhost:8000/salud || fallo "API 1" api1.log
echo "✓ API 1  http://localhost:8000/docs   $(curl -s localhost:8000/salud)"
esperar http://localhost:8001/salud || fallo "API 2" api2.log
echo "✓ API 2  http://localhost:8001/docs   $(curl -s localhost:8001/salud)"

(cd "$REPO/models/webapp/backend" && exec "$PY" -m uvicorn app.main:app --port 8002 > "$LOGS/traductor.log" 2>&1) &
esperar http://localhost:8002/api/meta || fallo "El traductor" traductor.log
echo "✓ Web app http://localhost:8002"
curl -s localhost:8002/api/meta | "$PY" -c '
import json, sys
m = json.load(sys.stdin)
stuff = "PROVISIONAL (el modelo aún no sube su tabla al API 2)" if m["model"] == "placeholder" else m["model"]
temporadas, fuentes = m["seasons"], m["sources"]
print(f"   Stuff+: {stuff}")
print(f"   Temporadas: {temporadas} · fuentes: {fuentes}")'
command -v open >/dev/null && open http://localhost:8002
echo
echo "Todo prendido. Ctrl+C para apagar. El notebook del modelo, al subir su tabla, recarga la app solo."
wait
