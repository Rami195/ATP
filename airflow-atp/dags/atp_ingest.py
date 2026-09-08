"""
DAG principal del pipeline ATP.

Este archivo contiene solamente la orquestación. La implementación de cada
nodo del grafo vive en `include/atp/tasks/`, de forma similar a un Job de
Databricks donde cada task apunta a su propio notebook o script.
"""

from __future__ import annotations

import pendulum
from airflow.sdk import Param, dag

from atp import config
from atp.tasks import (
    consolidate,
    discover_seasons,
    land_bronze,
    land_bronze_aux,
    save,
    validate,
)


@dag(
    dag_id="atp_ingest",
    schedule="0 */8 * * *",
    start_date=pendulum.datetime(
        2026,
        8,
        1,
        tz="America/Argentina/Buenos_Aires",
    ),
    catchup=False,
    max_active_tasks=8,
    tags=[
        "ciencia-de-datos",
        "proyecto-integrador",
        "entrega-1",
    ],
    doc_md=__doc__,
    params={
        "anio_desde": Param(
            config.ANIO_DESDE_DEFECTO,
            type="integer",
            title="Primera temporada",
            description=(
                "Primera temporada a descargar "
                "(la fuente arranca en 1968)."
            ),
        ),
        "anio_hasta": Param(
            config.ANIO_HASTA_DEFECTO,
            type="integer",
            title="Última temporada",
            description=(
                "Última temporada a descargar. "
                "2026 está incompleta en la fuente."
            ),
        ),
        "forzar_descarga": Param(
            False,
            type="boolean",
            title="Forzar la descarga",
            description=(
                "Ignora la caché de Bronze y "
                "vuelve a pedir todas las temporadas."
            ),
        ),
    },
)
def atp_ingest():
    # 1. Determinar temporadas
    anios = discover_seasons()

    # 2. Ingesta Bronze
    bronces = land_bronze.expand(
        anio=anios
    )
    auxiliares = land_bronze_aux()

    # 3. Consolidación Silver
    consolidado = consolidate(
        bronces
    )

    # La ingesta auxiliar debe terminar antes
    # de continuar con la consolidación.
    auxiliares >> consolidado

    # 4. Calidad
    validado = validate(
        consolidado
    )

    # 5. Publicación
    save(validado)


atp_ingest()
