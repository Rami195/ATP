"""Task que publica el dataset final de la corrida."""

from __future__ import annotations

import logging
import shutil

from airflow.sdk import task

from atp import config

log = logging.getLogger(__name__)


@task
def save(ruta_partidos: str, **context) -> str:
    """Copia el consolidado validado a un archivo fechado."""
    dag_run = context["dag_run"]
    momento = (
        dag_run.logical_date
        or dag_run.run_after
    )
    ds = momento.date().isoformat()

    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    destino = (
        config.OUTPUT_DIR
        / f"atp_partidos_{ds}.csv"
    )

    shutil.copy(
        ruta_partidos,
        destino,
    )

    log.info(
        "Dataset escrito en %s",
        destino,
    )

    return str(destino)
