"""Stuff model interface.

The app never assumes how Stuff is modeled. It builds a feature table (one row per pitcher x pitch type,
evaluated at a given air density) and asks the model for a raw score where higher = better for the pitcher.
Stuff+ is then 100 + 10 * z of that score, computed within each park and season.

To plug in the trained model, save any object with a `predict(DataFrame) -> array` method (sklearn Pipeline,
or the four sub-models wrapped in one class) to data/processed/stuff_model.joblib. It receives the columns in
FEATURE_COLUMNS. Until that file exists the transparent placeholder below is used, and the Methodology page says so.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

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

    def predict(self, X: pd.DataFrame) -> np.ndarray:
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


def load_model(processed_dir: Path):
    path = processed_dir / "stuff_model.joblib"
    if path.exists():
        import joblib

        model = joblib.load(path)
        if not hasattr(model, "name"):
            try:
                model.name = "trained"
            except AttributeError:
                pass
        return model
    return PlaceholderStuffModel()


def stuff_plus(raw: np.ndarray, weights: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """100 + 10 z within each group (park x season), weighted by pitch counts."""
    raw = np.asarray(raw, dtype=float)
    out = np.full(len(raw), np.nan)
    for g in pd.unique(groups):
        m = groups == g
        w = weights[m]
        mu = np.average(raw[m], weights=w)
        sd = np.sqrt(np.average((raw[m] - mu) ** 2, weights=w))
        out[m] = 100 + 10 * (raw[m] - mu) / (sd if sd > 0 else 1.0)
    return out
