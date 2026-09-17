from __future__ import annotations

from airflow.sdk import task
from atp import descarga


@task
def land_bronze_aux(**context) -> dict[str, str]:
    forzar = context["params"]["forzar_descarga"]
    rutas = descarga.descargar_auxiliares(forzar=forzar)
    return {clave: str(ruta) for clave, ruta in rutas.items()}
