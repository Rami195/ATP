"""Task que descarga las tablas auxiliares a la capa Bronze."""

from __future__ import annotations

from airflow.sdk import task

from atp import descarga


@task
def land_bronze_aux(**context) -> list[str]:
    """Descarga biografías y torneos en curso."""
    forzar = context["params"]["forzar_descarga"]
    rutas = descarga.descargar_auxiliares(forzar=forzar)
    return [str(path) for path in rutas.values()]
