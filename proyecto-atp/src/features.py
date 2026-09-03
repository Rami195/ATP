"""Paso 3 y 4 del pipeline: formato jugador-partido, historial sin fuga y
dataset de modelado con asignacion aleatoria A/B.

Las dos reglas que gobiernan todo este modulo:

1. Nada de lo que ocurre DURANTE el partido puede ser feature. Las columnas
   w_ace, w_bpSaved, etc. describen el partido que queremos predecir: usarlas
   es hacer trampa. Solo entran al modelo como historial de partidos ANTERIORES.
2. Las columnas vienen etiquetadas winner_/loser_, o sea que el orden mismo
   revela el resultado. Por eso reasignamos cada partido a jugador A / jugador B
   con una moneda al aire reproducible, y el target pasa a ser "gana A".
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config

# Features historicas construidas por jugador. Todas miran hacia atras.
FEATURES_HISTORICAS = [
    "n_partidos", "winrate_hist", "winrate_10",
    "n_partidos_sup", "winrate_sup",
    "bp_salvados_pct", "bp_convertidos_pct",
    "tb_winrate", "decisivos_winrate", "indice_presion",
    "ace_pct", "df_pct", "primer_saque_in_pct",
    "primer_saque_gan_pct", "segundo_saque_gan_pct", "pts_saque_ganados_pct",
    "dias_descanso", "partidos_en_anio",
    "h2h_ganados", "h2h_jugados",
]

# Datos del jugador conocidos ANTES del partido (ranking al lunes del torneo).
DATOS_PREVIOS = [
    "jugador_id", "jugador_nombre", "jugador_mano",
    "jugador_ht", "jugador_edad", "jugador_rank", "jugador_rank_pts", "jugador_seed",
]

_RE_SET = re.compile(r"^(\d+)-(\d+)(?:\((\d+)\))?$")
_MARCAS_INCOMPLETO = ("RET", "W/O", "WO", "DEF", "ABN", "Walkover", "Default")


# --------------------------------------------------------------------------
# Parseo del score
# --------------------------------------------------------------------------
def _parsear_score(score: object, best_of: float) -> tuple[int, int, int, int, int]:
    """(sets, tiebreaks_totales, tb_ganados_por_el_ganador, decisivo, incompleto)."""
    if not isinstance(score, str) or not score.strip():
        return 0, 0, 0, 0, 1

    incompleto = int(any(marca in score for marca in _MARCAS_INCOMPLETO))

    sets = tb_total = tb_gano_w = 0
    for token in score.split():
        m = _RE_SET.match(token)
        if not m:
            continue
        juegos_w, juegos_l = int(m.group(1)), int(m.group(2))
        sets += 1
        # Un set es tie-break si termino 7-6/6-7 o si trae el marcador del TB
        # entre parentesis (cubre los super tie-breaks 10-8, 7-6(10), etc.).
        if m.group(3) is not None or {juegos_w, juegos_l} == {7, 6}:
            tb_total += 1
            if juegos_w > juegos_l:
                tb_gano_w += 1

    # Se llego al set decisivo si se jugaron todos los sets posibles.
    decisivo = 0
    if not incompleto and best_of in (3, 5) and sets == int(best_of):
        decisivo = 1

    return sets, tb_total, tb_gano_w, decisivo, incompleto


def parsear_scores(partidos: pd.DataFrame) -> pd.DataFrame:
    """Deriva tie-breaks y sets decisivos del string de score."""
    partidos = partidos.copy()

    # Memoizamos: hay muchos partidos y relativamente pocos scores distintos.
    cache: dict[tuple, tuple] = {}
    filas = []
    for score, best_of in zip(partidos["score"], partidos["best_of"]):
        clave = (score, best_of)
        if clave not in cache:
            cache[clave] = _parsear_score(score, best_of)
        filas.append(cache[clave])

    derivado = pd.DataFrame(
        filas,
        columns=["sets_jugados", "tb_jugados", "tb_ganados_w", "decisivo", "incompleto"],
        index=partidos.index,
    )
    partidos = pd.concat([partidos, derivado], axis=1)
    partidos["tb_ganados_l"] = partidos["tb_jugados"] - partidos["tb_ganados_w"]
    return partidos


# --------------------------------------------------------------------------
# Head to head
# --------------------------------------------------------------------------
def _agregar_h2h(partidos: pd.DataFrame) -> pd.DataFrame:
    """Historial mutuo ANTES de cada partido, sin contar el partido en curso."""
    partidos = partidos.copy()
    ganador = partidos["winner_id"].astype(str).values
    perdedor = partidos["loser_id"].astype(str).values

    # Clave de par independiente del orden.
    menor = np.where(ganador < perdedor, ganador, perdedor)
    mayor = np.where(ganador < perdedor, perdedor, ganador)
    par = pd.Series([f"{a}|{b}" for a, b in zip(menor, mayor)], index=partidos.index)

    gano_menor = pd.Series((ganador == menor).astype(int), index=partidos.index)

    # cumsum menos la fila actual = todo lo previo.
    previas_menor = gano_menor.groupby(par).cumsum() - gano_menor
    total_previas = par.groupby(par).cumcount()

    ganador_es_menor = pd.Series(ganador == menor, index=partidos.index)
    partidos["h2h_ganados_w"] = np.where(
        ganador_es_menor, previas_menor, total_previas - previas_menor
    )
    partidos["h2h_ganados_l"] = total_previas - partidos["h2h_ganados_w"]
    partidos["h2h_jugados"] = total_previas
    return partidos


# --------------------------------------------------------------------------
# Formato largo: una fila por jugador y por partido
# --------------------------------------------------------------------------
def a_formato_largo(partidos: pd.DataFrame) -> pd.DataFrame:
    """Duplica cada partido en dos filas (una por jugador)."""
    print("[3/4] Construyendo formato jugador-partido e historial sin fuga")

    partidos = parsear_scores(partidos)
    partidos = _agregar_h2h(partidos)

    contexto = [
        "id_partido", "fecha", "anio", "orden_ronda", "tourney_id", "tourney_name",
        "surface", "tourney_level", "round", "best_of", "minutes",
        "sets_jugados", "decisivo", "incompleto", "h2h_jugados",
    ]
    if "indoor" in partidos.columns:
        contexto.append("indoor")

    def _lado(propio: str, rival: str, gano: int) -> pd.DataFrame:
        df = partidos[contexto].copy()
        df["gano"] = gano
        df["jugador_id"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_id"]
        df["jugador_nombre"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_name"]
        df["jugador_mano"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_hand"]
        df["jugador_ht"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_ht"]
        df["jugador_edad"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_age"]
        df["jugador_rank"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_rank"]
        df["jugador_rank_pts"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_rank_points"]
        df["jugador_seed"] = partidos[f"{'winner' if propio == 'w' else 'loser'}_seed"]
        df["rival_id"] = partidos[f"{'winner' if rival == 'w' else 'loser'}_id"]

        # Estadisticas DE ESE partido: no son features, son el insumo con el
        # que despues construimos el historial de los partidos siguientes.
        for stat in config.STATS_PARTIDO:
            df[f"m_{stat}"] = partidos[f"{propio}_{stat}"]
        # Del rival solo necesitamos los break points, para calcular cuantos
        # convirtio el jugador.
        df["m_rival_bpFaced"] = partidos[f"{rival}_bpFaced"]
        df["m_rival_bpSaved"] = partidos[f"{rival}_bpSaved"]

        df["m_tb_jugados"] = partidos["tb_jugados"]
        df["m_tb_ganados"] = partidos[f"tb_ganados_{propio}"]
        df["m_decisivo_jugado"] = partidos["decisivo"]
        df["m_decisivo_ganado"] = partidos["decisivo"] * gano
        df["h2h_ganados"] = partidos[f"h2h_ganados_{propio}"]
        return df

    largo = pd.concat(
        [_lado("w", "l", 1), _lado("l", "w", 0)], ignore_index=True, sort=False
    )

    largo = largo.sort_values(
        ["jugador_id", "fecha", "orden_ronda"], kind="mergesort"
    ).reset_index(drop=True)

    print(f"      filas jugador-partido {len(largo):>8,}")
    print(f"      jugadores distintos   {largo['jugador_id'].nunique():>8,}")
    return largo


# --------------------------------------------------------------------------
# Historial acumulado (todo desplazado: excluye el partido en curso)
# --------------------------------------------------------------------------
def _acum_excluyendo_actual(valores: pd.Series, claves) -> pd.Series:
    """Suma acumulada de los partidos PREVIOS del jugador."""
    v = pd.to_numeric(valores, errors="coerce").fillna(0.0)
    return v.groupby(claves).cumsum() - v


def _ratio(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Division segura: 0/0 -> NaN (no hay historial suficiente todavia)."""
    den = denominador.replace(0, np.nan)
    return numerador / den


