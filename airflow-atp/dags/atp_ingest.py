"""Pipeline ATP orientado a la pregunta de negocio sobre estilos de juego."""

>>>>>>> 20d695d (Refactor pipeline ATP y datasets analiticos)
from __future__ import annotations

import pendulum
from airflow.sdk import Param, dag

from atp import config
from atp.tasks import (
    build_player_profiles,
    build_prematch_matchups,
    consolidate,
    discover_seasons,
    land_bronze,
    land_bronze_aux,
    normalize_player_matches,
    validate_analytics,
    validate_matches,
)


@dag(
    dag_id="atp_ingest",
    schedule="0 */8 * * *",
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    max_active_tasks=8,
    tags=["ciencia-de-datos", "atp", "estilos", "proyecto-integrador"],
    doc_md=__doc__,
    params={
        "anio_desde": Param(
            config.ANIO_DESDE_DEFECTO,
            type="integer",
            title="Primera temporada",
        ),
        "anio_hasta": Param(
            config.ANIO_HASTA_DEFECTO,
            type="integer",
            title="Ultima temporada",
        ),
        "forzar_descarga": Param(
            False,
            type="boolean",
            title="Forzar descarga Bronze",
        ),
        "min_partidos_estilo": Param(
            config.MIN_PARTIDOS_ESTILO,
            type="integer",
            minimum=5,
            title="Minimo de partidos con stats para perfil de estilo",
        ),
        "min_historial_prematch": Param(
            config.MIN_HISTORIAL_PREMATCH,
            type="integer",
            minimum=5,
            title="Minimo de partidos previos por jugador para modelado",
        ),
    },
)
def atp_ingest():
    # BRONZE
    anios = discover_seasons()
    temporadas = land_bronze.expand(anio=anios)
    auxiliares = land_bronze_aux()

    # SILVER: una fila = un partido
    consolidado = consolidate(temporadas)
    partidos_validos = validate_matches(consolidado)

    # GOLD intermedio: una fila = un tenista en un partido
    player_match = normalize_player_matches(partidos_validos, auxiliares)

    # GOLD final 1: una fila = un tenista, para descubrir estilos
    perfiles = build_player_profiles(player_match)

    # GOLD final 2: una fila = un partido A/B, para probar estilo vs ranking
    matchups = build_prematch_matchups(player_match)

    # Quality gate final de las salidas analiticas
    validate_analytics(perfiles, matchups)


atp_ingest()
