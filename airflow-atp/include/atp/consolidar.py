"""Paso 2 del pipeline: consolidacion, tipado y control de calidad."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

COLUMNAS_NUMERICAS = [
    "draw_size", "match_num", "best_of", "minutes",
    "winner_seed", "winner_ht", "winner_age", "winner_rank", "winner_rank_points",
    "loser_seed", "loser_ht", "loser_age", "loser_rank", "loser_rank_points",
] + [f"{lado}_{stat}" for lado in ("w", "l") for stat in config.STATS_PARTIDO]


def consolidar(rutas: list[Path]) -> pd.DataFrame:
    """Une los CSV anuales en una unica tabla partido-nivel, tipada y ordenada."""
    print("[2/4] Consolidando temporadas")

    marcos = []
    for ruta in sorted(rutas):
        df = pd.read_csv(ruta, dtype=str, encoding="utf-8", encoding_errors="replace")
        df["anio_archivo"] = int(ruta.stem)
        marcos.append(df)

    partidos = pd.concat(marcos, ignore_index=True, sort=False)
    filas_crudas = len(partidos)

    # --- Tipado ----------------------------------------------------------
    for col in COLUMNAS_NUMERICAS:
        if col in partidos.columns:
            partidos[col] = pd.to_numeric(partidos[col], errors="coerce")

    partidos["fecha"] = pd.to_datetime(
        partidos["tourney_date"], format="%Y%m%d", errors="coerce"
    )
    partidos["anio"] = partidos["fecha"].dt.year

    partidos["orden_ronda"] = (
        partidos["round"].map(config.ORDEN_RONDA).fillna(config.ORDEN_RONDA_DEFECTO)
    )

    # --- Limpieza --------------------------------------------------------
    # Sin id de alguno de los dos jugadores el partido no sirve para nada.
    sin_id = partidos["winner_id"].isna() | partidos["loser_id"].isna()
    sin_fecha = partidos["fecha"].isna()
    partidos = partidos[~(sin_id | sin_fecha)].copy()

    antes_dedupe = len(partidos)
    partidos = partidos.drop_duplicates(subset=["tourney_id", "match_num"], keep="first")
    duplicados = antes_dedupe - len(partidos)

    # Orden cronologico real: fecha de torneo, luego ronda. Dentro de un mismo
    # torneo todas las filas comparten tourney_date, asi que sin `orden_ronda`
    # una final podria quedar "antes" de una primera ronda y contaminar el
    # historial que construimos despues.
    partidos = partidos.sort_values(
        ["fecha", "tourney_id", "orden_ronda", "match_num"], kind="mergesort"
    ).reset_index(drop=True)

    # Identificador unico de partido. Ojo: una minoria de filas viene sin
    # `match_num` (9 sobre ~11.500 en 2022-2025), y concatenar contra un nulo
    # produce un id nulo que despues rompe el armado del dataset A/B. Para
    # esas filas usamos la posicion dentro del torneo como respaldo.
    numero = partidos["match_num"].astype("Int64").astype(str)
    respaldo = "s" + partidos.groupby("tourney_id").cumcount().astype(str)
    numero = numero.where(partidos["match_num"].notna(), respaldo)
    partidos["id_partido"] = partidos["tourney_id"].astype(str) + "-" + numero

    # Garantia final de unicidad: si algo se escapo, desambiguamos en vez de
    # perder partidos silenciosamente mas adelante.
    repetidos = partidos["id_partido"].duplicated(keep=False)
    if repetidos.any():
        sufijo = partidos.groupby("id_partido").cumcount().astype(str)
        partidos.loc[repetidos, "id_partido"] += "-r" + sufijo[repetidos]
        print(f"      ids desambiguados     {int(repetidos.sum()):>8,}")

    print(f"      filas crudas          {filas_crudas:>8,}")
    print(f"      descartadas (id/fecha){filas_crudas - antes_dedupe:>8,}")
    print(f"      duplicados eliminados {duplicados:>8,}")
    print(f"      partidos consolidados {len(partidos):>8,}")
    print(f"      rango                 {partidos['fecha'].min():%Y-%m-%d} a {partidos['fecha'].max():%Y-%m-%d}")
    return partidos


def informe_calidad(partidos: pd.DataFrame) -> pd.DataFrame:
    """Porcentaje de nulos por columna clave. Insumo directo de la Entrega 1."""
    columnas = [
        "surface", "round", "best_of", "score", "minutes",
        "winner_rank", "loser_rank", "winner_ht", "loser_ht",
        "w_bpFaced", "w_bpSaved", "l_bpFaced", "l_bpSaved", "w_svpt", "l_svpt",
    ]
    columnas = [c for c in columnas if c in partidos.columns]

    informe = pd.DataFrame({
        "columna": columnas,
        "nulos": [int(partidos[c].isna().sum()) for c in columnas],
    })
    informe["pct_nulos"] = (informe["nulos"] / len(partidos) * 100).round(2)

    print("\n      Nulos por columna clave (top 6):")
    for _, fila in informe.sort_values("pct_nulos", ascending=False).head(6).iterrows():
        print(f"        {fila['columna']:<16} {fila['pct_nulos']:>6.2f} %")

    # Las stats de saque/resto no existen para buena parte de los partidos
    # viejos. Es el dato mas importante del informe: define desde que anio
    # conviene entrenar.
    if "w_svpt" in partidos.columns:
        cobertura = (
            partidos.assign(tiene=partidos["w_svpt"].notna())
            .groupby("anio")["tiene"].mean()
            .mul(100).round(1)
        )
        primeros = cobertura[cobertura > 80]
        if not primeros.empty:
            print(f"        cobertura de stats > 80 % desde {primeros.index.min()}")

    print()
    return informe


def cargar_bios(ruta: Path | None) -> pd.DataFrame | None:
    """Tabla de biografias de jugadores, para enriquecer features."""
    if ruta is None or not ruta.exists():
        return None
    bios = pd.read_csv(ruta, dtype=str, encoding="utf-8", encoding_errors="replace")
    for col in ("weight", "height", "turnedpro"):
        if col in bios.columns:
            bios[col] = pd.to_numeric(bios[col], errors="coerce")
    return bios