def agregar_historial(largo: pd.DataFrame) -> pd.DataFrame:
    """Agrega las features historicas. Ninguna mira el partido en curso."""
    largo = largo.copy()
    jugador = largo["jugador_id"]
    jugador_sup = [largo["jugador_id"], largo["surface"].fillna("Desconocida")]
    jugador_anio = [largo["jugador_id"], largo["anio"]]

    # --- Volumen y resultados -------------------------------------------
    largo["n_partidos"] = largo.groupby(jugador).cumcount()
    victorias = _acum_excluyendo_actual(largo["gano"], jugador)
    largo["winrate_hist"] = _ratio(victorias, largo["n_partidos"])

    # Forma reciente: promedio movil de las ultimas 10, desplazado una fila.
    largo["winrate_10"] = (
        largo.groupby("jugador_id")["gano"]
        .transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    )

    largo["n_partidos_sup"] = largo.groupby(jugador_sup).cumcount()
    largo["winrate_sup"] = _ratio(
        _acum_excluyendo_actual(largo["gano"], jugador_sup), largo["n_partidos_sup"]
    )

    largo["partidos_en_anio"] = largo.groupby(jugador_anio).cumcount()

    # --- Rendimiento bajo presion (el corazon de la pregunta) ------------
    bp_salvados = _acum_excluyendo_actual(largo["m_bpSaved"], jugador)
    bp_enfrentados = _acum_excluyendo_actual(largo["m_bpFaced"], jugador)
    largo["bp_salvados_pct"] = _ratio(bp_salvados, bp_enfrentados)

    # Break points convertidos = los que el rival enfrento y no salvo.
    oportunidades = _acum_excluyendo_actual(largo["m_rival_bpFaced"], jugador)
    convertidos = oportunidades - _acum_excluyendo_actual(largo["m_rival_bpSaved"], jugador)
    largo["bp_convertidos_pct"] = _ratio(convertidos, oportunidades)

    largo["tb_winrate"] = _ratio(
        _acum_excluyendo_actual(largo["m_tb_ganados"], jugador),
        _acum_excluyendo_actual(largo["m_tb_jugados"], jugador),
    )
    largo["decisivos_winrate"] = _ratio(
        _acum_excluyendo_actual(largo["m_decisivo_ganado"], jugador),
        _acum_excluyendo_actual(largo["m_decisivo_jugado"], jugador),
    )

    # Indice compuesto de presion (derivado, no viene de la fuente).
    largo["indice_presion"] = largo[
        ["bp_salvados_pct", "bp_convertidos_pct", "tb_winrate", "decisivos_winrate"]
    ].mean(axis=1, skipna=True)

    # --- Saque y resto ---------------------------------------------------
    svpt = _acum_excluyendo_actual(largo["m_svpt"], jugador)
    primeros_in = _acum_excluyendo_actual(largo["m_1stIn"], jugador)
    primeros_gan = _acum_excluyendo_actual(largo["m_1stWon"], jugador)
    segundos_gan = _acum_excluyendo_actual(largo["m_2ndWon"], jugador)

    largo["ace_pct"] = _ratio(_acum_excluyendo_actual(largo["m_ace"], jugador), svpt)
    largo["df_pct"] = _ratio(_acum_excluyendo_actual(largo["m_df"], jugador), svpt)
    largo["primer_saque_in_pct"] = _ratio(primeros_in, svpt)
    largo["primer_saque_gan_pct"] = _ratio(primeros_gan, primeros_in)
    largo["segundo_saque_gan_pct"] = _ratio(segundos_gan, svpt - primeros_in)
    largo["pts_saque_ganados_pct"] = _ratio(primeros_gan + segundos_gan, svpt)

    # --- Descanso --------------------------------------------------------
    largo["dias_descanso"] = (
        largo.groupby("jugador_id")["fecha"].diff().dt.days
    )

    print(f"      features historicas   {len(FEATURES_HISTORICAS):>8}")
    return largo


