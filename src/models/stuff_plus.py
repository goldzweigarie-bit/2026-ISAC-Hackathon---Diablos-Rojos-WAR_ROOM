"""Stuff+: combinacion de targets multi-objetivo y normalizacion a escala 100.

Escala (convocatoria):
    Stuff+ = 100 + 10 * z(score_pitch)
    100  promedio LMB ajustado por temporada y estadio
    110  +1 desviacion estandar
    90   -1 desviacion estandar
    120+ elite (~percentil 97)
"""
import numpy as np
import pandas as pd

TARGETS = [
    "p_whiff", "p_chase", "p_called_strike", "p_weak_contact",
    "p_groundball", "p_barrel", "xrun_value",
]
# Pesos de combinacion: a calibrar en notebooks/03 (validar con log-loss holdout)
TARGET_WEIGHTS = {
    "p_whiff": 0.30, "p_chase": 0.10, "p_called_strike": 0.10,
    "p_weak_contact": 0.15, "p_groundball": 0.15, "p_barrel": -0.20,
}


def combine_targets(pred: pd.DataFrame) -> pd.Series:
    """Combina las probabilidades predichas en un score continuo."""
    score = sum(pred[t] * w for t, w in TARGET_WEIGHTS.items())
    score += pred["xrun_value"] * TARGET_WEIGHTS.get("xrun_value", -1.0)
    return score


def to_stuff_plus(score: pd.Series) -> pd.Series:
    """Normaliza a la escala Stuff+ (100 = promedio LMB, 10 = 1 desv. est.)."""
    return 100.0 + 10.0 * (score - score.mean()) / score.std(ddof=0)
