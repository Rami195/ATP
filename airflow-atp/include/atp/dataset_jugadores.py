"""Construccion del dataset de jugadores ATP.

Agrega las estadisticas de cada jugador a lo largo de todos sus partidos
validos (excluyendo Carpet), separadas en totales y por superficie.
Incluye totales, tasas comparables, cobertura, saque, devolucion y titulos.

El resultado es un unico CSV con una fila por jugador, guardado en la capa
plata junto al consolidado de partidos.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)

# ---- Mapeo de categorias de torneo para titulos -------------------------
# Solo se cuentan titulos en estas categorias. Las demas (D=Davis Cup,
# A=team events, O=Olimpiadas, F=Tour Finals) quedan fuera.
CATEGORIAS_TITULO = {
    "250": "250",
    "500": "500",
    "M": "1000",
    "G": "grand-slam",
}

# Stats de saque/resto que se agregan por jugador. Coinciden con
# config.STATS_PARTIDO pero renombradas al esquema unificado.
STATS_SAQUE = [
    ("ace", "aces"),
    ("df", "dobles-faltas"),
    ("svpt", "puntos-saque"),
    ("1stIn", "primeros-saques-dentro"),
    ("1stWon", "primeros-saques-ganados"),
    ("2ndWon", "segundos-saques-ganados"),
    ("SvGms", "games-saque"),
    ("bpSaved", "break-points-salvados"),
    ("bpFaced", "break-points-enfrentados"),
]

# Metricas de devolucion derivadas de las estadisticas de saque del rival.
STATS_RESTO = [
    ("puntos_resto_jugados", "puntos-resto-jugados"),
    ("puntos_resto_ganados", "puntos-resto-ganados"),
    ("break_points_oportunidades", "break-points-oportunidades"),
    ("break_points_convertidos", "break-points-convertidos"),
]

SUPERFICIES_VALIDAS = ("Hard", "Clay", "Grass")

# Mapeo de superficie de la fuente a sufijo en espanol para nombres de columnas
MAPEO_SUPERFICIES = {
    "Hard": "cemento",
    "Clay": "clay",
    "Grass": "grass",
}
SUFIJOS_SUPERFICIE = ("cemento", "clay", "grass")


# ---------------------------------------------------------------------------
# Funciones de carga y limpieza
# ---------------------------------------------------------------------------

def cargar_datos_consolidados(ruta: str | Path) -> pd.DataFrame:
    """Lee el CSV consolidado de partidos."""
    df = pd.read_csv(ruta, low_memory=False)
    log.info("Consolidado cargado: %s filas x %s columnas", len(df), df.shape[1])
    return df


def normalizar_superficies(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza la columna `surface` a Title Case y excluye Carpet.

    Devuelve un DataFrame sin las filas de Carpet (case-insensitive) y
    sin las filas cuya superficie sea nula o no reconocida.
    """
    df = df.copy()
    antes = len(df)

    # Excluir filas sin superficie informada
    df = df[df["surface"].notna()].copy()
    sin_superficie = antes - len(df)

    df["surface"] = df["surface"].astype(str).str.strip().str.title()
    antes2 = len(df)
    df = df[df["surface"] != "Carpet"].copy()
    carpet_excluidos = antes2 - len(df)

    log.info(
        "Superficies: %d sin superficie descartados, %d Carpet descartados",
        sin_superficie, carpet_excluidos,
    )
    return df


def parsear_score(score: object) -> tuple[float, float, float, float]:
    """Extrae sets y games ganados/perdidos del score.

    Devuelve (sets_w, sets_l, games_w, games_l).
    Para W/O o scores no parseables devuelve (NaN, NaN, NaN, NaN).
    """
    if pd.isna(score):
        return float("nan"), float("nan"), float("nan"), float("nan")
    pares = re.findall(r"(\d+)-(\d+)", str(score))
    if not pares:
        return float("nan"), float("nan"), float("nan"), float("nan")
    sets_w = sum(1 for w, l in pares if int(w) > int(l))
    sets_l = sum(1 for w, l in pares if int(l) > int(w))
    games_w = sum(int(w) for w, l in pares)
    games_l = sum(int(l) for w, l in pares)
    return float(sets_w), float(sets_l), float(games_w), float(games_l)