# --------------------------------------------------------------------------
# Dataset de modelado
# --------------------------------------------------------------------------
def a_formato_ab(
    largo: pd.DataFrame,
    semilla: int = config.SEMILLA,
    min_historial: int = config.MIN_HISTORIAL_DEFECTO,
) -> pd.DataFrame:
    """Arma el dataset final: jugador A vs jugador B y target `gana_a`.

    La asignacion A/B es una moneda al aire con semilla fija. Sin esto, el
    modelo aprende "el jugador de la izquierda siempre gana" y da 100 % de
    accuracy sin haber aprendido nada de tenis.
    """
    print("[4/4] Armando dataset de modelado (asignacion aleatoria A/B)")

    # `id_partido` no va aca: pasa a ser el indice y lo reinsertamos al final.
    contexto = [
        "fecha", "anio", "tourney_id", "tourney_name",
        "surface", "tourney_level", "round", "best_of", "incompleto", "h2h_jugados",
    ]
    if "indoor" in largo.columns:
        contexto.append("indoor")

    cols_lado = DATOS_PREVIOS + [c for c in FEATURES_HISTORICAS if c != "h2h_jugados"]

    # drop_duplicates garantiza indice unico: sin esto, un id repetido hace
    # que .loc[comunes] devuelva mas filas de las esperadas y el armado falle.
    ganadores = largo[largo["gano"] == 1].drop_duplicates("id_partido").set_index("id_partido")
    perdedores = largo[largo["gano"] == 0].drop_duplicates("id_partido").set_index("id_partido")

    # Nos quedamos con los partidos que tienen los dos lados.
    comunes = ganadores.index.intersection(perdedores.index)
    ganadores = ganadores.loc[comunes]
    perdedores = perdedores.loc[comunes]

    rng = np.random.default_rng(semilla)
    intercambiar = rng.random(len(comunes)) < 0.5

    g = ganadores[cols_lado]
    p = perdedores[cols_lado]
    cond = pd.DataFrame(
        np.repeat(intercambiar[:, None], len(cols_lado), axis=1),
        index=g.index, columns=cols_lado,
    )

    lado_a = g.mask(cond, p).add_suffix("_a")
    lado_b = p.mask(cond, g).add_suffix("_b")

    dataset = pd.concat(
        [ganadores[contexto].reset_index(drop=True),
         lado_a.reset_index(drop=True),
         lado_b.reset_index(drop=True)],
        axis=1,
    )
    dataset.insert(0, "id_partido", ganadores.index.values)
    # Si no hubo intercambio, A es el ganador original.
    dataset["gana_a"] = (~intercambiar).astype(int)

    # --- Diferencias A - B: casi siempre son mejores features que los
    # --- valores absolutos, porque el partido es una comparacion.
    numericas = [c for c in FEATURES_HISTORICAS if c != "h2h_jugados"] + [
        "jugador_ht", "jugador_edad", "jugador_rank", "jugador_rank_pts"
    ]
    for col in numericas:
        col_a, col_b = f"{col}_a", f"{col}_b"
        if col_a in dataset.columns and col_b in dataset.columns:
            dataset[f"dif_{col}"] = (
                pd.to_numeric(dataset[col_a], errors="coerce")
                - pd.to_numeric(dataset[col_b], errors="coerce")
            )

    # El ranking es fuertemente no lineal: la distancia entre el 1 y el 10 no
    # es la misma que entre el 101 y el 110. El log lo corrige.
    for lado in ("a", "b"):
        rank = pd.to_numeric(dataset[f"jugador_rank_{lado}"], errors="coerce")
        dataset[f"log_rank_{lado}"] = np.log1p(rank)
    dataset["dif_log_rank"] = dataset["log_rank_a"] - dataset["log_rank_b"]

    total = len(dataset)
    suficiente = (
        (dataset["n_partidos_a"] >= min_historial)
        & (dataset["n_partidos_b"] >= min_historial)
    )
    dataset["historial_suficiente"] = suficiente.astype(int)

    print(f"      partidos en dataset   {total:>8,}")
    print(f"      con historial >= {min_historial:<4} {int(suficiente.sum()):>8,}")
    print(f"      balance del target    {dataset['gana_a'].mean():>8.3f}  (esperado ~0.500)")
    return dataset


