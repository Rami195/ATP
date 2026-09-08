"""Task que consolida los CSV de temporada en la capa Silver."""

from __future__ import annotations

import logging
from pathlib import Path

from airflow.sdk import task

from atp import config, consolidar

log = logging.getLogger(__name__)


@task
def consolidate(rutas_temporadas: list[str]) -> str:
    """Une, tipa y deduplica las temporadas descargadas."""
    partidos = consolidar.consolidar(
        [Path(ruta) for ruta in rutas_temporadas]
    )

    config.DIR_PROCESADO.mkdir(
        parents=True,
        exist_ok=True,
    )

    destino = (
        config.DIR_PROCESADO
        / "partidos_consolidado.csv"
    )

    partidos.to_csv(destino, index=False)

    log.info(
        "Consolidado: %s filas x %s columnas -> %s",
        len(partidos),
        len(partidos.columns),
        destino,
    )

    return str(destino)
