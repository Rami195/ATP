from __future__ import annotations

from airflow.sdk import task
from atp import calidad


@task
def validate_matches(ruta_partidos: str, **context) -> str:
    params = context["params"]
    return calidad.validar_partidos_consolidados(
        ruta_partidos,
        anio_desde=params["anio_desde"],
        anio_hasta=params["anio_hasta"],
    )
