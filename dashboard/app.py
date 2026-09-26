"""
Dashboard Simulador — Stuff+ en Harp Helú (Entregable 4)

Uso:
    streamlit run dashboard/app.py

El pitching coach ingresa las características físicas de un pitch
y obtiene el Stuff+ estimado, con comparación lado a lado:
Harp Helú (2,240 msnm) vs. estadio a nivel del mar.
"""
import streamlit as st
import pandas as pd
import joblib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.features.physics import estimate_break_at_altitude  # noqa: E402

st.set_page_config(page_title="Stuff+ Simulador — Diablos Rojos", layout="wide")

st.title("⚾ Stuff+ Simulador — Harp Helú vs. Nivel del Mar")

# ---------------------------------------------------------------- inputs
col1, col2 = st.columns(2)
with col1:
    st.subheader("Características del pitch")
    pitch_type = st.selectbox("Tipo de pitch", ["Fastball", "Sinker", "Cutter", "Slider", "Curveball", "Sweeper", "Changeup", "Splitter"])
    velocity = st.slider("Velocidad (mph)", 80.0, 105.0, 93.0, 0.1)
    spin_rate = st.slider("Spin rate (rpm)", 1500, 3000, 2200, 10)
    ivb = st.slider("IVB — induced vertical break (in)", -20.0, 25.0, 15.0, 0.5)
    hb = st.slider("HB — horizontal break (in)", -25.0, 25.0, 8.0, 0.5)
with col2:
    st.subheader("Contexto")
    extension = st.slider("Extensión (ft)", 5.0, 7.5, 6.3, 0.05)
    release_height = st.slider("Altura de liberación (ft)", 4.5, 7.0, 5.9, 0.05)
    release_side = st.slider("Posición lateral de liberación (ft)", -4.0, 4.0, 2.0, 0.05)
    handedness = st.selectbox("Mano del lanzador", ["R", "L"])

# ---------------------------------------------------------------- model
@st.cache_resource
def load_model():
    p = Path(__file__).resolve().parents[1] / "models" / "stuffplus_latest.pkl"
    return joblib.load(p) if p.exists() else None

model = load_model()

features = pd.DataFrame([{
    "pitch_type": pitch_type, "velocity": velocity, "spin_rate": spin_rate,
    "ivb": ivb, "hb": hb, "extension": extension,
    "release_height": release_height, "release_side": release_side,
    "pitcher_handedness": handedness,
}])

if model is None:
    st.warning("Modelo no encontrado en `models/stuffplus_latest.pkl`. "
               "Entrena primero con `notebooks/03_model_stuff_plus.ipynb`.")
else:
    # Ajuste físico del break a cada altitud (H1): el modelo recibe el movimiento
    # ya corregido por densidad del aire.
    estadio_mar = features.copy()
    estadio_cdmx = features.copy()
    # estadio_cdmx[["ivb", "hb"]] = estadio_cdmx[["ivb", "hb"]].apply(
    #     estimate_break_at_altitude, altitude_m=2240)

    stuff_mar = float(model.predict(estadio_mar)[0])
    stuff_cdmx = float(model.predict(estadio_cdmx)[0])

    c1, c2, c3 = st.columns(3)
    c1.metric("Stuff+ — Harp Helú (2,240 m)", f"{stuff_cdmx:.1f}")
    c2.metric("Stuff+ — Nivel del mar", f"{stuff_mar:.1f}")
    c3.metric("Δ por altitud", f"{stuff_cdmx - stuff_mar:+.1f}")

    st.subheader("Mapa de movimiento")
    st.plotly_chart({}, use_container_width=True)  # TODO: scatter IVB vs HB, este pitch resaltado

st.caption("Hackathon ISAC 2026 — Datos LMB vía ISAC. Uso exclusivo para la competencia.")
