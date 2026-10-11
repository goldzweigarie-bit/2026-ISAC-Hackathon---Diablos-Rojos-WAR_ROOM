"""
stuff_plus_pipeline.py
======================
Pipeline unificado para el Hackathon ISAC Diablos Rojos 2026.
Combina el modelo de Run Values/XGBoost (equipo) con la Resolvabilidad Bayesiana (tú).
Usa Polars para manipulación de datos y Seaborn para visualización.
"""

from __future__ import annotations
import warnings
from typing import Dict, List, Tuple

import numpy as np
import polars as pl
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, log_loss

sns.set_theme(style="whitegrid")
warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# CONSTANTES Y CONFIGURACIÓN
# --------------------------------------------------------------------------- #
VALOR_EVENTO = {
    'Walk': 0.31, 'HitByPitch': 0.33, 'Single': 0.46, 'Error': 0.46,
    'Double': 0.77, 'Triple': 1.05, 'HomeRun': 1.40,
    'Out': -0.27, 'Strikeout': -0.27, 'FieldersChoice': -0.27, 'Sacrifice': -0.27
}
TIPOS_MODELO = ['Four-Seam', 'Sinker', 'Cutter', 'Slider', 'Curveball', 'Changeup', 'Splitter']
ALTITUDE_VARIANCE_FACTOR = 0.75
TARGET_COL = "is_swinging_strike"

# --------------------------------------------------------------------------- #
# PASO 1: RUN VALUES
# --------------------------------------------------------------------------- #
def calcular_run_values(df: pl.DataFrame) -> pl.DataFrame:
    """Calcula el valor en carreras de cada pitcheo usando Polars."""
    #  Usar pl.col() en lugar de df['col']
    termina_pa = (
        pl.col('KorBB').is_in(['Strikeout', 'Walk']) | 
        pl.col('PitchCall').is_in(['InPlay', 'HitByPitch'])
    )
    
    empieza_pa = (
        (pl.col('game_anon_id') != pl.col('game_anon_id').shift()) |
        (pl.col('Inning') != pl.col('Inning').shift()) |
        (pl.col('Top/Bottom') != pl.col('Top/Bottom').shift()) |
        (pl.col('batter_anon_id') != pl.col('batter_anon_id').shift()) |
        termina_pa.shift(fill_value=False)
    )
    
    df = df.with_columns(pa_id=empieza_pa.cum_sum())
    
    #  Usar pl.when().then().otherwise() con pl.col()
    df = df.with_columns([
        pl.when(pl.col('KorBB') == 'Strikeout').then(pl.lit('Strikeout'))
        .when(pl.col('KorBB') == 'Walk').then(pl.lit('Walk'))
        .when(pl.col('PitchCall') == 'HitByPitch').then(pl.lit('HitByPitch'))
        .when(pl.col('PitchCall') == 'InPlay').then(pl.col('play_result'))
        .otherwise(None).alias('evento')
    ])
    
    df = df.with_columns([
        pl.when(termina_pa).then(pl.col('evento')).otherwise(None).alias('evento_final'),
        pl.col('evento').replace_strict(
            old=list(VALOR_EVENTO.keys()),
            new=list(VALOR_EVENTO.values()),
            default=None
        ).alias('rv_evento')
    ])
    
    # Simplificación: rv_pitcheo = rv_evento (fillna 0)
    df = df.with_columns([
        pl.col('rv_evento').fill_null(0).alias('rv_pitcheo')
    ])
    
    return df

# --------------------------------------------------------------------------- #
# PASO 2: FEATURES DE ARSENAL Y CONTEXTO
# --------------------------------------------------------------------------- #
def crear_features_arsenal(df: pl.DataFrame) -> pl.DataFrame:
    """Crea variables relativas a la recta primaria y de contexto."""
    #  Usar pl.col() en lugar de df['col']
    zurdo = pl.col('PitcherThrows') == 'Left'
    
    df = df.with_columns([
        pl.when(zurdo).then(-pl.col('HorzBreak')).otherwise(pl.col('HorzBreak')).alias('hb'),
        pl.when(zurdo).then(-pl.col('RelSide')).otherwise(pl.col('RelSide')).alias('rel_side'),
    ])
    
    # Eje de giro (seno y coseno)
    eje = pl.when(zurdo).then(360 - pl.col('SpinAxis')).otherwise(pl.col('SpinAxis'))
    df = df.with_columns([
        (eje * np.pi / 180).sin().alias('eje_sin'),
        (eje * np.pi / 180).cos().alias('eje_cos'),
    ])
    
    #  Usar pl.col().mean() en lugar de df['col'].mean()
    df = df.with_columns([
        (pl.col('RelSpeed') - pl.col('RelSpeed').mean()).alias('velo_diff_vs_fb'),
        (pl.col('InducedVertBreak') - pl.col('InducedVertBreak').mean()).alias('ivb_diff_vs_fb'),
        (pl.col('hb') - pl.col('hb').mean()).alias('hb_diff_vs_fb'),
    ])
    
    # Variables de contexto
    df = df.with_columns([
        pl.col('altitude_category').cast(pl.String).replace_strict(
            old=['No Altitude', 'Medium Altitude', 'Extreme Altitude'],
            new=[0, 1, 2],
            default=None
        ).cast(pl.Int32).alias('altitud_num'),
        (pl.col('PitcherThrows') == 'Right').cast(pl.Int32).alias('mano_derecha'),
        (pl.col('PitcherThrows') == pl.col('BatterSide')).cast(pl.Int32).alias('mismo_lado'),
    ])
    
    return df

