"""Task que determina qué temporadas debe procesar la corrida."""

from __future__ import annotations

import logging

from airflow.sdk import task

from atp import config

log = logging.getLogger(__name__)


@task
def discover_seasons(**context) -> list[int]:
    """Arma la lista de temporadas a procesar según los parámetros del DAG."""
    params = context["params"]
    desde = params["anio_desde"]
    hasta = params["anio_hasta"]

    if desde < config.ANIO_MIN_DISPONIBLE:
        raise ValueError(
            f"La fuente arranca en {config.ANIO_MIN_DISPONIBLE}."
        )

    if desde > hasta:
        raise ValueError(
            "anio_desde no puede ser mayor que anio_hasta."
        )

    anios = list(range(desde, hasta + 1))

    log.info(
        "Temporadas a procesar: %s-%s (%s temporadas)",
        desde,
        hasta,
        len(anios),
    )

    return anios
