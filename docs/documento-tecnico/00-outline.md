# Documento Técnico — Esquema (Entregable 5, 6–10 páginas)

> Convertir a PDF al final. Cada sección indica su extensión sugerida.

## 1. Resumen ejecutivo (0.5 pág.)
Qué hicimos, en una frase: "Construimos el primer modelo Stuff+ calibrado para las
condiciones físicas del Harp Helú (2,240 msnm) con tres temporadas de datos pitch-by-pitch de la LMB."

## 2. Marco teórico (1.5 págs.)
- Sabermetría moderna: de ERA a evaluación pitch-by-pitch (Tango et al., 2007; FanGraphs Stuff+/Location+/Pitching+)
- Física del béisbol: densidad del aire, arrastre, efecto Magnus, por qué el break se reduce ~20% a altitud (Alan Nathan; Coors Field como referencia a 1,609 m)
- El entorno LMB: Harp Helú a 2,240 msnm vs. estadios a nivel del mar; hipótesis H1–H4

## 3. Datos (1 pág.)
- Tres temporadas de pitch-by-pitch de LMB (ISAC)
- Limpieza: pitches válidos, tracking faltante, definición de targets (whiff, chase, called strike, weak contact, GB%, barrel%, xRunValue)

## 4. Modelado (2 págs.)
- **Arquitectura:** XGBoost/LightGBM multi-objetivo (justificar vs. GAM / Bayesiano jerárquico)
- **Features:** físicas (velocidad, IVB, HB, spin, axis, release, extensión) + arsenal (diferenciales vs. FB, túnel, uso, secuencia) + contexto (estadio, altitud, count, lado)
- **Función de pérdida:** por target (log-loss para probabilidades, MSE para xRunValue) + combinación ponderada
- **Definición formal de la escala:** `Stuff+ = 100 + 10·z(score)` y proceso de normalización por temporada y estadio

## 5. Validación fuera de muestra (1.5 págs.)
- Pitcher holdout, season holdout, park holdout — métricas: RMSE, log-loss, calibración
- Baseline: modelo nulo (xRunValue promedio por count) — debemos superarlo (25% de la evaluación)

## 6. Hallazgos: efecto altitud en CDMX (1.5 págs.)
- Delta Stuff+ por pitch shape: Harp Helú vs. nivel del mar
- Perfiles que ganan/pierden Stuff+ relativo (respaldar H1–H4)

## 7. Alcance y fronteras del modelo (0.5 pág.)
- Qué NO hace: no captura framing del catcher, lesiones, día vs. noche, clima en vivo; causalidad limitada (cf. Causal Forest como capa opcional)

## 8. Referencias
Lista de la convocatoria + citas internas de este repo.
