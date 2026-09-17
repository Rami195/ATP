"""Validaciones de calidad para las capas Silver y Gold del pipeline ATP."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import config, consolidar
from .features import STYLE_FEATURES

log = logging.getLogger(__name__)

COLUMNAS_OBLIGATORIAS = ["id_partido", "winner_id", "loser_id", "fecha", "tourney_id"]
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
    ("w_ace", "w_svpt"), ("w_1stIn", "w_svpt"), ("w_1stWon", "w_1stIn"),
    ("w_2ndWon", "w_svpt"), ("w_bpSaved", "w_bpFaced"),
    ("l_ace", "l_svpt"), ("l_1stIn", "l_svpt"), ("l_1stWon", "l_1stIn"),
    ("l_2ndWon", "l_svpt"), ("l_bpSaved", "l_bpFaced"),
]
MAX_PCT_INCONSISTENCIAS = 0.05
COLUMNAS_NULABLES_POR_DISENIO = {
    "winner_seed", "loser_seed", "winner_entry", "loser_entry",
}
AVISO_PCT_NULOS = 0.10


def validar_partidos_consolidados(
    ruta_partidos: str | Path,
    anio_desde: int,
    anio_hasta: int,
) -> str:
    """Quality gate de la tabla partido-nivel antes de crear features."""
    ruta_partidos = Path(ruta_partidos)
    df = pd.read_csv(ruta_partidos, low_memory=False, parse_dates=["fecha"])

    problemas: list[str] = []
    avisos: list[str] = []

    if not df["id_partido"].is_unique:
        problemas.append(
            f"[unicidad] id_partido con {int(df['id_partido'].duplicated().sum())} duplicados"
        )

    for col in COLUMNAS_OBLIGATORIAS:
        nulos = int(df[col].isna().sum())
        if nulos:
            problemas.append(f"[completitud] {col} tiene {nulos} nulos")

    vacias = df.columns[df.isna().all()].tolist()
    if vacias:
        problemas.append(f"[completitud] columnas 100% nulas: {vacias}")

    por_temporada = df.groupby("anio_archivo").size()
    flacas = por_temporada[por_temporada < MIN_PARTIDOS_POR_TEMPORADA]
    if not flacas.empty:
        problemas.append(
            f"[completitud] temporadas con menos de {MIN_PARTIDOS_POR_TEMPORADA} partidos: "
            f"{flacas.to_dict()}"
        )

    if df.shape[1] < 5:
        problemas.append(f"[completitud] muy pocas columnas: {df.shape[1]}")

    pedidas = set(range(anio_desde, anio_hasta + 1))
    presentes = set(df["anio_archivo"].unique())
    faltantes = pedidas - presentes
    if faltantes:
        problemas.append(f"[actualidad] faltan temporadas: {sorted(faltantes)}")

    for col, (minimo, maximo) in RANGOS_PLAUSIBLES.items():
        s = pd.to_numeric(df[col], errors="coerce")
        fuera = int(((s < minimo) | (s > maximo)).sum())
        if fuera:
            problemas.append(
                f"[precision] {col}: {fuera} valores fuera de [{minimo}, {maximo}]"
            )

    for col, dominio in DOMINIOS.items():
        invalidos = df[col].dropna()
        invalidos = invalidos[~invalidos.isin(dominio)]
        if len(invalidos):
            problemas.append(
                f"[precision] {col}: {len(invalidos)} fuera de {sorted(dominio)}"
            )

    for menor, mayor in CRUCES_CONSISTENCIA:
        comparables = df[menor].notna() & df[mayor].notna()
        n = int(comparables.sum())
        if not n:
            continue
        viol = int((df.loc[comparables, menor] > df.loc[comparables, mayor]).sum())
        pct = viol / n * 100
        if pct > MAX_PCT_INCONSISTENCIAS:
            problemas.append(
                f"[consistencia] {menor} <= {mayor}: {viol}/{n} ({pct:.3f}%)"
            )
        elif viol:
            avisos.append(f"{menor} <= {mayor}: {viol}/{n} ({pct:.3f}%)")

    tipos = df.dtypes
    hay_numerica = tipos.apply(pd.api.types.is_numeric_dtype).any()
    hay_fecha = tipos.apply(pd.api.types.is_datetime64_any_dtype).any()
    hay_categorica = tipos.apply(
        lambda t: pd.api.types.is_object_dtype(t)
        or pd.api.types.is_string_dtype(t)
        or isinstance(t, pd.CategoricalDtype)
    ).any()
    if not (hay_numerica and hay_fecha and hay_categorica):
        problemas.append(
            f"[tipos] falta variedad: numerica={hay_numerica}, fecha={hay_fecha}, "
            f"categorica={hay_categorica}"
        )

    nulos_pct = df.isna().mean().sort_values(ascending=False)
    for col, pct in nulos_pct[nulos_pct > AVISO_PCT_NULOS].items():
        if col not in COLUMNAS_NULABLES_POR_DISENIO:
            avisos.append(f"{col}: {pct * 100:.1f}% nulos")

    for aviso in avisos:
        log.warning("Observabilidad Silver: %s", aviso)

    if problemas:
        raise ValueError("Validacion Silver fallida:\n  - " + "\n  - ".join(problemas))

    informe = consolidar.informe_calidad(df)
    config.DIR_PROCESADO.mkdir(parents=True, exist_ok=True)
    informe.to_csv(config.DIR_PROCESADO / "informe_calidad.csv", index=False)

    log.info("Validacion Silver OK: %s filas x %s columnas", len(df), df.shape[1])
    return str(ruta_partidos)


def validar_player_match_long(ruta: str | Path) -> None:
    df = pd.read_csv(
        ruta,
        dtype={"player_id": "string", "opponent_id": "string"},
        low_memory=False,
    )
    problemas = []
    conteo = df.groupby("id_partido").size()
    if not (conteo == 2).all():
        problemas.append("cada id_partido debe tener exactamente dos filas")
    ganadores = df.groupby("id_partido")["won"].sum()
    if not (ganadores == 1).all():
        problemas.append("cada partido debe tener exactamente un won=1")
    if (df["player_id"] == df["opponent_id"]).any():
        problemas.append("hay filas donde player_id == opponent_id")
    if problemas:
        raise ValueError("Validacion player_match_long fallida: " + "; ".join(problemas))


def validar_style_dataset(ruta: str | Path, min_partidos: int) -> None:
    df = pd.read_csv(ruta, dtype={"player_id": "string"}, low_memory=False)
    problemas = []
    if not df["player_id"].is_unique:
        problemas.append("player_id no es unico")
    if (df["matches_with_serve_stats"] < min_partidos).any():
        problemas.append("hay jugadores sin historial minimo de saque")
    if (df["matches_with_return_stats"] < min_partidos).any():
        problemas.append("hay jugadores sin historial minimo de resto")
    if df[STYLE_FEATURES].isna().any().any():
        problemas.append("hay nulos en features centrales de estilo")
    fuera = ((df[STYLE_FEATURES] < 0) | (df[STYLE_FEATURES] > 1)).any().any()
    if fuera:
        problemas.append("hay tasas de estilo fuera de [0, 1]")
    if problemas:
        raise ValueError("Validacion player_style_dataset fallida: " + "; ".join(problemas))


def validar_matchups_modelo(ruta: str | Path, min_historial: int) -> None:
    df = pd.read_csv(
        ruta,
        dtype={"a_player_id": "string", "b_player_id": "string"},
        low_memory=False,
    )
    problemas = []
    if not df["id_partido"].is_unique:
        problemas.append("id_partido no es unico")
    if not df["target_a_wins"].isin([0, 1]).all():
        problemas.append("target_a_wins contiene valores distintos de 0/1")
    if (df["a_player_id"] >= df["b_player_id"]).any():
        problemas.append("A/B no respeta el orden neutral por player_id")
    for c in [
        "a_serve_matches_before", "b_serve_matches_before",
        "a_return_matches_before", "b_return_matches_before",
    ]:
        if (df[c] < min_historial).any():
            problemas.append(f"{c} no respeta el historial minimo")
    if df[["a_player_rank", "b_player_rank"]].isna().any().any():
        problemas.append("hay rankings nulos en la muestra de modelado")
    prohibidas = [c for c in df.columns if c.startswith("winner_") or c.startswith("loser_")]
    if prohibidas:
        problemas.append(f"hay columnas con leakage winner/loser: {prohibidas}")
    if problemas:
        raise ValueError("Validacion matchups_modelo fallida: " + "; ".join(problemas))

    proporcion = df["target_a_wins"].mean()
    log.info("Target A gana en %.2f%% de la muestra", proporcion * 100)
