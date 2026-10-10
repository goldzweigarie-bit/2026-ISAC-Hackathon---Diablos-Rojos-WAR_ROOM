"""Stuff+ PROVISIONAL: solo se usa mientras el API 2 no tenga la tabla de Stuff+ del modelo.

No está entrenado: son pesos puestos a mano para que la web app tenga algo que mostrar antes de que el
modelo termine. En cuanto el modelo sube su tabla al API 2, el traductor deja de usar este archivo (y el
encabezado de la app deja de decir "Modelo provisional").
"""
from __future__ import annotations

import numpy as np
import polars as pl

FEATURE_COLUMNS = [
    "pitch_type", "throws", "rel_speed", "plate_speed", "spin_rate", "spin_axis", "extension", "rel_height",
    "rel_side", "ivb", "hb_arm", "vaa", "fb_rel_speed", "fb_ivb", "fb_hb_arm", "rho_ratio",
]

FASTBALLS = {"Four-Seam", "Sinker"}
BREAKING = {"Slider", "Curveball", "Cutter"}
OFFSPEED = {"Changeup", "Splitter"}


class PlaceholderStuffModel:
    """Hand-set, physically sensible weights so the app has something to show before training.

    It rewards velocity, carry on four-seamers, run/sink on sinkers, total break on breaking balls and
    velocity/movement separation on offspeed. It is NOT fitted to outcomes.
    """

    name = "placeholder"

    def predict(self, X: pl.DataFrame) -> np.ndarray:
        pt = X["pitch_type"].to_numpy()
        velo = X["plate_speed"].to_numpy()
        ivb = X["ivb"].to_numpy()
        hb = X["hb_arm"].to_numpy()
        ext = X["extension"].to_numpy()
        vaa = X["vaa"].to_numpy()
        spin = X["spin_rate"].to_numpy()
        fb_velo = X["fb_rel_speed"].to_numpy()
        fb_ivb = X["fb_ivb"].to_numpy()
        rel_velo = X["rel_speed"].to_numpy()

        score = np.zeros(len(X))
        four = pt == "Four-Seam"
        score[four] = (0.10 * (velo[four] - 85) + 0.07 * (ivb[four] - 15) + 0.05 * (ext[four] - 6)
                       + 0.06 * (vaa[four] + 5.5))
        sink = pt == "Sinker"
        score[sink] = (0.10 * (velo[sink] - 84) + 0.05 * (hb[sink] - 13) - 0.05 * (ivb[sink] - 8)
                       + 0.04 * (ext[sink] - 6))
        cut = pt == "Cutter"
        score[cut] = 0.08 * (velo[cut] - 82) + 0.05 * (-hb[cut] - 2) + 0.03 * (ivb[cut] - 8)
        slide = pt == "Slider"
        total = np.hypot(hb, ivb)
        score[slide] = 0.05 * (total[slide] - 7) + 0.04 * (velo[slide] - 76) + 0.02 * (spin[slide] - 2400) / 100
        curve = pt == "Curveball"
        score[curve] = (0.05 * (-ivb[curve] - 6) + 0.03 * (np.abs(hb[curve]) - 6) + 0.03 * (velo[curve] - 71)
                        + 0.02 * (spin[curve] - 2500) / 100)
        off = np.isin(pt, list(OFFSPEED))
        diff = fb_velo[off] - rel_velo[off]
        score[off] = (-0.012 * (diff - 9.0) ** 2 + 0.05 * (fb_ivb[off] - ivb[off] - 6) + 0.03 * (hb[off] - 12)
                      + 0.03 * (velo[off] - 76))
        return score


def stuff_plus(raw: np.ndarray, weights: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """100 + 10 z within each group (park x season), weighted by pitch counts."""
    raw = np.asarray(raw, dtype=float)
    out = np.full(len(raw), np.nan)
    for g in dict.fromkeys(groups):                       # cada grupo distinto, en orden de aparición
        m = groups == g
        w = weights[m]
        mu = np.average(raw[m], weights=w)
        sd = np.sqrt(np.average((raw[m] - mu) ** 2, weights=w))
        out[m] = 100 + 10 * (raw[m] - mu) / (sd if sd > 0 else 1.0)
    return out
