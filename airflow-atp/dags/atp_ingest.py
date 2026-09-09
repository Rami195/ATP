"""
### Dataset ATP a nivel partido

Sostiene la pregunta del proyecto:

> **Cómo se le gana a quién: estilos de juego del circuito ATP.**
> ¿Existen estilos de juego diferenciables entre los tenistas según sus
> patrones de saque y golpeo? ¿Hay estilos globalmente superiores, y el
> emparejamiento de estilos predice el ganador de un partido por encima del
> ranking?

**Una fila = un partido.** Los estilos son de un jugador y se construyen
agregando sus partidos; el emparejamiento se evalúa a nivel partido, que es
la unidad de esta tabla.

El resultado está en el par `winner_`/`loser_`, el formato en que lo publica
la fuente. Ese formato tiene una fuga de datos —el nombre de la columna ya
contiene la respuesta— que se resuelve reasignando a jugador A / jugador B en
`features.py`, aguas abajo.

**Cobertura de la fuente**: el saque está completo (aces, dobles faltas,
primer saque, break points). El golpeo no viene medido —no hay winners ni
errores no forzados— y se aproxima con el rendimiento al resto, el tipo de
revés (81,5% de los partidos) y el perfil por superficie.

**Dos capas**, siguiendo el modelo medallón:

* **Bronce** (`land_bronze`, `land_bronze_aux`) — los CSV de temporada tal
  como llegan, sin interpretar. Únicas tareas que tocan la fuente, y una
  temporada ya bajada no se vuelve a pedir.
* **Plata** (`consolidate`) — un partido por fila, tipado, deduplicado, con
  `id_partido` único. No toca la red: lee del bronce.

**Sin sensor ni branching**: el portal sirve archivos estáticos, sin
Cloudflare ni JavaScript, así que no hay espera real que modelar. Al ser un
servidor propio puede tener caídas puntuales, cubiertas por los 3 reintentos
de `_descargar_archivo` y la caché del bronce.

**Reproducibilidad**: mismo código + misma fuente = mismo resultado. En una
segunda corrida `land_bronze` no genera ninguna request.
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
# Umbrales de validación. Cada uno sale de perfilar el dataset; al lado va la
# medición que lo justifica, para poder revisarlo cuando la fuente cambie.
# ---------------------------------------------------------------------------

# Sin estas columnas la fila no identifica un partido. Medido: 0 nulos en las
# cinco, así que exigir cero es realista.
COLUMNAS_OBLIGATORIAS = ["id_partido", "winner_id", "loser_id", "fecha", "tourney_id"]

# Piso por temporada, no global: un piso global se cumpliría con una sola de
# las 26. Medido: la más flaca es 2020 con 1.466 (COVID), mediana 3.012.
MIN_PARTIDOS_POR_TEMPORADA = 1200

# Rangos físicamente posibles, holgados sobre lo observado: atrapan el
# disparate sin castigar el caso real extremo.
RANGOS_PLAUSIBLES = {
    # Los 409 walkovers llegan con `minutes` nulo, no en 0. Máximo observado:
    # 665 min, Isner-Mahut 2010.
    "minutes": (0, 720),
    "winner_rank": (1, 2500),      # observado: 1 a 2.100
    "loser_rank": (1, 2500),       # observado: 1 a 2.159
    "winner_ht": (140, 230),       # observado: 155 a 211 cm
    "loser_ht": (140, 230),
    "winner_age": (14, 50),        # observado: 14,9 a 44,6 años
    "loser_age": (14, 50),
}

# Dominios cerrados: un valor nuevo acá significa que la fuente cambió.
DOMINIOS = {
    "best_of": {3, 5},
    "surface": {"Hard", "Clay", "Grass", "Carpet"},
}

# Relaciones que no pueden violarse dentro de una fila. Si el parseo corriera
# las columnas un lugar, se romperían en masa.
CRUCES_CONSISTENCIA = [
    ("w_ace", "w_svpt"), ("w_1stIn", "w_svpt"), ("w_1stWon", "w_1stIn"),
    ("w_2ndWon", "w_svpt"), ("w_bpSaved", "w_bpFaced"),
    ("l_ace", "l_svpt"), ("l_1stIn", "l_svpt"), ("l_1stWon", "l_1stIn"),
    ("l_2ndWon", "l_svpt"), ("l_bpSaved", "l_bpFaced"),
]

# Tolerancia por cruce. No es cero porque la fuente ya trae 10 violaciones
# sobre 70.799 comparables (0,0042% la peor). Una rotura del parseo llevaría
# el mismo chequeo a 99,98%.
MAX_PCT_INCONSISTENCIAS = 0.05

# Acá el nulo es un valor, no un dato faltante: `seed` vacío = no sembrado,
# `entry` vacío = entró directo. Medido: 59-87% de nulos, todos legítimos.
COLUMNAS_NULABLES_POR_DISENIO = {
    "winner_seed", "loser_seed", "winner_entry", "loser_entry",
}

# Umbral de aviso (no frena). Va apenas encima de la banda conocida de 8,6%
# (stats de saque) a 9,1% (`minutes`): hoy no suena, suena si empeora.
AVISO_PCT_NULOS = 0.10


@dag(
    dag_id="atp_ingest",
    # A demanda: la fuente no publica con una cadencia que justifique un
    # schedule fijo.
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Argentina/Buenos_Aires"),
    catchup=False,
    # Cortesía con la fuente: no hace falta más para 26 temporadas, y evita
    # abrir más conexiones simultáneas de las necesarias contra el portal,
    # que es un servidor propio y no un CDN.
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

        El bronce es append-only: si la temporada ya está en disco no se
        vuelve a pedir. Esa lógica vive en `descargar_temporada`, en
        `include/atp/descarga.py`.
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

        Los umbrales salen del profiling del dataset, y están definidos como
        constantes arriba del archivo con la medición que los justifica.
        """
        import pandas as pd

        df = pd.read_csv(ruta_partidos, low_memory=False, parse_dates=["fecha"])
        params = context["params"]

        problemas: list[str] = []   # frenan la corrida
        avisos: list[str] = []      # sólo se registran

        # --- 1. UNICIDAD -------------------------------------------------
        # Test operativo de la unidad de análisis: si la clave repite, o está
        # mal definida o el pipeline duplica. Cero tolerancia.
        if not df["id_partido"].is_unique:
            repetidos = int(df["id_partido"].duplicated().sum())
            problemas.append(f"[unicidad] 'id_partido' con {repetidos} duplicados")

        # --- 2. COMPLETITUD ----------------------------------------------
        for col in COLUMNAS_OBLIGATORIAS:
            nulos = int(df[col].isna().sum())
            if nulos:
                problemas.append(f"[completitud] '{col}' tiene {nulos} nulos y no puede tenerlos")

        vacias = df.columns[df.isna().all()].tolist()
        if vacias:
            problemas.append(f"[completitud] columnas 100% nulas: {vacias}")

        # Por temporada: un piso global quedaría en verde con un dataset
        # mutilado si sólo bajara una de las 26.
        por_temporada = df.groupby("anio_archivo").size()
        flacas = por_temporada[por_temporada < MIN_PARTIDOS_POR_TEMPORADA]
        if not flacas.empty:
            problemas.append(
                f"[completitud] temporadas con menos de {MIN_PARTIDOS_POR_TEMPORADA} "
                f"partidos: {flacas.to_dict()}")

        if df.shape[1] < 5:
            problemas.append(f"[completitud] muy pocas columnas: {df.shape[1]} (se piden >= 5)")

        # --- 3. ACTUALIDAD -----------------------------------------------
        # Atrapa la descarga que falló en silencio.
        pedidas = set(range(params["anio_desde"], params["anio_hasta"] + 1))
        presentes = set(df["anio_archivo"].unique())
        if pedidas - presentes:
            problemas.append(f"[actualidad] faltan temporadas pedidas: {sorted(pedidas - presentes)}")

        # --- 4. PRECISIÓN -------------------------------------------------
        # Un jugador de 300 cm no es un dato raro: es un error de captura.
        # Los nulos no cuentan como violación (comparar con NaN da False).
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
        # cruzarlas.
        #
        # Sólo se comparan filas con ambos valores presentes: `NaN <= x` da
        # False en pandas y contaría como violación falsa.
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

        # --- MEZCLA DE TIPOS ----------------------------------------------
        # Sin fechas no hay corte temporal; sin categóricas no hay segmentación.
        #
        # `is_string_dtype` además de `is_object_dtype`: en pandas 3 las
        # columnas de texto pasaron de `object` a `str`, y requirements.txt
        # sólo fija `pandas>=2.2`.
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

        # El informe de nulos por columna
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

    # Las tablas auxiliares todavía no alimentan a consolidate: las bios se
    # joinean recién en features.py. La dependencia se declara igual para que
    # el bronce quede completo antes de pasar a plata.
    consolidado = consolidate(bronces)
    auxiliares >> consolidado

    save(validate(consolidado))


atp_ingest()
