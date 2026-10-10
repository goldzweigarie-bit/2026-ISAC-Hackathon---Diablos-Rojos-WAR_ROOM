"""Stuff+: combinacion de targets multi-objetivo y normalizacion a escala 100."""
import polars as pl

TARGETS = [
    "p_whiff", "p_chase", "p_called_strike", "p_weak_contact",
    "p_groundball", "p_barrel", "xrun_value",
]
TARGET_WEIGHTS = {
    "p_whiff": 0.30, "p_chase": 0.10, "p_called_strike": 0.10,
    "p_weak_contact": 0.15, "p_groundball": 0.15, "p_barrel": -0.20,
}


def combine_targets(pred: pl.DataFrame) -> pl.Series:
    """Combina las probabilidades predichas en un score continuo."""
    # Usar get_column() en lugar de pred[t]
    score = pl.Series([0.0] * pred.height)
    for t, w in TARGET_WEIGHTS.items():
        score = score + pred.get_column(t) * w
    score = score + pred.get_column("xrun_value") * TARGET_WEIGHTS.get("xrun_value", -1.0)
    return score


def to_stuff_plus(score: pl.Series) -> pl.Series:
    """Normaliza a la escala Stuff+ (100 = promedio LMB, 10 = 1 desv. est.)."""
    return 100.0 + 10.0 * (score - score.mean()) / score.std(ddof=0)