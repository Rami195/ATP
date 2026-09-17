from __future__ import annotations

import pendulum
from airflow.sdk import task
from atp import descarga


@task(
    map_index_template="{{ task.op_kwargs['anio'] }}",
    retries=2,
    retry_delay=pendulum.duration(seconds=15),
)
def land_bronze(anio: int, **context) -> str:
    forzar = context["params"]["forzar_descarga"]
    return str(descarga.descargar_temporada(anio, forzar=forzar))