# --------------------------------------------------------------------------- #
# PASO 3: RESOLVABILIDAD BAYESIANA
# --------------------------------------------------------------------------- #
def calcular_resolvabilidad_bayesiana(df: pl.DataFrame) -> pl.DataFrame:
    """Calcula el resolvability_score bayesiano."""
    #  Polars: agg con expresiones, no lista de strings
    priors = df.group_by('tipo').agg([
        pl.col('InducedVertBreak').mean().alias('ivb_mean'),
        pl.col('InducedVertBreak').std().alias('ivb_std'),
        pl.col('hb').mean().alias('hb_mean'),
        pl.col('hb').std().alias('hb_std'),
    ])
    
    df = df.join(priors, on='tipo', how='left')
    
    #  Usar pl.col() en las expresiones
    df = df.with_columns([
        ((pl.col('InducedVertBreak') - pl.col('ivb_mean')) / pl.col('ivb_std')).alias('z_ivb'),
        ((pl.col('hb') - pl.col('hb_mean')) / pl.col('hb_std')).alias('z_hb'),
    ])
    
    # Varianza del likelihood con factor de altitud
    df = df.with_columns([
        pl.when(pl.col('altitud_num') == 2)
        .then(pl.col('ivb_std')**2 * ALTITUDE_VARIANCE_FACTOR)
        .otherwise(pl.col('ivb_std')**2)
        .alias('likelihood_var_ivb'),
        
        pl.when(pl.col('altitud_num') == 2)
        .then(pl.col('hb_std')**2 * ALTITUDE_VARIANCE_FACTOR)
        .otherwise(pl.col('hb_std')**2)
        .alias('likelihood_var_hb'),
    ])
    
    # Varianza posterior
    df = df.with_columns([
        (1.0 / (1.0/pl.col('ivb_std')**2 + 1.0/pl.col('likelihood_var_ivb'))).alias('posterior_var_ivb'),
        (1.0 / (1.0/pl.col('hb_std')**2 + 1.0/pl.col('likelihood_var_hb'))).alias('posterior_var_hb'),
    ])
    
    # Resolvability score
    df = df.with_columns([
        (0.5 * (1.0 - pl.col('posterior_var_ivb') / pl.col('ivb_std')**2) + 
         0.5 * (1.0 - pl.col('posterior_var_hb') / pl.col('hb_std')**2)).alias('resolvability_score'),
    ])
    
    # Interacciones con altitud
    df = df.with_columns([
        (pl.col('resolvability_score') * (pl.col('altitud_num') == 2).cast(pl.Float64)).alias('resolv_x_extreme'),
    ])
    
    return df

# --------------------------------------------------------------------------- #
# PASO 4: MODELO XGBOOST CON PITCHER HOLDOUT
# --------------------------------------------------------------------------- #
def entrenar_modelo_stuff(df: pl.DataFrame, feature_cols: List[str]) -> Dict:
    """Entrena XGBoost con validación cruzada por pitcher (GroupKFold)."""
    #  Usar get_column() en lugar de df['col']
    X = df.select(feature_cols).to_numpy()
    y = df.get_column('is_swinging_strike').to_numpy()
    groups = df.get_column('pitcher_anon_id').to_numpy()
    
    gkf = GroupKFold(n_splits=5)
    
    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=6, learning_rate=0.1,
        tree_method='hist', enable_categorical=True, random_state=42
    )
    
    oof_preds = np.zeros(len(y))
    for train_idx, val_idx in gkf.split(X, y, groups):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]
        
        model.fit(X_train, y_train)
        oof_preds[val_idx] = model.predict_proba(X_val)[:, 1]
    
    auc_score = roc_auc_score(y, oof_preds)
    
    return {
        "model": model,
        "oof_preds": oof_preds,
        "auc": auc_score,
        "feature_importance": dict(zip(feature_cols, model.feature_importances_))
    }

# --------------------------------------------------------------------------- #
# PASO 5: VISUALIZACIÓN CON SEABORN
# --------------------------------------------------------------------------- #
def plot_stuff_por_altitud(df: pl.DataFrame):
    """Grafica el Stuff+ promedio por tipo de pitch y altitud."""
    # to_pandas() para seaborn
    plot_df = df.select(['tipo', 'altitude_category', 'stuff_plus']).to_pandas()
    
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=plot_df, x='tipo', y='stuff_plus', hue='altitude_category', palette='viridis')
    plt.title('Stuff+ por Tipo de Pitch y Altitud')
    plt.xlabel('Tipo de Pitch')
    plt.ylabel('Stuff+')
    plt.legend(title='Altitud')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# --------------------------------------------------------------------------- #
# EJEMPLO DE USO (MAIN)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print("Cargando datos con Polars...")
    df = pl.read_parquet("/Users/ariegoldzweig/Desktop/stuff-plus-diablos/data/raw/diablos_data.parquet")
    
    print("Calculando Run Values...")
    df = calcular_run_values(df)
    
    print("Creando Features de Arsenal...")
    df = crear_features_arsenal(df)
    
    print("Calculando Resolvabilidad Bayesiana...")
    df = calcular_resolvabilidad_bayesiana(df)
    
    print("Entrenando Modelo XGBoost...")
    feature_cols = ['InducedVertBreak', 'hb', 'RelSpeed', 'SpinRate', 'resolvability_score', 'resolv_x_extreme']
    resultados = entrenar_modelo_stuff(df, feature_cols)
    print(f"AUC del modelo: {resultados['auc']:.3f}")
    
    print("Graficando resultados...")
    plot_stuff_por_altitud(df)