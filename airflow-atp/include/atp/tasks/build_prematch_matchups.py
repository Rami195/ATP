from __future__ import annotations

import logging
import pandas as pd
from airflow.sdk import task
from atp import calidad, config, features

log = logging.getLogger(__name__)


@task
def build_prematch_matchups(ruta_player_match: str, **context) -> dict[str, str]:
    """Crea features historicas pre-partido y un dataset A/B sin leakage winner/loser."""
    min_historial = int(context["params"]["min_historial_prematch"])
    largo = pd.read_csv(
        ruta_player_match,
        dtype={"player_id": "string", "opponent_id": "string"},
        parse_dates=["fecha"],
        low_memory=False,
    )

    historial = features.construir_historial_prematch(largo)
    todos, modelo = features.construir_matchups_modelo(historial, min_historial=min_historial)

    config.DIR_ANALITICO.mkdir(parents=True, exist_ok=True)
    rutas = {
        "prematch_history": config.DIR_ANALITICO / "player_prematch_history.csv",
        "matchups_all": config.DIR_ANALITICO / "matchups_prematch_all.csv",
        "model_dataset": config.DIR_ANALITICO / "matchups_modelo.csv",
    }
    historial.to_csv(rutas["prematch_history"], index=False)
    todos.to_csv(rutas["matchups_all"], index=False)
    modelo.to_csv(rutas["model_dataset"], index=False)

    calidad.validar_matchups_modelo(rutas["model_dataset"], min_historial=min_historial)
    log.info("Matchups modelables: %s partidos", len(modelo))
    return {k: str(v) for k, v in rutas.items()}
