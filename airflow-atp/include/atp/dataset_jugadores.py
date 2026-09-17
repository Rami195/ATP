"""Construccion del dataset de jugadores ATP.

Agrega las estadisticas de cada jugador a lo largo de todos sus partidos
validos (excluyendo Carpet), separadas en totales y por superficie.
Incluye titulos ganados por categoria y superficie.

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


# ---------------------------------------------------------------------------
# Preparacion de participaciones
# ---------------------------------------------------------------------------

def preparar_participaciones_ganador(df: pd.DataFrame) -> pd.DataFrame:
    """Crea la vista del ganador con columnas unificadas."""
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

    columnas = list(renombre.keys()) + ["surface", "tourney_id", "round", "tourney_level"]
    out = df[columnas].rename(columns=renombre).copy()
    out["victoria"] = 1
    return out


def preparar_participaciones_perdedor(df: pd.DataFrame) -> pd.DataFrame:
    """Crea la vista del perdedor con columnas unificadas."""
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

    columnas = list(renombre.keys()) + ["surface", "tourney_id", "round", "tourney_level"]
    out = df[columnas].rename(columns=renombre).copy()
    out["victoria"] = 0
    return out


def unificar_participaciones(df: pd.DataFrame) -> pd.DataFrame:
    """Concatena las vistas de ganador y perdedor."""
    ganadores = preparar_participaciones_ganador(df)
    perdedores = preparar_participaciones_perdedor(df)
    participaciones = pd.concat([ganadores, perdedores], ignore_index=True)
    log.info("Participaciones unificadas: %d filas", len(participaciones))
    return participaciones


# ---------------------------------------------------------------------------
# Estadisticas totales
# ---------------------------------------------------------------------------

def _columnas_agregables() -> list[str]:
    """Devuelve las columnas numericas que se suman por jugador."""
    cols = ["victoria", "sets_ganados", "sets_perdidos",
            "games_ganados", "games_perdidos", "minutos"]
    for stat_orig, _ in STATS_SAQUE:
        cols.append(stat_orig)
    return cols


def _renombrar_stats_espanol(df: pd.DataFrame, sufijo: str) -> pd.DataFrame:
    """Renombra columnas internas al formato en espanol con guion medio."""
    renombre = {
        "victoria": f"victorias-{sufijo}",
        "sets_ganados": f"sets-ganados-{sufijo}",
        "sets_perdidos": f"sets-perdidos-{sufijo}",
        "games_ganados": f"games-ganados-{sufijo}",
        "games_perdidos": f"games-perdidos-{sufijo}",
        "minutos": f"minutos-{sufijo}",
    }
    for stat_orig, stat_es in STATS_SAQUE:
        renombre[stat_orig] = f"{stat_es}-{sufijo}"
    return df.rename(columns=renombre)


def calcular_estadisticas_totales(participaciones: pd.DataFrame) -> pd.DataFrame:
    """Calcula estadisticas acumuladas sobre todos los partidos validos."""
    cols = _columnas_agregables()
    totales = participaciones.groupby("id_jugador")[cols].sum()

    totales = _renombrar_stats_espanol(totales, "totales")

    # Partidos totales y derrotas
    conteo = participaciones.groupby("id_jugador").size().rename("partidos-totales")
    totales = totales.join(conteo)
    totales["derrotas-totales"] = totales["partidos-totales"] - totales["victorias-totales"]

    return totales


def calcular_estadisticas_por_superficie(participaciones: pd.DataFrame) -> pd.DataFrame:
    """Calcula estadisticas acumuladas por superficie."""
    cols = _columnas_agregables()
    superficies_presentes = sorted(
        s for s in participaciones["surface"].unique() if s in SUPERFICIES_VALIDAS
    )

    partes = []
    for superficie in superficies_presentes:
        sub = participaciones[participaciones["surface"] == superficie]
        stats = sub.groupby("id_jugador")[cols].sum()
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
    minimo: int = 5,
) -> pd.DataFrame:
    """Excluye jugadores con menos de `minimo` partidos validos."""
    antes = len(stats)
    stats = stats[stats["partidos-totales"] >= minimo].copy()
    excluidos = antes - len(stats)
    log.info(
        "Filtro de minimo %d partidos: %d jugadores excluidos, %d incluidos",
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

    # 3. No hay jugadores con menos de 5 partidos
    bajo_minimo = df[df["partidos-totales"] < 5]
    if len(bajo_minimo):
        problemas.append(
            f"[filtro] {len(bajo_minimo)} jugadores con menos de 5 partidos"
        )

    # 4. No hay estadisticas de Carpet
    cols_carpet = [c for c in df.columns if "carpet" in c.lower()]
    if cols_carpet:
        problemas.append(f"[carpet] columnas de Carpet encontradas: {cols_carpet}")

    # 5. No hay porcentajes
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

    # 10. Totales consistentes con suma de superficies
    for metrica in ("partidos", "victorias", "derrotas"):
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

    # 11. Sin filas duplicadas
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
    """Porcentaje de nulos por columna clave del dataset de jugadores.

    Complementa ``consolidar.informe_calidad`` (que opera sobre partidos)
    con un reporte equivalente para el dataset agregado por jugador.
    """
    columnas = [
        "id-jugador", "nombre-jugador", "fecha-nacimiento", "altura-cm",
        "peso-kg", "mano-dominante", "tipo-reves", "año-profesional", "pais",
        "partidos-totales", "victorias-totales", "aces-totales",
        "partidos-cemento", "partidos-clay", "partidos-grass",
    ]
    columnas = [c for c in columnas if c in df.columns]

    informe = pd.DataFrame({
        "columna": columnas,
        "nulos": [int(df[c].isna().sum()) for c in columnas],
    })
    informe["pct_nulos"] = (informe["nulos"] / len(df) * 100).round(2)

    print("\n      Nulos por columna clave — dataset jugadores (top 6):")
    for _, fila in informe.sort_values("pct_nulos", ascending=False).head(6).iterrows():
        print(f"        {fila['columna']:<24} {fila['pct_nulos']:>6.2f} %")
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

    # Rellenar estadisticas de superficie faltantes con 0
    # (jugadores que no jugaron en alguna superficie)
    cols_superficie = [
        c for c in stats.columns
        if any(c.endswith(f"-{s}") for s in SUFIJOS_SUPERFICIE)
        and not c.startswith("titulos-")
    ]
    stats[cols_superficie] = stats[cols_superficie].fillna(0)

    # 9. Filtrar jugadores con menos de 5 partidos
    stats = filtrar_minimo_partidos(stats, minimo=5)

    # 10. Cargar informacion personal
    ruta_bios = config.DIR_CRUDO / config.ARCHIVO_BIOS
    bios = cargar_informacion_jugadores(ruta_bios)

    # 11. Unir con informacion personal
    dataset = unir_informacion_jugadores(stats, bios)

    # 12. Ordenar columnas: info personal primero, luego totales, superficie, titulos
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

    # 13. Validar
    validar_dataset(dataset)

    # 14. Guardar
    destino = config.DIR_PROCESADO / "atp_jugadores.csv"
    guardar_dataset(dataset, destino)

    return str(destino)
