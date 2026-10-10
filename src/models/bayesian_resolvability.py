"""
bayesian_resolvability.py
=========================
Modelo de "Resolvabilidad Bayesiana" para Stuff+ del Hackathon ISAC Diablos Rojos 2026.

Fundamento teórico (paper "Bayesball", bioRxiv 2022)
----------------------------------------------------
El bateador se modela como un inferente Bayesiano que combina:
  - PRIOR:   la expectativa del movimiento de cada tipo de pitch (aprendida del arsenal).
  - LIKELIHOOD: la observación en vuelo del pitch real, contaminada por ruido visual.

Posterior  Likelihood × Prior   (Bayes)

Hipótesis central del proyecto (Estadio Alfredo Harp Helú, 2,240 msnm):
La menor densidad del aire a "Extreme Altitude" reduce el efecto Magnus, por lo que el
pitch se mueve menos y su trayectoria es visualmente más predecible. Modelamos esto como
una LIKELIHOOD con MENOR VARIANZA (el bateador "ve mejor" lo que está por llegar):
  sigma_likelihood(Extreme) = sigma_base * ALTITUDE_VARIANCE_FACTOR (0.75)

Con una likelihood más precisa, el posterior colapsa más rápido sobre el valor real,
el bateador depende menos del prior y el pitch es más "RESOLVIBLE" → menor P(whiff)
más allá de lo que un modelo físico lineal predice (penalización perceptual).

Pipeline:
  1. calculate_prior_movement(df)            -> priors de movimiento por pitch type.
  2. calculate_bayesian_resolvability(df)    -> discrepancia, likelihood variance,
                                                resolvability_score (ganancia de precisión
                                                del posterior normalizada).
  3. train_bayesian_stuff_model(df)          -> Logistic Regression interpretable sobre
                                                features físicas + resolvability +
                                                interacciones con altitude; devuelve modelo
                                                y reporte de importancia.

Autor: Equipo Stuff+ Bayesiano — Hackathon ISAC Diablos Rojos 2026.
"""

from __future__ import annotations

import warnings
from typing import Dict, List, Tuple

import polars as pl
import numpy as np
import pandas as pd  # solo para sklearn (ColumnTransformer, LogisticRegression)
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, log_loss,
                             roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# --------------------------------------------------------------------------- #
# Hiperparámetros del modelo perceptual (documentados y tunables)
# --------------------------------------------------------------------------- #
ALTITUDE_VARIANCE_FACTOR: float = 0.75  # σ_likelihood(Extreme) = 0.75 × σ_base
MOVEMENT_COLS: Tuple[str, str] = ("InducedVertBreak", "HorzBreak")
TARGET_COL: str = "is_swinging_strike"
EXTREME_ALT: str = "Extreme Altitude"