# Version reducida del dataset: solo lo que aporta senal medida, sin las
# columnas redundantes. Se queda con las `dif_` porque un partido es una
# comparacion: `dif_x` es exactamente `x_a - x_b`, asi que incluir las tres
# genera colinealidad perfecta y rompe cualquier modelo lineal.
COLUMNAS_REDUCIDO = {
    "identificacion": ["id_partido", "fecha", "anio"],
    # Contexto del partido (categoricas, para one-hot).
    "contexto": ["surface", "tourney_level", "round", "best_of", "indoor"],
    # Nombres: no son features, sirven para interpretar y para la app.
    "referencia": ["jugador_nombre_a", "jugador_nombre_b"],
    # Fuerza del jugador: las de mayor AUC individual.
    "fuerza": [
        "dif_log_rank", "dif_jugador_rank_pts",
        "dif_winrate_hist", "dif_winrate_sup", "dif_winrate_10",
        "dif_n_partidos",
    ],
    # Saque y resto.
    "juego": ["dif_pts_saque_ganados_pct", "dif_segundo_saque_gan_pct"],
    # Presion: el corazon de la hipotesis del proyecto.
    "presion": [
        "dif_indice_presion", "dif_bp_salvados_pct", "dif_bp_convertidos_pct",
        "dif_tb_winrate", "dif_decisivos_winrate",
    ],
    "historial_mutuo": ["dif_h2h_ganados", "h2h_jugados"],
    "target": ["gana_a"],
}


