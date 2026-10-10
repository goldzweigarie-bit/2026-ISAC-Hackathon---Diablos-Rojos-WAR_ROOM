#!/bin/bash
# Arranca el API 2. Uso:  ./iniciar.sh          (solo esta Mac)
#                         ./iniciar.sh red      (también otras computadoras de la misma red)
cd "$(dirname "$0")"                                   # se mueve a la carpeta api2/, la llames desde donde la llames
PYTHON="${PYTHON:-$([ -x ../../.venv/bin/python ] && echo ../../.venv/bin/python || echo python3)}"   # el .venv del repo si existe

if [ ! -f .env ]; then
    echo "Falta api2/.env. Cópialo de .env.example y pon tu API_KEY y API_KEY_ESCRITURA:"
    echo "    cp .env.example .env"
    exit 1
fi

HOST=127.0.0.1                                         # 127.0.0.1 = solo esta computadora
if [ "$1" = "red" ]; then
    HOST=0.0.0.0                                       # 0.0.0.0 = acepta conexiones de la red
    echo "Otras computadoras se conectan a: http://$(ipconfig getifaddr en0 2>/dev/null || hostname -I | cut -d' ' -f1):8001"
fi

echo "Documentación: http://localhost:8001/docs   (Ctrl+C para detener)"
exec "$PYTHON" -m uvicorn main:app --host "$HOST" --port 8001
