"""Features relacionales de arsenal.

Cada pitch se evalua en relacion con el repertorio completo del pitcher
(FanGraphs: los secundarios se juzgan con respecto a la recta primaria).
"""
import pandas as pd


def velo_diff_vs_fb(df: pd.DataFrame) -> pd.Series:
    """Diferencial de velocidad vs. fastball primaria del pitcher."""
    fb = (df[df["pitch_type"].isin(["Fastball", "Sinker"])]
          .groupby(["pitcher_id", "game_year"])["velocity"].transform("max"))
    return df["velocity"] - fb


def ivb_diff_vs_fb(df: pd.DataFrame) -> pd.Series:
    """Diferencial de IVB vs. fastball primaria."""
    fb = (df[df["pitch_type"].isin(["Fastball", "Sinker"])]
          .groupby(["pitcher_id", "game_year"])["ivb"].transform("mean"))
    return df["ivb"] - fb


def hb_diff_vs_fb(df: pd.DataFrame) -> pd.Series:
    """Diferencial de HB vs. fastball primaria."""
    fb = (df[df["pitch_type"].isin(["Fastball", "Sinker"])]
          .groupby(["pitcher_id", "game_year"])["hb"].transform("mean"))
    return df["hb"] - fb


def pitch_usage_pct(df: pd.DataFrame) -> pd.Series:
    """Frecuencia de uso del pitch_type dentro del repertorio del pitcher."""
    return df.groupby(["pitcher_id", "game_year", "pitch_type"])["pitch_type"].transform("count") / \
           df.groupby(["pitcher_id", "game_year"])["pitch_type"].transform("count")
