"""Validacion fuera de muestra: pitcher, season y park holdout.

Criterio de evaluacion: robustez fuera de muestra pesa 25% del hackathon.
Baselines a superar: modelo nulo (xRunValue promedio por count).
"""
import pandas as pd
from sklearn.metrics import mean_squared_error, log_loss, brier_score_loss


def pitcher_holdout(df, model, features, target, group_col="pitcher_id"):
    """Entrena sin ciertos pitchers y evalua en ellos (RMSE + calibracion)."""
    results = []
    for pid in df[group_col].unique():
        train, test = df[df[group_col] != pid], df[df[group_col] == pid]
        if len(test) < 50:
            continue
        model.fit(train[features], train[target])
        pred = model.predict(test[features])
        results.append({"pitcher_id": pid, "rmse": mean_squared_error(test[target], pred) ** 0.5,
                        "n": len(test)})
    return pd.DataFrame(results)


def park_holdout(df, model, features, target, park_col="stadium", test_park="Harp Helu"):
    """Entrena sin Harp Helu y evalua el delta de Stuff+ por pitch shape."""
    train, test = df[df[park_col] != test_park], df[df[park_col] == test_park]
    model.fit(train[features], train[target])
    pred = model.predict(test[features])
    return {"rmse_harp": mean_squared_error(test[target], pred) ** 0.5, "n": len(test)}
