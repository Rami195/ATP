"""
### Dataset canónico ATP — Proyecto Integrador, Ciencia de Datos UTN FRM 2026

Construye el dataset a nivel partido para responder: ¿en qué medida el
ranking, la forma reciente y el rendimiento bajo presión (break points,
tie-breaks, sets decisivos) predicen el ganador de un partido ATP?

**Una fila = un partido.** La columna objetivo (para las entregas siguientes)
es quién ganó; acá en la Entrega 1 el pipeline se detiene en el dataset
consolidado, todavía en formato `winner_`/`loser_` (la reasignación A/B para
evitar la fuga por ese formato es trabajo de `features.py`, fuera de esta
entrega).

**Dos capas, dos grupos de tareas**, mismo modelo medallón que `fifa_ingest`:

* **Bronce** (`land_bronze`, `land_bronze_aux`) — los CSV de temporada tal
  como los devuelve TML-Database, sin interpretar. Son las únicas tareas que
  tocan la fuente. Una temporada ya bajada no se vuelve a pedir.
* **Plata** (`consolidate`) — un partido por fila, tipado, deduplicado, con
  `id_partido` único. No toca la red: lee del bronce ya en disco.

**Por qué no hay sensor ni branching acá**, a diferencia de `fifa_ingest`:
TML-Database es un repositorio de GitHub estático — no hay nada externo
impredecible que esperar (no hay Cloudflare, no hay caídas intermitentes), así
que agregar esa complejidad copiaría un patrón sin que resuelva un problema
real de esta fuente.

**Reproducibilidad**: mismo código + misma fuente = mismo resultado. Correr
el DAG dos veces seguidas deja ver, en los logs de `land_bronze`, que las
temporadas ya bajadas no generan ninguna request nueva — la misma propiedad
del bronce que vimos con sofifa.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pendulum
from airflow.sdk import Param, dag, task

from atp import config, consolidar, descarga

log = logging.getLogger(__name__)

OUTPUT_DIR = Path("/usr/local/airflow/include/output")


@dag(
    dag_id="atp_ingest",
    # A demanda: no hay necesidad de correr esto todos los días para la
    # Entrega 1, y la fuente no publica con una cadencia que lo justifique.
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    # Cortesía con la fuente: no hace falta más para 26 temporadas, y evita
    # abrir más conexiones simultáneas de las necesarias contra GitHub.
    max_active_tasks=8,
    tags=["ciencia-de-datos", "proyecto-integrador", "entrega-1"],
    doc_md=__doc__,
    params={
        "anio_desde": Param(
            config.ANIO_DESDE_DEFECTO, type="integer",
            title="Primera temporada",
            description="Primera temporada a descargar (la fuente arranca en 1968).",
        ),
        "anio_hasta": Param(
            config.ANIO_HASTA_DEFECTO, type="integer",
            title="Última temporada",
            description="Última temporada a descargar. 2026 está incompleta en la fuente.",
        ),
        "forzar_descarga": Param(
            False, type="boolean",
            title="Forzar la descarga",
            description="Ignora la caché de bronce y vuelve a pedir todas las temporadas.",
        ),
    },
)
def atp_ingest():

    @task
    def discover_seasons(**context) -> list[int]:
        """Arma la lista de temporadas a procesar, según los parámetros de la corrida."""
        params = context["params"]
        desde, hasta = params["anio_desde"], params["anio_hasta"]

        if desde < config.ANIO_MIN_DISPONIBLE:
            raise ValueError(f"La fuente arranca en {config.ANIO_MIN_DISPONIBLE}.")
        if desde > hasta:
            raise ValueError("anio_desde no puede ser mayor que anio_hasta.")

        anios = list(range(desde, hasta + 1))
        log.info("Temporadas a procesar: %s-%s (%s temporadas)", desde, hasta, len(anios))
        return anios

    @task(map_index_template="{{ task.op_kwargs['anio'] }}",
          retries=2, retry_delay=pendulum.duration(seconds=15))
    def land_bronze(anio: int, **context) -> str:
        """**Capa bronce**: baja el CSV de una temporada, sin interpretarlo.

        Si la temporada ya está en disco, no se vuelve a pedir (misma regla
        append-only del bronce que vimos con sofifa) — `descargar_temporada`
        ya trae esa lógica de `include/atp/descarga.py`.
        """
        forzar = context["params"]["forzar_descarga"]
        destino = descarga.descargar_temporada(anio, forzar=forzar)
        return str(destino)

    @task
    def land_bronze_aux(**context) -> list[str]:
        """Bronce de las tablas auxiliares (biografías, torneos en curso).

        Tarea única (no `.expand()`): son sólo dos archivos chicos, no
        justifica el paralelismo de tareas dinámicas.
        """
        forzar = context["params"]["forzar_descarga"]
        rutas = descarga.descargar_auxiliares(forzar=forzar)
        return [str(p) for p in rutas.values()]

    @task
    def consolidate(rutas_temporadas: list[str]) -> str:
        """**Capa plata**: une las temporadas en una tabla partido-nivel.

        No toca la red — todo lo que necesita ya está en el bronce. Tipa
        columnas, deduplica y arma `id_partido` único (ver
        `include/atp/consolidar.py`).
        """
        partidos = consolidar.consolidar([Path(r) for r in rutas_temporadas])

        config.DIR_PROCESADO.mkdir(parents=True, exist_ok=True)
        destino = config.DIR_PROCESADO / "partidos_consolidado.csv"
        partidos.to_csv(destino, index=False)

        log.info("Consolidado: %s filas x %s columnas -> %s",
                 len(partidos), len(partidos.columns), destino)
        return str(destino)

    @task
    def quality_report(ruta_partidos: str) -> str:
        """Valida los 6 criterios medibles de la Entrega 1 sobre el dataset.

        Si alguno falla, el DAG falla a propósito: no se publica un dataset
        que no cumple el piso de calidad. Ver "Qué es un buen dataset de
        salida" en las instrucciones de la entrega.
        """
        import pandas as pd

        df = pd.read_csv(ruta_partidos, low_memory=False, parse_dates=["fecha"])

        problemas = []

        if not df["id_partido"].is_unique:
            repetidos = df["id_partido"].duplicated().sum()
            problemas.append(f"clave 'id_partido' con {repetidos} duplicados")

        if len(df) <= 1000:
            problemas.append(f"volumen insuficiente: {len(df)} filas (se pide > 1.000)")

        if df.shape[1] < 5:
            problemas.append(f"muy pocas columnas: {df.shape[1]} (se piden >= 5)")

        tipos = df.dtypes
        hay_numerica = tipos.apply(lambda t: pd.api.types.is_numeric_dtype(t)).any()
        hay_fecha = tipos.apply(lambda t: pd.api.types.is_datetime64_any_dtype(t)).any()
        hay_categorica = tipos.apply(
            lambda t: pd.api.types.is_object_dtype(t) or isinstance(t, pd.CategoricalDtype)
        ).any()
        if not (hay_numerica and hay_fecha and hay_categorica):
            problemas.append(
                f"falta variedad de tipos (numérica={hay_numerica}, "
                f"fecha={hay_fecha}, categórica={hay_categorica})")

        vacias = df.columns[df.isna().all()].tolist()
        if vacias:
            problemas.append(f"columnas 100% nulas: {vacias}")

        if problemas:
            raise ValueError("Chequeo de calidad fallido:\n  - " + "\n  - ".join(problemas))

        # El informe de nulos por columna (informativo, no bloqueante): saber
        # cuáles hay y por qué es parte de lo que hay que poder explicar.
        informe = consolidar.informe_calidad(df)
        ruta_informe = config.DIR_PROCESADO / "informe_calidad.csv"
        informe.to_csv(ruta_informe, index=False)

        log.info("Calidad OK: %s filas x %s columnas, clave única, sin columnas vacías",
                 len(df), df.shape[1])
        return ruta_partidos

    @task
    def save(ruta_partidos: str, **context) -> str:
        """Escribe el entregable fechado con la corrida.

        La fecha sale del `DagRun`, no de `context["ds"]`: este DAG corre a
        demanda (`schedule=None`), así que no siempre hay un intervalo de
        datos asociado.
        """
        import shutil

        dag_run = context["dag_run"]
        momento = dag_run.logical_date or dag_run.run_after
        ds = momento.date().isoformat()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        destino = OUTPUT_DIR / f"atp_partidos_{ds}.csv"
        shutil.copy(ruta_partidos, destino)

        log.info("Dataset escrito en %s", destino)
        return str(destino)

    anios = discover_seasons()
    bronces = land_bronze.expand(anio=anios)
    auxiliares = land_bronze_aux()

    # land_bronze_aux no se usa como insumo de consolidate en esta entrega
    # (las bios se joinean recién en features.py, Entrega 2/3), pero corre
    # igual para que el bronce quede completo desde ya.
    consolidado = consolidate(bronces)
    auxiliares >> consolidado

    save(quality_report(consolidado))


atp_ingest()
