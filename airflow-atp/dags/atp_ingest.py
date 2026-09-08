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

# ---------------------------------------------------------------------------
# Umbrales de validación
#
# Todos salen de perfilar el dataset real (77.474 partidos, 2000-2025), no de
# copiar un número de otro proyecto: un umbral heredado no protege nada. Al
# lado de cada uno está lo que se midió, que es lo que lo justifica.
# ---------------------------------------------------------------------------

# Sin estas columnas la fila no identifica un partido ni se puede ordenar en
# el tiempo. Medido: hoy las cinco tienen 0 nulos, así que exigir 0 es real.
COLUMNAS_OBLIGATORIAS = ["id_partido", "winner_id", "loser_id", "fecha", "tourney_id"]

# Piso de partidos por temporada. Medido: la más flaca es 2020 con 1.466
# (temporada acortada por COVID) y la mediana es 3.012. 1.200 deja un 18% de
# margen bajo ese piso histórico y sigue atrapando una descarga truncada.
MIN_PARTIDOS_POR_TEMPORADA = 1200

# Rangos físicamente posibles, holgados respecto de lo observado para atrapar
# el disparate sin castigar el caso real y extremo.
RANGOS_PLAUSIBLES = {
    # 0 es correcto: son los 51 walkovers (score "W/O"), partidos que no se
    # jugaron. El máximo observado, 665, es Isner-Mahut 2010 (11h05).
    "minutes": (0, 720),
    "winner_rank": (1, 2500),      # observado: 1 a 2.100
    "loser_rank": (1, 2500),       # observado: 1 a 2.159
    "winner_ht": (140, 230),       # observado: 155 a 211 cm
    "loser_ht": (140, 230),
    "winner_age": (14, 50),        # observado: 14,9 a 44,6 años
    "loser_age": (14, 50),
}

# Dominios cerrados: cualquier valor nuevo acá es una fuente que cambió.
DOMINIOS = {
    "best_of": {3, 5},
    "surface": {"Hard", "Clay", "Grass", "Carpet"},
}

# Cruces que no pueden violarse: no podés meter más aces que puntos sacados.
# Si el parseo se corriera de columna, estas relaciones se romperían en masa.
CRUCES_CONSISTENCIA = [
    ("w_ace", "w_svpt"), ("w_1stIn", "w_svpt"), ("w_1stWon", "w_1stIn"),
    ("w_2ndWon", "w_svpt"), ("w_bpSaved", "w_bpFaced"),
    ("l_ace", "l_svpt"), ("l_1stIn", "l_svpt"), ("l_1stWon", "l_1stIn"),
    ("l_2ndWon", "l_svpt"), ("l_bpSaved", "l_bpFaced"),
]

# Tolerancia de inconsistencias, en % de las filas comparables. No es cero
# absoluto porque la fuente ya trae 7 filas rotas sobre 71.055 comparables
# (0,004%). 0,05% deja ~12x de margen sobre ese ruido conocido, y una rotura
# sistemática del parseo movería el número en órdenes de magnitud.
MAX_PCT_INCONSISTENCIAS = 0.05

# Columnas donde el nulo NO es un dato faltante sino un valor con significado,
# así que quedan fuera del aviso de nulos: un `seed` vacío significa "no era
# cabeza de serie" (la mayoría no lo es) y un `entry` vacío, "entró directo"
# (no fue wildcard ni qualifier). Medido: 59-87% de nulos, todos legítimos.
COLUMNAS_NULABLES_POR_DISENIO = {
    "winner_seed", "loser_seed", "winner_entry", "loser_entry",
}

