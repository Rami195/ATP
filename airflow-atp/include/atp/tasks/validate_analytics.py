from __future__ import annotations

import logging
from pathlib import Path
from airflow.sdk import task

log = logging.getLogger(__name__)


@task
def validate_analytics(perfiles: dict[str, str], matchups: dict[str, str]) -> dict[str, str]:
    """Chequeo final de existencia de los entregables Gold."""
    salidas = {**perfiles, **matchups}
    faltantes = [nombre for nombre, ruta in salidas.items() if not Path(ruta).exists()]
    if faltantes:
        raise FileNotFoundError(f"Faltan salidas Gold: {faltantes}")
    log.info("Gold OK: %s archivos analiticos", len(salidas))
    return salidas