def _agregar_sets_games(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas de sets y games parseados del score."""
    parsed = df["score"].apply(parsear_score)
    df = df.copy()
    df["w_sets"] = parsed.apply(lambda t: t[0])
    df["l_sets"] = parsed.apply(lambda t: t[1])
    df["w_games"] = parsed.apply(lambda t: t[2])
    df["l_games"] = parsed.apply(lambda t: t[3])
    return df


def _calcular_estadisticas_resto(df: pd.DataFrame, prefijo_rival: str) -> pd.DataFrame:
    """Calcula puntos al resto y break points usando el bloque del rival."""
    requeridas = [
        f"{prefijo_rival}_svpt",
        f"{prefijo_rival}_1stWon",
        f"{prefijo_rival}_2ndWon",
        f"{prefijo_rival}_bpSaved",
        f"{prefijo_rival}_bpFaced",
    ]
    numericas = {}
    for columna in requeridas:
        if columna in df.columns:
            numericas[columna] = pd.to_numeric(df[columna], errors="coerce")
        else:
            numericas[columna] = pd.Series(float("nan"), index=df.index)

    svpt = numericas[f"{prefijo_rival}_svpt"]
    first_won = numericas[f"{prefijo_rival}_1stWon"]
    second_won = numericas[f"{prefijo_rival}_2ndWon"]
    bp_saved = numericas[f"{prefijo_rival}_bpSaved"]
    bp_faced = numericas[f"{prefijo_rival}_bpFaced"]

    completos = pd.concat(numericas.values(), axis=1).notna().all(axis=1)
    no_negativos = pd.concat(numericas.values(), axis=1).ge(0).all(axis=1)
    consistentes = (
        completos
        & no_negativos
        & ((first_won + second_won) <= svpt)
        & (bp_saved <= bp_faced)
    )

    resultado = pd.DataFrame(index=df.index)
    resultado["partidos_validos_resto"] = consistentes.astype(int)
    resultado["puntos_resto_jugados"] = svpt.where(consistentes)
    resultado["puntos_resto_ganados"] = (svpt - first_won - second_won).where(consistentes)
    resultado["break_points_oportunidades"] = bp_faced.where(consistentes)
    resultado["break_points_convertidos"] = (bp_faced - bp_saved).where(consistentes)
    return resultado


# ---------------------------------------------------------------------------
# Preparacion de participaciones
# ---------------------------------------------------------------------------

def preparar_participaciones_ganador(df: pd.DataFrame) -> pd.DataFrame:
    """Crea la vista del ganador con columnas unificadas.

    Verifica que el bloque completo de 9 estadisticas de servicio este
    presente y sea valido (>= 0). Si alguna estadistica falta o es invalida,
    las estadisticas de saque se establecen en NaN y partidos_validos = 0.
    """
    renombre = {
        "winner_id": "id_jugador",
        "minutes": "minutos",
        "w_sets": "sets_ganados",
        "l_sets": "sets_perdidos",
        "w_games": "games_ganados",
        "l_games": "games_perdidos",
    }
    for stat_orig, _ in STATS_SAQUE:
        renombre[f"w_{stat_orig}"] = stat_orig

    cols_stats_w = [f"w_{stat_orig}" for stat_orig, _ in STATS_SAQUE]
    columnas_presentes = [c for c in cols_stats_w if c in df.columns]

    if len(columnas_presentes) == len(cols_stats_w):
        stats_completas = df[cols_stats_w].notna().all(axis=1)
        for c in cols_stats_w:
            val_num = pd.to_numeric(df[c], errors="coerce")
            stats_completas = stats_completas & val_num.notna() & (val_num >= 0)
    else:
        stats_completas = pd.Series(False, index=df.index)

    df_temp = df.copy()
    for col in list(renombre.keys()):
        if col not in df_temp.columns:
            df_temp[col] = float("nan")

    columnas = list(renombre.keys()) + ["surface", "tourney_id", "round", "tourney_level"]
    out = df_temp[columnas].rename(columns=renombre).copy()
    out["victoria"] = 1
    out["partidos_validos"] = stats_completas.astype(int)

    # Convertir estadisticas de saque a numerico exacto conservando ceros reales
    stats_cols = [stat_orig for stat_orig, _ in STATS_SAQUE]
    for sc in stats_cols:
        out[sc] = pd.to_numeric(out[sc], errors="coerce")

    # Excluir de las estadisticas de saque los partidos con bloque incompleto
    out.loc[~stats_completas, stats_cols] = float("nan")

    resto = _calcular_estadisticas_resto(df_temp, "l")
    for columna in resto.columns:
        out[columna] = resto[columna].to_numpy()

    return out


def preparar_participaciones_perdedor(df: pd.DataFrame) -> pd.DataFrame:
    """Crea la vista del perdedor con columnas unificadas.

    Verifica que el bloque completo de 9 estadisticas de servicio este
    presente y sea valido (>= 0). Si alguna estadistica falta o es invalida,
    las estadisticas de saque se establecen en NaN y partidos_validos = 0.
    """
    renombre = {
        "loser_id": "id_jugador",
        "minutes": "minutos",
        "l_sets": "sets_ganados",
        "w_sets": "sets_perdidos",
        "l_games": "games_ganados",
        "w_games": "games_perdidos",
    }
    for stat_orig, _ in STATS_SAQUE:
        renombre[f"l_{stat_orig}"] = stat_orig

    cols_stats_l = [f"l_{stat_orig}" for stat_orig, _ in STATS_SAQUE]
    columnas_presentes = [c for c in cols_stats_l if c in df.columns]

    if len(columnas_presentes) == len(cols_stats_l):
        stats_completas = df[cols_stats_l].notna().all(axis=1)
        for c in cols_stats_l:
            val_num = pd.to_numeric(df[c], errors="coerce")
            stats_completas = stats_completas & val_num.notna() & (val_num >= 0)
    else:
        stats_completas = pd.Series(False, index=df.index)

    df_temp = df.copy()
    for col in list(renombre.keys()):
        if col not in df_temp.columns:
            df_temp[col] = float("nan")

    columnas = list(renombre.keys()) + ["surface", "tourney_id", "round", "tourney_level"]
    out = df_temp[columnas].rename(columns=renombre).copy()
    out["victoria"] = 0
    out["partidos_validos"] = stats_completas.astype(int)

    # Convertir estadisticas de saque a numerico exacto conservando ceros reales
    stats_cols = [stat_orig for stat_orig, _ in STATS_SAQUE]
    for sc in stats_cols:
        out[sc] = pd.to_numeric(out[sc], errors="coerce")

    # Excluir de las estadisticas de saque los partidos con bloque incompleto
    out.loc[~stats_completas, stats_cols] = float("nan")

    resto = _calcular_estadisticas_resto(df_temp, "w")
    for columna in resto.columns:
        out[columna] = resto[columna].to_numpy()

    return out


def unificar_participaciones(df: pd.DataFrame) -> pd.DataFrame:
    """Concatena las vistas de ganador y perdedor."""
    ganadores = preparar_participaciones_ganador(df)
    perdedores = preparar_participaciones_perdedor(df)
    participaciones = pd.concat([ganadores, perdedores], ignore_index=True)
    validos = int(participaciones["partidos_validos"].sum())
    log.info(
        "Participaciones unificadas: %d filas (%d con estadisticas de servicio completas)",
        len(participaciones), validos,
    )
    return participaciones


# ---------------------------------------------------------------------------
# Estadisticas totales
# ---------------------------------------------------------------------------

def _columnas_agregables() -> list[str]:
    """Devuelve las columnas numericas que se suman por jugador."""
    cols = ["victoria", "partidos_validos", "partidos_validos_resto", "sets_ganados", "sets_perdidos",
            "games_ganados", "games_perdidos", "minutos"]
    for stat_orig, _ in STATS_SAQUE:
        cols.append(stat_orig)
    for stat_orig, _ in STATS_RESTO:
        cols.append(stat_orig)
    return cols


def _renombrar_stats_espanol(df: pd.DataFrame, sufijo: str) -> pd.DataFrame:
    """Renombra columnas internas al formato en espanol con guion medio."""
    renombre = {
        "victoria": f"victorias-{sufijo}",
        "partidos_validos": f"partidos-validos-{sufijo}",
        "partidos_validos_resto": f"partidos-validos-resto-{sufijo}",
        "sets_ganados": f"sets-ganados-{sufijo}",
        "sets_perdidos": f"sets-perdidos-{sufijo}",
        "games_ganados": f"games-ganados-{sufijo}",
        "games_perdidos": f"games-perdidos-{sufijo}",
        "minutos": f"minutos-{sufijo}",
    }
    for stat_orig, stat_es in STATS_SAQUE:
        renombre[stat_orig] = f"{stat_es}-{sufijo}"
    for stat_orig, stat_es in STATS_RESTO:
        renombre[stat_orig] = f"{stat_es}-{sufijo}"
    return df.rename(columns=renombre)


def calcular_estadisticas_totales(participaciones: pd.DataFrame) -> pd.DataFrame:
    """Calcula estadisticas acumuladas sobre todos los partidos validos."""
    cols_conteo = ["victoria", "partidos_validos", "partidos_validos_resto", "sets_ganados", "sets_perdidos",
                   "games_ganados", "games_perdidos", "minutos"]
    cols_metricas = (
        [stat_orig for stat_orig, _ in STATS_SAQUE]
        + [stat_orig for stat_orig, _ in STATS_RESTO]
    )

    totales_conteo = participaciones.groupby("id_jugador")[cols_conteo].sum(min_count=0)
    # min_count=1 asegura que si un jugador tiene 0 observaciones de saque, el total sea NaN (no 0.0)
    totales_metricas = participaciones.groupby("id_jugador")[cols_metricas].sum(min_count=1)

    totales = totales_conteo.join(totales_metricas)
    totales = _renombrar_stats_espanol(totales, "totales")

    # Partidos totales y derrotas
    conteo = participaciones.groupby("id_jugador").size().rename("partidos-totales")
    totales = totales.join(conteo)
    totales["derrotas-totales"] = totales["partidos-totales"] - totales["victorias-totales"]

    return totales


def calcular_estadisticas_por_superficie(participaciones: pd.DataFrame) -> pd.DataFrame:
    """Calcula estadisticas acumuladas por superficie."""
    cols_conteo = ["victoria", "partidos_validos", "partidos_validos_resto", "sets_ganados", "sets_perdidos",
                   "games_ganados", "games_perdidos", "minutos"]
    cols_metricas = (
        [stat_orig for stat_orig, _ in STATS_SAQUE]
        + [stat_orig for stat_orig, _ in STATS_RESTO]
    )

    superficies_presentes = sorted(
        s for s in participaciones["surface"].unique() if s in SUPERFICIES_VALIDAS
    )

    partes = []
    for superficie in superficies_presentes:
        sub = participaciones[participaciones["surface"] == superficie]
        stats_conteo = sub.groupby("id_jugador")[cols_conteo].sum(min_count=0)
        stats_metricas = sub.groupby("id_jugador")[cols_metricas].sum(min_count=1)
        stats = stats_conteo.join(stats_metricas)

        suf = MAPEO_SUPERFICIES.get(superficie, superficie.lower())
        stats = _renombrar_stats_espanol(stats, suf)

        conteo = sub.groupby("id_jugador").size().rename(f"partidos-{suf}")
        stats = stats.join(conteo)
        stats[f"derrotas-{suf}"] = stats[f"partidos-{suf}"] - stats[f"victorias-{suf}"]

        partes.append(stats)

    if not partes:
        return pd.DataFrame()

    resultado = partes[0]
    for parte in partes[1:]:
        resultado = resultado.join(parte, how="outer")

    return resultado


def _proporcion_segura(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Divide conteos consistentes y deja NaN cuando la tasa no esta definida."""
    n = pd.to_numeric(numerador, errors="coerce")
    d = pd.to_numeric(denominador, errors="coerce")
    validos = n.notna() & d.notna() & (n >= 0) & (d > 0) & (n <= d)
    return (n / d).where(validos)


def agregar_tasas_y_cobertura(stats: pd.DataFrame) -> pd.DataFrame:
    """Agrega tasas reutilizables y cobertura general y por superficie."""
    stats = stats.copy()
    for sufijo in ("totales", *SUFIJOS_SUPERFICIE):
        partidos = f"partidos-{sufijo}"
        if partidos not in stats.columns:
            continue

        formulas = {
            f"tasa-victorias-{sufijo}": (
                stats.get(f"victorias-{sufijo}"), stats[partidos]
            ),
            f"tasa-aces-{sufijo}": (
                stats.get(f"aces-{sufijo}"), stats.get(f"puntos-saque-{sufijo}")
            ),
            f"tasa-dobles-faltas-{sufijo}": (
                stats.get(f"dobles-faltas-{sufijo}"), stats.get(f"puntos-saque-{sufijo}")
            ),
            f"tasa-primer-saque-dentro-{sufijo}": (
                stats.get(f"primeros-saques-dentro-{sufijo}"), stats.get(f"puntos-saque-{sufijo}")
            ),
            f"efectividad-primer-saque-{sufijo}": (
                stats.get(f"primeros-saques-ganados-{sufijo}"), stats.get(f"primeros-saques-dentro-{sufijo}")
            ),
            f"tasa-break-points-salvados-{sufijo}": (
                stats.get(f"break-points-salvados-{sufijo}"), stats.get(f"break-points-enfrentados-{sufijo}")
            ),
            f"tasa-puntos-ganados-resto-{sufijo}": (
                stats.get(f"puntos-resto-ganados-{sufijo}"), stats.get(f"puntos-resto-jugados-{sufijo}")
            ),
            f"tasa-break-points-convertidos-{sufijo}": (
                stats.get(f"break-points-convertidos-{sufijo}"), stats.get(f"break-points-oportunidades-{sufijo}")
            ),
            f"cobertura-saque-{sufijo}": (
                stats.get(f"partidos-validos-{sufijo}"), stats[partidos]
            ),
            f"cobertura-resto-{sufijo}": (
                stats.get(f"partidos-validos-resto-{sufijo}"), stats[partidos]
            ),
        }

        puntos_saque = stats.get(f"puntos-saque-{sufijo}")
        primeros_dentro = stats.get(f"primeros-saques-dentro-{sufijo}")
        if puntos_saque is not None and primeros_dentro is not None:
            formulas[f"efectividad-segundo-saque-{sufijo}"] = (
                stats.get(f"segundos-saques-ganados-{sufijo}"),
                puntos_saque - primeros_dentro,
            )

        for nombre, (numerador, denominador) in formulas.items():
            if numerador is not None and denominador is not None:
                stats[nombre] = _proporcion_segura(numerador, denominador)

    return stats


# ---------------------------------------------------------------------------
# Titulos
# ---------------------------------------------------------------------------

def calcular_titulos_por_superficie(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta titulos ganados por categoria y superficie.

    Un titulo = ganar la final (round == 'F') de un torneo cuyo
    tourney_level esta en CATEGORIAS_TITULO.
    """
    finales = df[
        (df["round"] == "F")
        & (df["tourney_level"].isin(CATEGORIAS_TITULO))
        & (df["surface"].isin(SUPERFICIES_VALIDAS))
    ].copy()

    # Desduplicar: un titulo por torneo (por si hubiera registros duplicados)
    finales = finales.drop_duplicates(subset=["tourney_id", "winner_id"])

    finales["categoria"] = finales["tourney_level"].map(CATEGORIAS_TITULO)
    finales["suf_superficie"] = finales["surface"].map(MAPEO_SUPERFICIES).fillna(finales["surface"].str.lower())

    titulos = (
        finales
        .groupby(["winner_id", "categoria", "suf_superficie"])
        .size()
        .reset_index(name="cantidad")
    )

    # Pivotear a columnas: titulos-250-cemento, titulos-grand-slam-clay, ...
    titulos["col"] = "titulos-" + titulos["categoria"] + "-" + titulos["suf_superficie"]
    pivot = titulos.pivot_table(
        index="winner_id", columns="col", values="cantidad", fill_value=0
    )
    pivot.index.name = "id_jugador"

    # Asegurar que existan todas las combinaciones esperadas
    for cat_codigo, cat_nombre in CATEGORIAS_TITULO.items():
        for superficie in SUPERFICIES_VALIDAS:
            suf = MAPEO_SUPERFICIES[superficie]
            col = f"titulos-{cat_nombre}-{suf}"
            if col not in pivot.columns:
                pivot[col] = 0

    return pivot


# ---------------------------------------------------------------------------
# Informacion personal
# ---------------------------------------------------------------------------

def cargar_informacion_jugadores(ruta_bios: Path) -> pd.DataFrame:
    """Lee y limpia la tabla de biografias de jugadores.

    Mapea los nombres de columnas al formato en espanol con guion medio.
    """
    bios = pd.read_csv(ruta_bios, dtype=str, encoding="utf-8", encoding_errors="replace")

    # Desduplicar: la tabla de bios tiene IDs repetidos (28 casos)
    duplicados = int(bios["id"].duplicated().sum())
    if duplicados:
        log.warning("Bios con %d IDs duplicados, se conserva la primera aparicion", duplicados)
        bios = bios.drop_duplicates(subset=["id"], keep="first")

    # Limpiar height: valores '0' -> NaN, convertir a numerico
    if "height" in bios.columns:
        bios["height"] = pd.to_numeric(bios["height"], errors="coerce")
        bios.loc[bios["height"] == 0, "height"] = float("nan")

    # Limpiar weight: solo valores numericos en rango plausible (40-200 kg)
    if "weight" in bios.columns:
        bios["weight"] = pd.to_numeric(bios["weight"], errors="coerce")
        bios.loc[
            (bios["weight"] < 40) | (bios["weight"] > 200), "weight"
        ] = float("nan")

    # turnedpro: valores '0' -> NaN
    if "turnedpro" in bios.columns:
        bios["turnedpro"] = pd.to_numeric(bios["turnedpro"], errors="coerce")
        bios.loc[bios["turnedpro"] == 0, "turnedpro"] = float("nan")

    # Formatear birthdate
    if "birthdate" in bios.columns:
        bios["birthdate"] = pd.to_datetime(
            bios["birthdate"], format="%Y%m%d", errors="coerce"
        )

    renombre = {
        "id": "id-jugador",
        "player": "nombre-jugador",
        "birthdate": "fecha-nacimiento",
        "height": "altura-cm",
        "weight": "peso-kg",
        "hand": "mano-dominante",
        "backhand": "tipo-reves",
        "turnedpro": "año-profesional",
        "ioc": "pais",
    }

    columnas_disponibles = [c for c in renombre if c in bios.columns]
    bios = bios[columnas_disponibles].rename(
        columns={c: renombre[c] for c in columnas_disponibles}
    )

    log.info("Bios cargadas: %d jugadores", len(bios))
    return bios


# ---------------------------------------------------------------------------
# Filtrado y union
# ---------------------------------------------------------------------------

def filtrar_minimo_partidos(
    stats: pd.DataFrame,
    minimo: int = 3,
) -> pd.DataFrame:
    """Excluye jugadores con menos de `minimo` partidos totales o sin estadisticas protegidas validas."""
    antes = len(stats)
    cond_minimo = stats["partidos-totales"] >= minimo

    if "partidos-validos-totales" in stats.columns:
        cond_stats = stats["partidos-validos-totales"] > 0
    else:
        cols_saque = [f"{s[1]}-totales" for s in STATS_SAQUE if f"{s[1]}-totales" in stats.columns]
        cond_stats = stats[cols_saque].notna().any(axis=1) if cols_saque else pd.Series(True, index=stats.index)

    stats = stats[cond_minimo & cond_stats].copy()
    excluidos = antes - len(stats)
    log.info(
        "Filtro de jugadores (minimo %d partidos y con estadisticas validas): %d excluidos, %d incluidos",
        minimo, excluidos, len(stats),
    )
    return stats


def unir_informacion_jugadores(
    stats: pd.DataFrame,
    bios: pd.DataFrame,
) -> pd.DataFrame:
    """Hace left join de las estadisticas con la informacion personal."""
    # stats tiene id_jugador como indice; bios tiene id-jugador como columna
    stats = stats.reset_index()
    stats.rename(columns={"id_jugador": "id-jugador"}, inplace=True)

    resultado = bios.merge(stats, on="id-jugador", how="right")
    log.info("Union con bios: %d filas", len(resultado))
    return resultado


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

def validar_dataset(df: pd.DataFrame) -> None:
    """Ejecuta las 12 validaciones obligatorias. Lanza ValueError si falla."""
    problemas: list[str] = []

    # 1. Una fila por jugador
    if df["id-jugador"].duplicated().any():
        n = int(df["id-jugador"].duplicated().sum())
        problemas.append(f"[unicidad] {n} id-jugador duplicados")

    # 2. id-jugador unico (equivalente al anterior, por claridad)
    if not df["id-jugador"].is_unique:
        if "[unicidad]" not in str(problemas):
            problemas.append("[unicidad] id-jugador no es unico")

    # 3. No hay jugadores con menos de 3 partidos
    bajo_minimo = df[df["partidos-totales"] < 3]
    if len(bajo_minimo):
        problemas.append(
            f"[filtro] {len(bajo_minimo)} jugadores con menos de 3 partidos"
        )

    # 3b. No hay jugadores sin estadisticas protegidas validas
    if "partidos-validos-totales" in df.columns:
        sin_stats = df[df["partidos-validos-totales"] <= 0]
        if len(sin_stats):
            problemas.append(
                f"[stats_protegidas] {len(sin_stats)} jugadores sin estadisticas de saque validas"
            )

    # 4. No hay estadisticas de Carpet
    cols_carpet = [c for c in df.columns if "carpet" in c.lower()]
    if cols_carpet:
        problemas.append(f"[carpet] columnas de Carpet encontradas: {cols_carpet}")

    # 5. Los nombres no usan variantes ambiguas de "porcentaje"; las proporciones
    # canonicas se identifican como tasa, efectividad o cobertura.
    cols_pct = [
        c for c in df.columns
        if any(p in c.lower() for p in ("porcentaje", "pct", "percent", "ratio"))
    ]
    if cols_pct:
        problemas.append(f"[porcentajes] columnas de porcentaje: {cols_pct}")

    # 6. Nombres en espanol (heuristico: verificar que no haya columnas tipicas en ingles)
    cols_ingles = [
        c for c in df.columns
        if c in ("matches", "wins", "losses", "aces", "first_serve", "player_id",
                 "player_name", "birth_date", "height", "weight", "country")
    ]
    if cols_ingles:
        problemas.append(f"[idioma] columnas en ingles: {cols_ingles}")

    # 7. Sin espacios en nombres de columnas
    cols_espacios = [c for c in df.columns if " " in c]
    if cols_espacios:
        problemas.append(f"[espacios] columnas con espacios: {cols_espacios}")

    # 8. Columnas de titulos presentes
    titulos_esperados = []
    for cat in CATEGORIAS_TITULO.values():
        for suf in SUFIJOS_SUPERFICIE:
            titulos_esperados.append(f"titulos-{cat}-{suf}")
    faltantes = [t for t in titulos_esperados if t not in df.columns]
    if faltantes:
        problemas.append(f"[titulos] columnas de titulos faltantes: {faltantes}")

    # 9. Titulos no negativos
    for col in titulos_esperados:
        if col in df.columns and (df[col] < 0).any():
            problemas.append(f"[titulos] valores negativos en {col}")

    # 10. Totales aditivos consistentes con suma de superficies
    metricas_aditivas = [
        "partidos", "victorias", "derrotas", "partidos-validos",
        "partidos-validos-resto", "sets-ganados", "sets-perdidos",
        "games-ganados", "games-perdidos", "minutos",
        *[nombre for _, nombre in STATS_SAQUE],
        *[nombre for _, nombre in STATS_RESTO],
    ]
    for metrica in metricas_aditivas:
        col_total = f"{metrica}-totales"
        cols_sup = [f"{metrica}-{s}" for s in SUFIJOS_SUPERFICIE]
        if col_total in df.columns and all(c in df.columns for c in cols_sup):
            suma = df[cols_sup].fillna(0).sum(axis=1)
            diff = (df[col_total] - suma).abs()
            inconsistentes = int((diff > 0.5).sum())
            if inconsistentes:
                problemas.append(
                    f"[consistencia] {col_total} != suma de superficies "
                    f"en {inconsistentes} jugadores"
                )

    # 11. Tasas, efectividades y coberturas dentro de [0, 1]
    columnas_proporcion = [
        c for c in df.columns
        if c.startswith(("tasa-", "efectividad-", "cobertura-"))
    ]
    for col in columnas_proporcion:
        observados = pd.to_numeric(df[col], errors="coerce").dropna()
        fuera_de_rango = int((~observados.between(0, 1, inclusive="both")).sum())
        if fuera_de_rango:
            problemas.append(
                f"[tasas] {fuera_de_rango} valores fuera de [0, 1] en {col}"
            )

    # 12. Sin filas duplicadas
    duplicadas = df.duplicated().sum()
    if duplicadas:
        problemas.append(f"[duplicados] {duplicadas} filas completamente duplicadas")

    if problemas:
        raise ValueError(
            "Validacion del dataset de jugadores fallida:\n  - "
            + "\n  - ".join(problemas)
        )

    log.info("Validacion del dataset de jugadores OK: %d filas, %d columnas",
             len(df), df.shape[1])


# ---------------------------------------------------------------------------
# Guardar
# ---------------------------------------------------------------------------

def guardar_dataset(df: pd.DataFrame, destino: Path) -> Path:
    """Escribe el dataset final en CSV."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False)
    log.info("Dataset de jugadores guardado: %s (%d filas)", destino, len(df))
    return destino


def informe_calidad_jugadores(df: pd.DataFrame) -> pd.DataFrame:
    """Porcentaje de nulos para todas las columnas del dataset de jugadores.

    Complementa ``consolidar.informe_calidad`` (que opera sobre partidos)
    con un reporte exhaustivo para el dataset agregado por jugador.
    """
    columnas = list(df.columns)

    informe = pd.DataFrame({
        "columna": columnas,
        "nulos": [int(df[c].isna().sum()) for c in columnas],
    })
    informe["pct_nulos"] = (informe["nulos"] / len(df) * 100).round(2) if len(df) > 0 else 0.0

    print(f"\n      Nulos por columna — dataset jugadores (total {len(columnas)} columnas):")
    for _, fila in informe.sort_values("pct_nulos", ascending=False).head(15).iterrows():
        print(f"        {fila['columna']:<35} {fila['nulos']:>6} ({fila['pct_nulos']:>6.2f} %)")
    print()

    return informe


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def build_player_dataset(ruta_consolidado: str | Path) -> str:
    """Construye el dataset de jugadores y lo guarda en la capa plata.

    Parametros
    ----------
    ruta_consolidado : ruta al CSV consolidado de partidos (salida de
        la tarea ``consolidate``).

    Devuelve
    --------
    str : ruta absoluta del CSV de jugadores generado.
    """
    # 1. Cargar
    df = cargar_datos_consolidados(ruta_consolidado)

    # 2. Normalizar superficies y excluir Carpet
    df = normalizar_superficies(df)

    # 3. Parsear sets y games del score
    df = _agregar_sets_games(df)

    # 4. Preparar participaciones unificadas
    participaciones = unificar_participaciones(df)

    # 5. Estadisticas totales
    totales = calcular_estadisticas_totales(participaciones)

    # 6. Estadisticas por superficie
    por_superficie = calcular_estadisticas_por_superficie(participaciones)

    # 7. Titulos por categoria y superficie
    titulos = calcular_titulos_por_superficie(df)

    # 8. Unir todo
    stats = totales.join(por_superficie, how="left").join(titulos, how="left")

    # Rellenar titulos faltantes con 0 (jugadores sin titulos)
    cols_titulos = [c for c in stats.columns if c.startswith("titulos-")]
    stats[cols_titulos] = stats[cols_titulos].fillna(0).astype(int)

    # Rellenar conteos de partidos/victorias/derrotas/games/sets/minutos en superficies faltantes con 0
    # (jugadores que no jugaron en alguna superficie).
    # ¡IMPORTANTE!: Las estadisticas de servicio (aces, dobles-faltas, etc.) NO se rellenan con 0,
    # quedan como NaN para no falsear el perfil del jugador.
    for suf in SUFIJOS_SUPERFICIE:
        cols_conteo_suf = [
            f"partidos-{suf}", f"victorias-{suf}", f"derrotas-{suf}",
            f"partidos-validos-{suf}", f"partidos-validos-resto-{suf}",
            f"sets-ganados-{suf}", f"sets-perdidos-{suf}",
            f"games-ganados-{suf}", f"games-perdidos-{suf}", f"minutos-{suf}",
        ]
        for col in cols_conteo_suf:
            if col in stats.columns:
                stats[col] = stats[col].fillna(0)
            else:
                stats[col] = 0

        for stat_orig, stat_es in STATS_SAQUE:
            col_stat = f"{stat_es}-{suf}"
            if col_stat not in stats.columns:
                stats[col_stat] = float("nan")
        for stat_orig, stat_es in STATS_RESTO:
            col_stat = f"{stat_es}-{suf}"
            if col_stat not in stats.columns:
                stats[col_stat] = float("nan")

    # 9. Filtrar jugadores con menos de 3 partidos
    stats = filtrar_minimo_partidos(stats, minimo=3)

    # 10. Calcular tasas y coberturas desde los totales del Silver
    stats = agregar_tasas_y_cobertura(stats)

    # 11. Cargar informacion personal
    ruta_bios = config.DIR_CRUDO / config.ARCHIVO_BIOS
    bios = cargar_informacion_jugadores(ruta_bios)

    # 12. Unir con informacion personal
    dataset = unir_informacion_jugadores(stats, bios)

    # 13. Ordenar columnas: info personal primero, luego totales, superficie, titulos
    cols_info = [
        c for c in dataset.columns
        if c in (
            "id-jugador", "nombre-jugador", "fecha-nacimiento", "altura-cm",
            "peso-kg", "mano-dominante", "tipo-reves", "año-profesional", "pais",
        )
    ]
    cols_totales = [c for c in dataset.columns if c.endswith("-totales")]
    cols_sup_ord = []
    for suf in SUFIJOS_SUPERFICIE:
        cols_sup_ord.extend(
            sorted(c for c in dataset.columns
                   if c.endswith(f"-{suf}") and not c.startswith("titulos-"))
        )
    cols_tit = sorted(c for c in dataset.columns if c.startswith("titulos-"))
    resto = [
        c for c in dataset.columns
        if c not in cols_info + cols_totales + cols_sup_ord + cols_tit
    ]
    dataset = dataset[cols_info + sorted(cols_totales) + cols_sup_ord + cols_tit + resto]

    # 14. Validar
    validar_dataset(dataset)

    # 15. Guardar
    destino = config.DIR_PROCESADO / "atp_jugadores.csv"
    guardar_dataset(dataset, destino)

    return str(destino)