# --------------------------------------------------------------------------- #
# Utilidades internas
# --------------------------------------------------------------------------- #
def _validate_columns(df: pl.DataFrame, required: set, fn: str) -> None:
    """Verifica que el DataFrame tenga las columnas necesarias."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"[{fn}] Faltan columnas requeridas: {sorted(missing)}")


# --------------------------------------------------------------------------- #
# Paso 1 — PRIOR del bateador
# --------------------------------------------------------------------------- #
def calculate_prior_movement(df: pl.DataFrame, group_cols: List[str] = None) -> pl.DataFrame:
    """Calcula el prior del movimiento (IVB/HB) por tipo de pitcheo."""
    if group_cols is None:
        group_cols = ["AutoPitchType"]
    
    required = set(group_cols) | set(MOVEMENT_COLS)
    _validate_columns(df, required, fn="calculate_prior_movement")
    
    grp = (
        df.drop_nulls(subset=list(MOVEMENT_COLS))
        .group_by(list(group_cols))
        .agg([
            *[pl.col(c).mean().alias(f"{c}_mean") for c in MOVEMENT_COLS],
            *[pl.col(c).std().alias(f"{c}_std") for c in MOVEMENT_COLS],
            *[pl.col(c).count().alias(f"{c}_count") for c in MOVEMENT_COLS],
        ])
    )
    
    return grp


# --------------------------------------------------------------------------- #
# Paso 2 — LIKELIHOOD, discrepancia y RESOLVABILIDAD
# --------------------------------------------------------------------------- #
def calculate_bayesian_resolvability(df: pl.DataFrame,
                                     prior_df: pl.DataFrame | None = None
                                     ) -> pl.DataFrame:
    """
    Actualización Bayesiana per-pitch: combina el prior del arsenal con la observación
    del pitch real bajo un likelihood cuya varianza depende de la categoría de altitud.

    Matemática (por componente de movimiento y ∈ {IVB, HB}, independencia aprox.):
        Prior:       y ~ N(μ_p, σ_p²)            (media y std del grupo, paso 1)
        Likelihood:  y_obs ~ N(y_real, σ_l²)      σ_l = σ_p × f(altitude)
                     f(Extreme Altitude) = ALTITUDE_VARIANCE_FACTOR = 0.75
                     f(otras)            = 1.0
        Posterior:   N(μ_post, σ_post²), con
                     precisión_post = precisión_prior + precisión_likelihood
                     σ_post² = (1/σ_p² + 1/σ_l²)⁻¹

    Resolvability score (entregable central):
        resolvability_score = (σ_p² - σ_post²) / σ_p²   ∈ [0, 1)
        = fracción de la incertidumbre del PRIOR que la observación (likelihood)
          logra "colapsar" en el POSTERIOR. Con σ_l más chica (altitud extrema) el
          denominador de la precisión crece, σ_post² se encoge y el score sube:
          el bateador resuelve mejor el pitch -> se espera mayor P(contacto) y
          menor P(whiff) a igualdad de física pura.

    Discrepancia (sorpresa perceptual, feature auxiliar):
        z_ivb = (IVB_obs - μ_p_IVB) / σ_p_IVB, z_hb análogo; surprise = ||z||₂.
        Un pitch que se aleja del prior sorprende al bateador y rompe el modelo
        mental (efecto "pitch tunneling" en términos de Bayesball).

    Parámetros
    ----------
    df : DataFrame crudo (columnas exactas del esquema ISAC).
    prior_df : salida de calculate_prior_movement(df); si None, se calcula interno.

    Retorna
    -------
    df con columnas nuevas:
        ivb_prior, hb_prior, ivb_prior_var, hb_prior_var,
        likelihood_var_factor, ivb_likelihood_var, hb_likelihood_var,
        z_ivb, z_hb, surprise_score,
        ivb_posterior_var, hb_posterior_var,
        resolvability_score, is_extreme_altitude.
    """
    _validate_columns(df, {"AutoPitchType", "altitude_category"} | set(MOVEMENT_COLS),
                      fn="calculate_bayesian_resolvability")
    
    #  Polars: clone() en lugar de copy()
    out = df.clone()

    if prior_df is None:
        prior_df = calculate_prior_movement(out)

    # --- Merge del prior al pitch individual -----------------------------
    #  Polars: join() en lugar de merge(), y seleccionar columnas antes
    prior_select = prior_df.select([
        "AutoPitchType",
        pl.col("InducedVertBreak_mean").alias("ivb_prior"),
        pl.col("InducedVertBreak_std").alias("ivb_std"),
        pl.col("HorzBreak_mean").alias("hb_prior"),
        pl.col("HorzBreak_std").alias("hb_std"),
    ])
    
    out = out.join(prior_select, on="AutoPitchType", how="left")

    # Varianzas del prior (σ_p²)
    out = out.with_columns([
        (pl.col("ivb_std") ** 2).alias("ivb_prior_var"),
        (pl.col("hb_std") ** 2).alias("hb_prior_var"),
    ])

    # --- Factor de varianza del likelihood según altitud -----------------
    # Bayesball: la percepción no es un sensor perfecto; su ruido depende del
    # contexto físico-visual. A 2,240 msnm el aire es menos denso, el Magnus
    # se atenúa, la trayectoria es más simple y la señal visual menos ruidosa.
    out = out.with_columns([
        pl.when(pl.col("altitude_category") == EXTREME_ALT)
        .then(pl.lit(ALTITUDE_VARIANCE_FACTOR))
        .otherwise(pl.lit(1.0))
        .alias("likelihood_var_factor"),
        
        (pl.col("altitude_category") == EXTREME_ALT).cast(pl.Int32).alias("is_extreme_altitude"),
    ])
    
    out = out.with_columns([
        (pl.col("ivb_prior_var") * pl.col("likelihood_var_factor")).alias("ivb_likelihood_var"),
        (pl.col("hb_prior_var") * pl.col("likelihood_var_factor")).alias("hb_likelihood_var"),
    ])

    # --- Discrepancia observación vs prior (sorpresa estandarizada) ------
    out = out.with_columns([
        ((pl.col("InducedVertBreak") - pl.col("ivb_prior")) / pl.col("ivb_std")).alias("z_ivb"),
        ((pl.col("HorzBreak") - pl.col("hb_prior")) / pl.col("hb_std")).alias("z_hb"),
    ])
    
    out = out.with_columns([
        ((pl.col("z_ivb") ** 2 + pl.col("z_hb") ** 2).sqrt()).alias("surprise_score"),
    ])

    # --- Actualización Bayesiana: varianza posterior ---------------------
    # σ_post² = (1/σ_p² + 1/σ_l²)⁻¹   (combinación de precisiones gaussianas)
    out = out.with_columns([
        (1.0 / (1.0 / pl.col("ivb_prior_var") + 1.0 / pl.col("ivb_likelihood_var"))).alias("ivb_posterior_var"),
        (1.0 / (1.0 / pl.col("hb_prior_var") + 1.0 / pl.col("hb_likelihood_var"))).alias("hb_posterior_var"),
    ])

    # --- Resolvability score: fracción de incertidumbre del prior resuelta
    # R = 1 - σ_post²/σ_p². Si σ_l → σ_p (sin ventana perceptual), R ≈ 0.5.
    # Si σ_l < σ_p (Extreme Altitude), R > 0.5: el posterior colapsa más.
    out = out.with_columns([
        (0.5 * (1.0 - pl.col("ivb_posterior_var") / pl.col("ivb_prior_var"))
         + 0.5 * (1.0 - pl.col("hb_posterior_var") / pl.col("hb_prior_var"))
        ).alias("resolvability_score"),
    ])

    # Limpieza de intermedios opcionales se mantiene: son auditables.
    return out


# --------------------------------------------------------------------------- #
# Paso 3 — Modelo interpretable de Stuff
# --------------------------------------------------------------------------- #
def train_bayesian_stuff_model(df: pl.DataFrame,
                               test_size: float = 0.2,
                               random_state: int = 42,
                               C: float = 0.5) -> Dict:
    """
    Entrena una Regresión Logística (interpretable) para P(whiff) = P(is_swinging_strike=1).

    Features:
      - Físicas: IVB, HB, RelSpeed, SpinRate.
      - Perceptuales bayesianas: resolvability_score, surprise_score, z_ivb, z_hb,
        is_extreme_altitude.
      - Interacciones clave (hipótesis del proyecto): el efecto de la resolvabilidad
        sobre el whiff se MODULA por la altitud -> resolvability × is_extreme_altitude
        y resolvability × altitude_category (one-hot). Si la hipótesis es cierta, el
        coeficiente de la interacción debe ser NEGATIVO (más resolvibilidad en altura
        => menor P(whiff) extra, penalización perceptual).
      - Contexto: AutoPitchType, altitude_category, PitcherThrows, BatterSide, Balls, Strikes.

    Nulos: imputación mediana (numéricas, incl. count) y moda (categóricas).

    Retorna
    -------
    dict con:
      "pipeline"       : Pipeline sklearn entrenado (listo para .predict_proba).
      "X_train/X_test" : splits reproducibles.
      "y_train/y_test" : splits reproducibles.
      "metrics"        : ROC AUC (test y OOF CV), log-loss, accuracy, classification report.
      "importance"     : DataFrame |coeficiente| estandarizado, ordenado (top 25).
      "oof_auc"        : AUC out-of-fold con CV estratificada 5-fold.
    """
    needed = {"AutoPitchType", "altitude_category", "PitcherThrows", "BatterSide",
              "RelSpeed", "SpinRate", "Balls", "Strikes", TARGET_COL,
              "resolvability_score", "surprise_score", "z_ivb", "z_hb",
              "is_extreme_altitude"} | set(MOVEMENT_COLS)
    _validate_columns(df, needed, fn="train_bayesian_stuff_model")

    # ---- Interacciones (las creamos ANTES del split)
    #  Polars: with_columns() en lugar de asignación directa
    d = df.clone()
    d = d.with_columns([
        (pl.col("resolvability_score") * pl.col("is_extreme_altitude")).alias("resolv_x_extreme"),
        (pl.col("resolvability_score") * (pl.col("altitude_category") == "No Altitude").cast(pl.Int32)).alias("resolv_x_noalt"),
        (pl.col("resolvability_score") * (pl.col("altitude_category") == "Medium Altitude").cast(pl.Int32)).alias("resolv_x_medium"),
    ])

    num_feats = ["InducedVertBreak", "HorzBreak", "RelSpeed", "SpinRate",
                 "Balls", "Strikes",
                 "resolvability_score", "surprise_score", "z_ivb", "z_hb",
                 "is_extreme_altitude",
                 "resolv_x_extreme", "resolv_x_noalt", "resolv_x_medium"]
    cat_feats = ["AutoPitchType", "altitude_category", "PitcherThrows", "BatterSide"]

    #  Polars: drop_nulls() en lugar de dropna()
    data = d.drop_nulls(subset=[TARGET_COL])
    
    #  Convertir a Pandas para sklearn (inevitable)
    data_pd = data.select(num_feats + cat_feats + [TARGET_COL]).to_pandas()
    X = data_pd[num_feats + cat_feats]
    y = data_pd[TARGET_COL].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y)

    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                          ("sc", StandardScaler())]), num_feats),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat_feats),
    ])

    clf = LogisticRegression(C=C, max_iter=2000, class_weight="balanced",
                             solver="lbfgs", random_state=random_state)
    pipe = Pipeline([("pre", pre), ("clf", clf)])
    pipe.fit(X_train, y_train)

    # ---- Métricas ------------------------------------------------------
    proba_test = pipe.predict_proba(X_test)[:, 1]
    pred_test = (proba_test >= 0.5).astype(int)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        oof = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]

    metrics = {
        "roc_auc_test": roc_auc_score(y_test, proba_test),
        "roc_auc_oof": roc_auc_score(y, oof),
        "log_loss_test": log_loss(y_test, proba_test),
        "accuracy_test": accuracy_score(y_test, pred_test),
        "classification_report": classification_report(y_test, pred_test,
                                                       output_dict=True),
    }

    # ---- Importancia: |coef| sobre features estandarizadas -------------
    feat_names = pipe.named_steps["pre"].get_feature_names_out()
    coefs = pipe.named_steps["clf"].coef_[0]
    
    # Polars DataFrame para la importancia
    importance = pl.DataFrame({
        "feature": feat_names,
        "coef": coefs,
    }).with_columns([
        pl.col("coef").abs().alias("abs_coef"),
        pl.col("coef").map_elements(lambda x: np.exp(x), return_dtype=pl.Float64).alias("odds_ratio"),
    ]).sort("abs_coef", descending=True).head(25)

    return {
        "pipeline": pipe,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "metrics": metrics,
        "importance": importance,
        "oof_auc": metrics["roc_auc_oof"],
    }