def reducir_columnas(dataset: pd.DataFrame) -> pd.DataFrame:
    """Dataset acotado a las columnas con senal medida.

    Descarta las que dieron AUC < 0.55 (dias_descanso, altura, edad, doble
    faltas, primer saque dentro) y las duplicadas `_a` / `_b`.
    """
    columnas = [c for grupo in COLUMNAS_REDUCIDO.values() for c in grupo]
    presentes = [c for c in columnas if c in dataset.columns]
    faltantes = [c for c in columnas if c not in dataset.columns]

    reducido = dataset.loc[dataset["historial_suficiente"] == 1, presentes].copy()

    n_features = sum(
        len([c for c in COLUMNAS_REDUCIDO[g] if c in dataset.columns])
        for g in ("contexto", "fuerza", "juego", "presion", "historial_mutuo")
    )
    print(f"      dataset reducido      {len(reducido):>8,} filas x {len(presentes)} columnas")
    print(f"      de las cuales features{n_features:>8}")
    if faltantes:
        print(f"      no encontradas        {faltantes}")
    return reducido


def control_de_fuga(dataset: pd.DataFrame) -> None:
    """Chequeos que deberian correr en cada ejecucion del pipeline."""
    print("\n      Controles de fuga de datos:")

    columnas_prohibidas = [c for c in dataset.columns if c.startswith("m_")]
    ok_cols = not columnas_prohibidas
    print(f"        [{'OK' if ok_cols else 'X'}] sin stats del partido en curso"
          f"{'' if ok_cols else f' -> {columnas_prohibidas}'}")

    balance = dataset["gana_a"].mean()
    ok_balance = 0.45 < balance < 0.55
    print(f"        [{'OK' if ok_balance else 'X'}] target balanceado ({balance:.3f})")

    # Si alguna feature separa perfectamente las clases, hay fuga.
    sospechosas = []
    for col in dataset.columns:
        if not col.startswith("dif_"):
            continue
        s = pd.to_numeric(dataset[col], errors="coerce")
        valido = s.notna()
        if valido.sum() < 100:
            continue
        auc_burda = (s[valido] > 0).groupby(dataset.loc[valido, "gana_a"]).mean()
        if len(auc_burda) == 2 and abs(auc_burda.iloc[1] - auc_burda.iloc[0]) > 0.90:
            sospechosas.append(col)
    ok_sep = not sospechosas
    print(f"        [{'OK' if ok_sep else 'X'}] ninguna feature separa las clases"
          f"{'' if ok_sep else f' -> {sospechosas}'}")
    print()
