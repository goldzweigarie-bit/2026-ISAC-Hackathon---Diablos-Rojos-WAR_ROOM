"""Corre un notebook completo sin abrir Jupyter (lo usa apis/correr_modelos.sh).

    python correr_notebook.py <notebook.ipynb> <copia_ejecutada.ipynb> <kernel>

El notebook del repo NO se modifica: la copia con salidas se guarda donde digas (apis/logs/, que git ignora),
porque las salidas muestran tablas sacadas de los datos de la competencia y el repo es público.
"""
import os
import sys
import time
import warnings

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

warnings.filterwarnings("ignore")          # avisos de formato de nbformat, no afectan
origen, destino, kernel = sys.argv[1], sys.argv[2], sys.argv[3]
nb = nbformat.read(origen, as_version=4)
codigo = [i for i, c in enumerate(nb.cells) if c.cell_type == "code"]
t0 = time.time()


def titulo(i):
    """El título de la sección (la celda de texto más cercana hacia arriba), para saber en qué paso va."""
    for c in reversed(nb.cells[:i]):
        if c.cell_type == "markdown" and c.source.strip():
            return c.source.strip().splitlines()[0].lstrip("# ")[:70]
    return ""


def al_empezar(cell, cell_index):
    if cell.cell_type != "code":
        return
    n = codigo.index(cell_index) + 1
    print(f"  celda {n}/{len(codigo)} · {time.time() - t0:5.0f} s · {titulo(cell_index)}", flush=True)


cliente = NotebookClient(nb, timeout=None, kernel_name=kernel,
                         resources={"metadata": {"path": os.path.dirname(os.path.abspath(origen))}})
cliente.on_cell_start = al_empezar
try:
    cliente.execute()
    print(f"✓ terminado en {(time.time() - t0) / 60:.1f} min", flush=True)
except CellExecutionError as e:
    print(f"\n✗ Falló una celda:\n{str(e)[-3000:]}", flush=True)
    sys.exit(1)
finally:
    nbformat.write(nb, destino)
