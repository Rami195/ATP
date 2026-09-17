from __future__ import annotations

import logging
from pathlib import Path
from airflow.sdk import task
from atp import config, consolidar

log = logging.getLogger(__name__)


@task
def consolidate(rutas_temporadas: list[str]) -> str:
    partidos = consolidar.consolidar([Path(r) for r in rutas_temporadas])
    config.DIR_PROCESADO.mkdir(parents=True, exist_ok=True)
    destino = config.DIR_PROCESADO / "partidos_consolidado.csv"
    partidos.to_csv(destino, index=False)
    log.info("Silver: %s filas x %s columnas -> %s", len(partidos), len(partidos.columns), destino)
    return str(destino)
