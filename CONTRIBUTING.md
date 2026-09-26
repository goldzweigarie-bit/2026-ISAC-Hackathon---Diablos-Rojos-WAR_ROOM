# Guía de trabajo en equipo

## Flujo con Git (GitFlow simplificado)

- `main` → siempre estable. Solo se actualiza con Pull Requests aprobadas.
- `develop` → rama de integración.
- Ramas por tarea: `feat/04-altitude-effect`, `fix/normalizacion-stuff`, `docs/entregable-5`, etc.

```bash
# 1. Clonar el repo
git clone https://github.com/<tu-usuario>/stuff-plus-diablos.git
cd stuff-plus-diablos

# 2. Crear tu rama de trabajo
git checkout -b feat/mi-tarea develop

# 3. Trabajar, commitear y subir
git add .
git commit -m "feat: agrega features de arsenal (velo_diff_vs_fb, tunnel)"
git push origin feat/mi-tarea

# 4. Abrir Pull Request hacia develop y pedir revisión
```

## Reglas del equipo

1. **Nunca** subas datos a `data/raw/` ni `data/processed/` al repo (están en `.gitignore`).
2. Un notebook por persona a la vez; si dos editan el mismo notebook, resolver conflictos con `nbdime` o dividir en celdas.
3. Todo código en `src/` debe poder importarse: `from src.features.arsenal import velo_diff_vs_fb`.
4. Los modelos entrenados van a `models/` con nombre `stuffplus_<fecha>_<version>.pkl`.
5. Cada entregable tiene su carpeta en `reports/` — trabaja ahí y marca ✅ en la tabla del README cuando esté listo.
6. Antes de la entrega (2026-10-15): `main` congelado, todo en PDF.

## Revisión de código

- Mínimo 1 aprobación de otro compañero para mergear a `develop`.
- Los notebooks de resultados (entregables) se revisan en conjunto (reunión de 30 min).

## Organización sugerida de responsables

| Persona | Encargado principal de |
|---|---|
| Integrante 1 | Modelado (`src/models`, notebook 03) y validación (05) |
| Integrante 2 | Features + efecto altitud (`src/features`, notebooks 02 y 04) |
| Integrante 3 | Dashboard (`dashboard/app.py`) y visualizaciones |
| Integrante 4 | Entregables escritos (`reports/`, `docs/documento-tecnico/`) |
