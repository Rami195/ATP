from __future__ import annotations

import logging
import pandas as pd
from airflow.sdk import task
from atp import calidad, config, features

log = logging.getLogger(__name__)


@task
def normalize_player_matches(ruta_partidos: str, auxiliares: dict[str, str]) -> str:
    """Convierte 1 fila=partido en 1 fila=jugador-partido y agrega biografias."""
    partidos = pd.read_csv(
        ruta_partidos,
        dtype={"winner_id": "string", "loser_id": "string"},
        low_memory=False,
    )
    bios = features.preparar_biografias(auxiliares.get("bios"))
    largo = features.normalizar_partidos_jugador(partidos, bios)

    config.DIR_ANALITICO.mkdir(parents=True, exist_ok=True)
    destino = config.DIR_ANALITICO / "player_match_long.csv"
    largo.to_csv(destino, index=False)
    calidad.validar_player_match_long(destino)

    log.info("Player-match: %s filas x %s columnas -> %s", len(largo), len(largo.columns), destino)
    return str(destino)
