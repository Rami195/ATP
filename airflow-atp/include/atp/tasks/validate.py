"""Task de control de calidad del dataset consolidado."""

from __future__ import annotations

import logging

import pandas as pd
from airflow.sdk import task

from atp import config, consolidar

log = logging.getLogger(__name__)


COLUMNAS_OBLIGATORIAS = [
    "id_partido",
    "winner_id",
    "loser_id",
    "fecha",
    "tourney_id",
]

MIN_PARTIDOS_POR_TEMPORADA = 1200

RANGOS_PLAUSIBLES = {
    "minutes": (0, 720),
    "winner_rank": (1, 2500),
    "loser_rank": (1, 2500),
    "winner_ht": (140, 230),
    "loser_ht": (140, 230),
    "winner_age": (14, 50),
    "loser_age": (14, 50),
}

DOMINIOS = {
    "best_of": {3, 5},
    "surface": {"Hard", "Clay", "Grass", "Carpet"},
}

CRUCES_CONSISTENCIA = [
    ("w_ace", "w_svpt"),
    ("w_1stIn", "w_svpt"),
    ("w_1stWon", "w_1stIn"),
    ("w_2ndWon", "w_svpt"),
    ("w_bpSaved", "w_bpFaced"),
    ("l_ace", "l_svpt"),
    ("l_1stIn", "l_svpt"),
    ("l_1stWon", "l_1stIn"),
    ("l_2ndWon", "l_svpt"),
    ("l_bpSaved", "l_bpFaced"),
]

MAX_PCT_INCONSISTENCIAS = 0.05

COLUMNAS_NULABLES_POR_DISENIO = {
    "winner_seed",
    "loser_seed",
    "winner_entry",
    "loser_entry",
}

AVISO_PCT_NULOS = 0.10


@task
def validate(ruta_partidos: str, **context) -> str:
    """Valida unicidad, completitud, actualidad, precisión y consistencia."""
    df = pd.read_csv(
        ruta_partidos,
        low_memory=False,
        parse_dates=["fecha"],
    )

    params = context["params"]

    problemas: list[str] = []
    avisos: list[str] = []

    # 1. UNICIDAD
    if not df["id_partido"].is_unique:
        repetidos = int(
            df["id_partido"].duplicated().sum()
        )
        problemas.append(
            "[unicidad] 'id_partido' con "
            f"{repetidos} duplicados"
        )

    # 2. COMPLETITUD
    for col in COLUMNAS_OBLIGATORIAS:
        nulos = int(df[col].isna().sum())
        if nulos:
            problemas.append(
                f"[completitud] '{col}' tiene "
                f"{nulos} nulos y no puede tenerlos"
            )

    vacias = df.columns[
        df.isna().all()
    ].tolist()

    if vacias:
        problemas.append(
            "[completitud] columnas 100% nulas: "
            f"{vacias}"
        )

    por_temporada = (
        df.groupby("anio_archivo").size()
    )

    flacas = por_temporada[
        por_temporada
        < MIN_PARTIDOS_POR_TEMPORADA
    ]

    if not flacas.empty:
        problemas.append(
            "[completitud] temporadas con menos de "
            f"{MIN_PARTIDOS_POR_TEMPORADA} partidos: "
            f"{flacas.to_dict()}"
        )

    if df.shape[1] < 5:
        problemas.append(
            "[completitud] muy pocas columnas: "
            f"{df.shape[1]} (se piden >= 5)"
        )

    # 3. ACTUALIDAD
    pedidas = set(
        range(
            params["anio_desde"],
            params["anio_hasta"] + 1,
        )
    )

    presentes = set(
        df["anio_archivo"].unique()
    )

    faltantes = pedidas - presentes

    if faltantes:
        problemas.append(
            "[actualidad] faltan temporadas pedidas: "
            f"{sorted(faltantes)}"
        )

    # 4. PRECISIÓN
    for col, (minimo, maximo) in (
        RANGOS_PLAUSIBLES.items()
    ):
        s = pd.to_numeric(
            df[col],
            errors="coerce",
        )

        fuera = int(
            (
                (s < minimo)
                | (s > maximo)
            ).sum()
        )

        if fuera:
            problemas.append(
                f"[precisión] '{col}' con {fuera} "
                f"valores fuera de "
                f"[{minimo}, {maximo}]"
            )

    for col, dominio in DOMINIOS.items():
        invalidos = df[col].dropna()
        invalidos = invalidos[
            ~invalidos.isin(dominio)
        ]

        if len(invalidos):
            problemas.append(
                f"[precisión] '{col}' con "
                f"{len(invalidos)} valores fuera "
                f"del dominio {sorted(dominio)}: "
                f"{sorted(invalidos.unique())[:5]}"
            )

    # 5. CONSISTENCIA
    for menor, mayor in CRUCES_CONSISTENCIA:
        comparables = (
            df[menor].notna()
            & df[mayor].notna()
        )

        n = int(comparables.sum())

        if not n:
            continue

        viol = int(
            (
                df.loc[comparables, menor]
                > df.loc[comparables, mayor]
            ).sum()
        )

        pct = viol / n * 100

        if pct > MAX_PCT_INCONSISTENCIAS:
            problemas.append(
                f"[consistencia] '{menor} <= {mayor}' "
                f"violado en {viol} de {n} filas "
                f"({pct:.3f}%, tope "
                f"{MAX_PCT_INCONSISTENCIAS}%)"
            )
        elif viol:
            avisos.append(
                f"{menor} <= {mayor}: "
                f"{viol} filas inconsistentes "
                f"({pct:.3f}%)"
            )

    # Mezcla de tipos
    tipos = df.dtypes

    hay_numerica = tipos.apply(
        lambda t: pd.api.types.is_numeric_dtype(t)
    ).any()

    hay_fecha = tipos.apply(
        lambda t:
        pd.api.types.is_datetime64_any_dtype(t)
    ).any()

    hay_categorica = tipos.apply(
        lambda t:
        pd.api.types.is_object_dtype(t)
        or pd.api.types.is_string_dtype(t)
        or isinstance(t, pd.CategoricalDtype)
    ).any()

    if not (
        hay_numerica
        and hay_fecha
        and hay_categorica
    ):
        problemas.append(
            "[tipos] falta variedad "
            f"(numérica={hay_numerica}, "
            f"fecha={hay_fecha}, "
            f"categórica={hay_categorica})"
        )

    # Observabilidad: nulos altos
    nulos_pct = (
        df.isna()
        .mean()
        .sort_values(ascending=False)
    )

    for col, pct in (
        nulos_pct[
            nulos_pct > AVISO_PCT_NULOS
        ].items()
    ):
        if (
            col
            not in COLUMNAS_NULABLES_POR_DISENIO
        ):
            avisos.append(
                f"'{col}' con "
                f"{pct * 100:.1f}% de nulos"
            )

    for aviso in avisos:
        log.warning(
            "Observabilidad: %s",
            aviso,
        )

    if problemas:
        raise ValueError(
            "Validación fallida, "
            "no se publica el dataset:\n  - "
            + "\n  - ".join(problemas)
        )

    informe = consolidar.informe_calidad(df)

    ruta_informe = (
        config.DIR_PROCESADO
        / "informe_calidad.csv"
    )

    informe.to_csv(
        ruta_informe,
        index=False,
    )

    log.info(
        "Validación OK: %s filas x %s columnas, "
        "%s temporadas, clave única, "
        "%s avisos de observabilidad",
        len(df),
        df.shape[1],
        len(presentes),
        len(avisos),
    )

    return ruta_partidos
