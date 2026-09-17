from __future__ import annotations

import logging
import pandas as pd
from airflow.sdk import task
from atp import calidad, config, features

log = logging.getLogger(__name__)


@task
def build_player_profiles(ruta_player_match: str, **context) -> dict[str, str]:
    """Genera los datasets tenista-nivel para descubrir e interpretar estilos."""
    min_partidos = int(context["params"]["min_partidos_estilo"])
    largo = pd.read_csv(
        ruta_player_match,
        dtype={"player_id": "string", "opponent_id": "string"},
        parse_dates=["fecha"],
        low_memory=False,
    )

    perfiles, style = features.construir_perfiles_jugador(largo, min_partidos=min_partidos)
    superficie = features.construir_perfiles_superficie(
        largo,
        min_partidos=config.MIN_PARTIDOS_SUPERFICIE,
    )

    config.DIR_ANALITICO.mkdir(parents=True, exist_ok=True)
    rutas = {
        "profiles_all": config.DIR_ANALITICO / "player_profiles_all.csv",
        "style_dataset": config.DIR_ANALITICO / "player_style_dataset.csv",
        "surface_profiles": config.DIR_ANALITICO / "player_surface_profiles.csv",
    }
    perfiles.to_csv(rutas["profiles_all"], index=False)
    style.to_csv(rutas["style_dataset"], index=False)
    superficie.to_csv(rutas["surface_profiles"], index=False)

    calidad.validar_style_dataset(rutas["style_dataset"], min_partidos=min_partidos)
    log.info("Dataset de estilos: %s jugadores elegibles", len(style))
    return {k: str(v) for k, v in rutas.items()}