# Por encima de este % de nulos la columna se registra como aviso. No frena:
# es observabilidad. Medido: el resto de las columnas se agrupa en una banda
# conocida de 8,3% (stats de saque, ausentes en partidos viejos) a 9,3%
# (`minutes`). El umbral va apenas por encima de esa banda para que funcione
# como alarma real: hoy no suena, y suena si la cobertura empeora.
AVISO_PCT_NULOS = 0.10


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
    def validate(ruta_partidos: str, **context) -> str:
        """Valida el dataset contra las cinco dimensiones de calidad.

        La validación es una tarea más del grafo, no un chequeo posterior:
        va entre `consolidate` y `save`, así que **si un chequeo crítico no
        pasa, `save` no corre** y el dato malo no llega al entregable.

        Dos niveles de severidad, según qué esté en juego:

        * **Crítico -> frena.** Rompe una regla que no puede romperse sin que
          el dataset sea inservible o esté mutilado.
        * **Observabilidad -> avisa.** Vale la pena mirarlo, pero no invalida
          la corrida. Queda en el log y en `informe_calidad.csv`.

        Los umbrales salen del profiling del dataset (ver constantes arriba),
        no de un número heredado: un umbral que no se eligió para este dataset
        no protege nada.
        """
        import pandas as pd

        df = pd.read_csv(ruta_partidos, low_memory=False, parse_dates=["fecha"])
        params = context["params"]

        problemas: list[str] = []   # frenan la corrida
        avisos: list[str] = []      # sólo se registran

        # --- 1. UNICIDAD -------------------------------------------------
        # Test operativo de la unidad de análisis: si la clave repite, o la
        # unidad está mal definida o el pipeline duplica filas. Cero tolerancia.
        if not df["id_partido"].is_unique:
            repetidos = int(df["id_partido"].duplicated().sum())
            problemas.append(f"[unicidad] 'id_partido' con {repetidos} duplicados")

        # --- 2. COMPLETITUD ----------------------------------------------
        # Sin estas columnas la fila no identifica un partido ni se puede
        # ordenar en el tiempo. Medido: hoy las cinco tienen 0 nulos.
        for col in COLUMNAS_OBLIGATORIAS:
            nulos = int(df[col].isna().sum())
            if nulos:
                problemas.append(f"[completitud] '{col}' tiene {nulos} nulos y no puede tenerlos")

        vacias = df.columns[df.isna().all()].tolist()
        if vacias:
            problemas.append(f"[completitud] columnas 100% nulas: {vacias}")

        # Volumen POR TEMPORADA, no global: un piso global de 1.000 filas se
        # cumpliría con una sola temporada descargada de las 26 pedidas, y el
        # DAG quedaría en verde con un dataset mutilado.
        por_temporada = df.groupby("anio_archivo").size()
        flacas = por_temporada[por_temporada < MIN_PARTIDOS_POR_TEMPORADA]
        if not flacas.empty:
            problemas.append(
                f"[completitud] temporadas con menos de {MIN_PARTIDOS_POR_TEMPORADA} "
                f"partidos: {flacas.to_dict()}")

        if df.shape[1] < 5:
            problemas.append(f"[completitud] muy pocas columnas: {df.shape[1]} (se piden >= 5)")

        # --- 3. ACTUALIDAD -----------------------------------------------
        # ¿Está todo lo que se pidió, o alguna descarga falló en silencio?
        pedidas = set(range(params["anio_desde"], params["anio_hasta"] + 1))
        presentes = set(df["anio_archivo"].unique())
        if pedidas - presentes:
            problemas.append(f"[actualidad] faltan temporadas pedidas: {sorted(pedidas - presentes)}")

        # --- 4. PRECISIÓN -------------------------------------------------
        # Rangos físicamente posibles. Un jugador de 300 cm no es un dato
        # raro: es un error de captura. Los límites son holgados respecto de
        # lo observado, para atrapar el disparate sin castigar el caso real
        # (el máximo de minutos observado, 665, es Isner-Mahut 2010).
        for col, (minimo, maximo) in RANGOS_PLAUSIBLES.items():
            s = pd.to_numeric(df[col], errors="coerce")
            fuera = int(((s < minimo) | (s > maximo)).sum())
            if fuera:
                problemas.append(
                    f"[precisión] '{col}' con {fuera} valores fuera de [{minimo}, {maximo}]")

        for col, dominio in DOMINIOS.items():
            invalidos = df[col].dropna()
            invalidos = invalidos[~invalidos.isin(dominio)]
            if len(invalidos):
                problemas.append(
                    f"[precisión] '{col}' con {len(invalidos)} valores fuera del dominio "
                    f"{sorted(dominio)}: {sorted(invalidos.unique())[:5]}")

        # --- 5. CONSISTENCIA ----------------------------------------------
        # Cada estadística es plausible por separado; el problema aparece al
        # cruzarlas. Si el parseo se corriera de columna, estas relaciones se
        # romperían en masa.
        #
        # Se comparan sólo las filas donde ambos valores existen: `NaN <= x`
        # devuelve False en pandas y contaría como violación falsa.
        #
        # Tolerancia y no cero absoluto porque la fuente ya trae 7 filas
        # inconsistentes sobre 71.055 comparables (0,004%). El umbral deja
        # margen para ese ruido conocido y sigue atrapando una rotura
        # sistemática, que movería el número en órdenes de magnitud.
        for menor, mayor in CRUCES_CONSISTENCIA:
            comparables = df[menor].notna() & df[mayor].notna()
            n = int(comparables.sum())
            if not n:
                continue
            viol = int((df.loc[comparables, menor] > df.loc[comparables, mayor]).sum())
            pct = viol / n * 100
            if pct > MAX_PCT_INCONSISTENCIAS:
                problemas.append(
                    f"[consistencia] '{menor} <= {mayor}' violado en {viol} de {n} filas "
                    f"({pct:.3f}%, tope {MAX_PCT_INCONSISTENCIAS}%)")
            elif viol:
                avisos.append(f"{menor} <= {mayor}: {viol} filas inconsistentes ({pct:.3f}%)")

        # --- Criterio de la consigna: mezcla de tipos ---------------------
        # `is_string_dtype` además de `is_object_dtype` porque en pandas 3 las
        # columnas de texto dejaron de ser `object` y pasaron a ser `str`: con
        # sólo el primer chequeo, esto daría falso al reconstruir la imagen con
        # una versión más nueva (requirements.txt sólo fija `pandas>=2.2`).
        tipos = df.dtypes
        hay_numerica = tipos.apply(lambda t: pd.api.types.is_numeric_dtype(t)).any()
        hay_fecha = tipos.apply(lambda t: pd.api.types.is_datetime64_any_dtype(t)).any()
        hay_categorica = tipos.apply(
            lambda t: pd.api.types.is_object_dtype(t)
            or pd.api.types.is_string_dtype(t)
            or isinstance(t, pd.CategoricalDtype)
        ).any()
        if not (hay_numerica and hay_fecha and hay_categorica):
            problemas.append(
                f"[tipos] falta variedad (numérica={hay_numerica}, "
                f"fecha={hay_fecha}, categórica={hay_categorica})")

        # --- Observabilidad: nulos altos, avisan pero no frenan -----------
        # Se excluyen las columnas donde el nulo es un valor con significado
        # propio, no un dato faltante (ver COLUMNAS_NULABLES_POR_DISENIO).
        nulos_pct = df.isna().mean().sort_values(ascending=False)
        for col, pct in nulos_pct[nulos_pct > AVISO_PCT_NULOS].items():
            if col not in COLUMNAS_NULABLES_POR_DISENIO:
                avisos.append(f"'{col}' con {pct*100:.1f}% de nulos")

        # --- Veredicto -----------------------------------------------------
        for aviso in avisos:
            log.warning("Observabilidad: %s", aviso)

        if problemas:
            raise ValueError(
                "Validación fallida, no se publica el dataset:\n  - "
                + "\n  - ".join(problemas))

        # El informe de nulos por columna: saber cuáles hay y por qué es parte
        # de lo que hay que poder explicar, aunque no bloquee.
        informe = consolidar.informe_calidad(df)
        ruta_informe = config.DIR_PROCESADO / "informe_calidad.csv"
        informe.to_csv(ruta_informe, index=False)

        log.info(
            "Validación OK: %s filas x %s columnas, %s temporadas, clave única, "
            "%s avisos de observabilidad",
            len(df), df.shape[1], len(presentes), len(avisos))
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

    save(validate(consolidado))


atp_ingest()
