from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

STYLE_FEATURES = [
    "ace_rate",
    "double_fault_rate",
    "first_serve_in_pct",
    "first_serve_win_pct",
    "second_serve_win_pct",
    "bp_save_pct",
    "first_return_win_pct",
    "second_return_win_pct",
    "break_conversion_pct",
]

PERFORMANCE_FEATURES = [
    "service_points_won_pct",
    "return_points_won_pct",
]

RAW_SUM_COLUMNS = [
    "aces",
    "double_faults",
    "service_points",
    "first_serves_in",
    "first_serve_points_won",
    "second_serve_points",
    "second_serve_points_won",
    "service_points_won",
    "service_games",
    "break_points_saved",
    "break_points_faced",
    "return_points",
    "return_points_won",
    "first_return_points",
    "first_return_points_won",
    "second_return_points",
    "second_return_points_won",
    "break_points_opportunities",
    "break_points_converted",
]


def _safe_div(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    n = pd.to_numeric(numerador, errors="coerce")
    d = pd.to_numeric(denominador, errors="coerce")
    resultado = n / d.where(d > 0)
    return resultado.replace([np.inf, -np.inf], np.nan)


def _last_valid(s: pd.Series):
    s = s.dropna()
    return s.iloc[-1] if len(s) else pd.NA


def preparar_biografias(ruta: str | Path | None) -> pd.DataFrame:
    cols = ["player_id", "bio_name", "bio_hand", "backhand", "bio_height", "bio_ioc"]
    if ruta is None or not Path(ruta).exists():
        return pd.DataFrame(columns=cols)

    bio = pd.read_csv(ruta, dtype="string", encoding="utf-8", encoding_errors="replace")
    bio = bio.rename(columns={
        "id": "player_id",
        "atpname": "bio_name",
        "hand": "bio_hand",
        "height": "bio_height",
        "ioc": "bio_ioc",
    })

    for c in ["player_id", "bio_name", "bio_hand", "backhand", "bio_ioc"]:
        if c in bio.columns:
            bio[c] = bio[c].str.strip()

    bio["backhand"] = bio["backhand"].replace({"Unknown": pd.NA, "U": pd.NA, "": pd.NA})
    bio.loc[~bio["backhand"].isin(["1H", "2H"]), "backhand"] = pd.NA

    bio["bio_hand"] = bio["bio_hand"].replace({"Unknown": pd.NA, "U": pd.NA, "": pd.NA})
    bio.loc[~bio["bio_hand"].isin(["R", "L", "A"]), "bio_hand"] = pd.NA

    bio["bio_height"] = pd.to_numeric(bio["bio_height"], errors="coerce")
    bio.loc[~bio["bio_height"].between(140, 230), "bio_height"] = np.nan

    # La fuente trae unos pocos ids repetidos por variantes ortograficas.
    # Se conserva la fila con mayor cantidad de metadatos utilizables.
    score_cols = [c for c in ["backhand", "bio_hand", "bio_height", "bio_ioc", "bio_name"] if c in bio]
    bio["_completitud"] = bio[score_cols].notna().sum(axis=1)
    bio = (
        bio.sort_values(["player_id", "_completitud"], kind="mergesort")
        .drop_duplicates("player_id", keep="last")
    )

    return bio[cols]


def _construir_lado(partidos: pd.DataFrame, ganador: bool) -> pd.DataFrame:
    jugador = "winner" if ganador else "loser"
    rival = "loser" if ganador else "winner"
    lado = "w" if ganador else "l"
    lado_rival = "l" if ganador else "w"

    comunes = [
        "id_partido", "fecha", "anio", "tourney_id", "tourney_name", "surface",
        "tourney_level", "indoor", "round", "orden_ronda", "best_of", "match_num",
    ]
    out = partidos[[c for c in comunes if c in partidos.columns]].copy()

    out["player_id"] = partidos[f"{jugador}_id"].astype("string")
    out["player_name"] = partidos[f"{jugador}_name"]
    out["player_hand_match"] = partidos[f"{jugador}_hand"]
    out["player_ht_match"] = partidos[f"{jugador}_ht"]
    out["player_ioc_match"] = partidos[f"{jugador}_ioc"]
    out["player_age"] = partidos[f"{jugador}_age"]
    out["player_rank"] = partidos[f"{jugador}_rank"]
    out["player_rank_points"] = partidos[f"{jugador}_rank_points"]

    out["opponent_id"] = partidos[f"{rival}_id"].astype("string")
    out["opponent_name"] = partidos[f"{rival}_name"]
    out["opponent_rank"] = partidos[f"{rival}_rank"]
    out["opponent_rank_points"] = partidos[f"{rival}_rank_points"]
    out["won"] = 1 if ganador else 0

    stat_map = {
        "aces": "ace",
        "double_faults": "df",
        "service_points": "svpt",
        "first_serves_in": "1stIn",
        "first_serve_points_won": "1stWon",
        "second_serve_points_won": "2ndWon",
        "service_games": "SvGms",
        "break_points_saved": "bpSaved",
        "break_points_faced": "bpFaced",
    }
    for destino, origen in stat_map.items():
        out[destino] = partidos[f"{lado}_{origen}"]
        out[f"opp_{destino}"] = partidos[f"{lado_rival}_{origen}"]

    return out


def normalizar_partidos_jugador(partidos: pd.DataFrame, bios: pd.DataFrame | None = None) -> pd.DataFrame:
    """Pasa de una fila por partido a dos filas por partido (una por tenista)."""
    partidos = partidos.copy()
    partidos["fecha"] = pd.to_datetime(partidos["fecha"], errors="coerce")

    numericas = [
        "winner_ht", "loser_ht", "winner_age", "loser_age", "winner_rank", "loser_rank",
        "winner_rank_points", "loser_rank_points",
    ] + [f"{lado}_{stat}" for lado in ("w", "l") for stat in [
        "ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced"
    ]]
    for c in numericas:
        if c in partidos.columns:
            partidos[c] = pd.to_numeric(partidos[c], errors="coerce")

    largo = pd.concat(
        [_construir_lado(partidos, True), _construir_lado(partidos, False)],
        ignore_index=True,
        sort=False,
    )

    if bios is not None and not bios.empty:
        largo = largo.merge(bios, on="player_id", how="left", validate="many_to_one")
    else:
        for c in ["bio_name", "bio_hand", "backhand", "bio_height", "bio_ioc"]:
            largo[c] = pd.NA

    largo["player_name"] = largo["player_name"].fillna(largo["bio_name"])
    largo["hand"] = largo["player_hand_match"].fillna(largo["bio_hand"])
    largo["height_cm"] = pd.to_numeric(largo["player_ht_match"], errors="coerce").fillna(
        pd.to_numeric(largo["bio_height"], errors="coerce")
    )
    largo["ioc"] = largo["player_ioc_match"].fillna(largo["bio_ioc"])

    # Cantidades derivadas para saque y resto. Las relaciones imposibles se dejan
    # como NaN en vez de corregir silenciosamente la fuente.
    largo["second_serve_points"] = largo["service_points"] - largo["first_serves_in"]
    largo.loc[largo["second_serve_points"] < 0, "second_serve_points"] = np.nan

    largo["service_points_won"] = (
        largo["first_serve_points_won"] + largo["second_serve_points_won"]
    )

    largo["return_points"] = largo["opp_service_points"]
    largo["return_points_won"] = largo["opp_service_points"] - (
        largo["opp_first_serve_points_won"] + largo["opp_second_serve_points_won"]
    )
    largo.loc[largo["return_points_won"] < 0, "return_points_won"] = np.nan

    largo["first_return_points"] = largo["opp_first_serves_in"]
    largo["first_return_points_won"] = (
        largo["opp_first_serves_in"] - largo["opp_first_serve_points_won"]
    )
    largo.loc[largo["first_return_points_won"] < 0, "first_return_points_won"] = np.nan

    largo["second_return_points"] = largo["opp_service_points"] - largo["opp_first_serves_in"]
    largo.loc[largo["second_return_points"] < 0, "second_return_points"] = np.nan
    largo["second_return_points_won"] = (
        largo["second_return_points"] - largo["opp_second_serve_points_won"]
    )
    largo.loc[largo["second_return_points_won"] < 0, "second_return_points_won"] = np.nan

    largo["break_points_opportunities"] = largo["opp_break_points_faced"]
    largo["break_points_converted"] = (
        largo["opp_break_points_faced"] - largo["opp_break_points_saved"]
    )
    largo.loc[largo["break_points_converted"] < 0, "break_points_converted"] = np.nan

    # Tasas por partido. Se conservan para exploracion; los perfiles de carrera
    # se calculan con suma(numerador)/suma(denominador), no promediando estas tasas.
    largo["ace_rate"] = _safe_div(largo["aces"], largo["service_points"])
    largo["double_fault_rate"] = _safe_div(largo["double_faults"], largo["service_points"])
    largo["first_serve_in_pct"] = _safe_div(largo["first_serves_in"], largo["service_points"])
    largo["first_serve_win_pct"] = _safe_div(largo["first_serve_points_won"], largo["first_serves_in"])
    largo["second_serve_win_pct"] = _safe_div(largo["second_serve_points_won"], largo["second_serve_points"])
    largo["service_points_won_pct"] = _safe_div(largo["service_points_won"], largo["service_points"])
    largo["bp_save_pct"] = _safe_div(largo["break_points_saved"], largo["break_points_faced"])
    largo["return_points_won_pct"] = _safe_div(largo["return_points_won"], largo["return_points"])
    largo["first_return_win_pct"] = _safe_div(largo["first_return_points_won"], largo["first_return_points"])
    largo["second_return_win_pct"] = _safe_div(largo["second_return_points_won"], largo["second_return_points"])
    largo["break_conversion_pct"] = _safe_div(largo["break_points_converted"], largo["break_points_opportunities"])

    largo["serve_stats_available"] = largo["service_points"].notna().astype("int8")
    largo["return_stats_available"] = largo["return_points"].notna().astype("int8")

    eliminar = [
        "bio_name", "bio_hand", "bio_height", "bio_ioc",
        "player_hand_match", "player_ht_match", "player_ioc_match",
    ] + [c for c in largo.columns if c.startswith("opp_") and c not in ["opponent_id", "opponent_name", "opponent_rank", "opponent_rank_points"]]
    largo = largo.drop(columns=[c for c in eliminar if c in largo.columns])

    largo = largo.sort_values(
        ["fecha", "tourney_id", "orden_ronda", "match_num", "id_partido", "player_id"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)

    return largo


def _agregar_perfiles(largo: pd.DataFrame, claves: list[str]) -> pd.DataFrame:
    orden = largo.sort_values(["fecha", "id_partido"], kind="mergesort")
    g = orden.groupby(claves, dropna=False, sort=False)

    base = g.agg(
        n_matches=("id_partido", "size"),
        n_wins=("won", "sum"),
        first_match=("fecha", "min"),
        last_match=("fecha", "max"),
        matches_with_serve_stats=("serve_stats_available", "sum"),
        matches_with_return_stats=("return_stats_available", "sum"),
        best_rank=("player_rank", "min"),
        last_rank=("player_rank", _last_valid),
        last_rank_points=("player_rank_points", _last_valid),
        player_name=("player_name", _last_valid),
        hand=("hand", _last_valid),
        backhand=("backhand", _last_valid),
        height_cm=("height_cm", "median"),
        ioc=("ioc", _last_valid),
    ).reset_index()

    sums = g[RAW_SUM_COLUMNS].sum(min_count=1).reset_index()
    p = base.merge(sums, on=claves, how="left", validate="one_to_one")

    p["win_rate"] = _safe_div(p["n_wins"], p["n_matches"])
    p["serve_coverage_pct"] = _safe_div(p["matches_with_serve_stats"], p["n_matches"])
    p["return_coverage_pct"] = _safe_div(p["matches_with_return_stats"], p["n_matches"])

    p["ace_rate"] = _safe_div(p["aces"], p["service_points"])
    p["double_fault_rate"] = _safe_div(p["double_faults"], p["service_points"])
    p["first_serve_in_pct"] = _safe_div(p["first_serves_in"], p["service_points"])
    p["first_serve_win_pct"] = _safe_div(p["first_serve_points_won"], p["first_serves_in"])
    p["second_serve_win_pct"] = _safe_div(p["second_serve_points_won"], p["second_serve_points"])
    p["service_points_won_pct"] = _safe_div(p["service_points_won"], p["service_points"])
    p["bp_save_pct"] = _safe_div(p["break_points_saved"], p["break_points_faced"])
    p["return_points_won_pct"] = _safe_div(p["return_points_won"], p["return_points"])
    p["first_return_win_pct"] = _safe_div(p["first_return_points_won"], p["first_return_points"])
    p["second_return_win_pct"] = _safe_div(p["second_return_points_won"], p["second_return_points"])
    p["break_conversion_pct"] = _safe_div(p["break_points_converted"], p["break_points_opportunities"])
    return p


def construir_perfiles_jugador(largo: pd.DataFrame, min_partidos: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    perfiles = _agregar_perfiles(largo, ["player_id"])

    # Mezcla de superficies para interpretar perfiles sin usarla como feature de estilo.
    surf = pd.crosstab(largo["player_id"], largo["surface"], normalize="index")
    surf = surf.rename(columns=lambda c: f"surface_share_{str(c).lower()}").reset_index()
    perfiles = perfiles.merge(surf, on="player_id", how="left", validate="one_to_one")

    perfiles["style_eligible"] = (
        (perfiles["matches_with_serve_stats"] >= min_partidos)
        & (perfiles["matches_with_return_stats"] >= min_partidos)
        & perfiles[STYLE_FEATURES].notna().all(axis=1)
    )

    perfiles = perfiles.sort_values(["style_eligible", "n_matches"], ascending=[False, False]).reset_index(drop=True)

    columnas_style = [
        "player_id", "player_name", "hand", "backhand", "height_cm", "ioc",
        "n_matches", "matches_with_serve_stats", "matches_with_return_stats",
        "serve_coverage_pct", "return_coverage_pct", "first_match", "last_match",
    ] + STYLE_FEATURES + PERFORMANCE_FEATURES + [
        "win_rate", "best_rank", "last_rank", "last_rank_points",
    ] + [c for c in perfiles.columns if c.startswith("surface_share_")]

    style = perfiles.loc[perfiles["style_eligible"], columnas_style].copy()
    return perfiles, style


def construir_perfiles_superficie(largo: pd.DataFrame, min_partidos: int = 10) -> pd.DataFrame:
    x = largo[largo["surface"].notna()].copy()
    perfiles = _agregar_perfiles(x, ["player_id", "surface"])
    perfiles["surface_profile_eligible"] = (
        (perfiles["matches_with_serve_stats"] >= min_partidos)
        & (perfiles["matches_with_return_stats"] >= min_partidos)
        & perfiles[STYLE_FEATURES].notna().all(axis=1)
    )
    return perfiles.sort_values(["player_id", "surface"]).reset_index(drop=True)


def _previous_cumsum(df: pd.DataFrame, columna: str) -> pd.Series:
    vals = pd.to_numeric(df[columna], errors="coerce").fillna(0)
    acumulado = vals.groupby(df["player_id"], sort=False).cumsum()
    previo = acumulado.groupby(df["player_id"], sort=False).shift(1)
    return previo.fillna(0)


def construir_historial_prematch(largo: pd.DataFrame) -> pd.DataFrame:
    """Calcula features usando exclusivamente partidos anteriores al actual."""
    x = largo.sort_values(
        ["player_id", "fecha", "tourney_id", "orden_ronda", "match_num", "id_partido"],
        kind="mergesort",
        na_position="last",
    ).copy()

    x["matches_before"] = x.groupby("player_id", sort=False).cumcount()
    # Cantidad de partidos con estadisticas disponibles antes del partido actual.
    valid_serve = x["serve_stats_available"].fillna(0)
    valid_return = x["return_stats_available"].fillna(0)
    x["serve_matches_before"] = valid_serve.groupby(x["player_id"], sort=False).cumsum().groupby(x["player_id"], sort=False).shift(1).fillna(0)
    x["return_matches_before"] = valid_return.groupby(x["player_id"], sort=False).cumsum().groupby(x["player_id"], sort=False).shift(1).fillna(0)

    hist_cols = RAW_SUM_COLUMNS
    for c in hist_cols:
        x[f"hist_{c}"] = _previous_cumsum(x, c)

    x["hist_ace_rate"] = _safe_div(x["hist_aces"], x["hist_service_points"])
    x["hist_double_fault_rate"] = _safe_div(x["hist_double_faults"], x["hist_service_points"])
    x["hist_first_serve_in_pct"] = _safe_div(x["hist_first_serves_in"], x["hist_service_points"])
    x["hist_first_serve_win_pct"] = _safe_div(x["hist_first_serve_points_won"], x["hist_first_serves_in"])
    x["hist_second_serve_win_pct"] = _safe_div(x["hist_second_serve_points_won"], x["hist_second_serve_points"])
    x["hist_service_points_won_pct"] = _safe_div(x["hist_service_points_won"], x["hist_service_points"])
    x["hist_bp_save_pct"] = _safe_div(x["hist_break_points_saved"], x["hist_break_points_faced"])
    x["hist_return_points_won_pct"] = _safe_div(x["hist_return_points_won"], x["hist_return_points"])
    x["hist_first_return_win_pct"] = _safe_div(x["hist_first_return_points_won"], x["hist_first_return_points"])
    x["hist_second_return_win_pct"] = _safe_div(x["hist_second_return_points_won"], x["hist_second_return_points"])
    x["hist_break_conversion_pct"] = _safe_div(x["hist_break_points_converted"], x["hist_break_points_opportunities"])

    keep = [
        "id_partido", "fecha", "anio", "tourney_id", "tourney_name", "surface", "tourney_level",
        "indoor", "round", "best_of", "player_id", "player_name", "hand", "backhand", "height_cm",
        "ioc", "player_age", "player_rank", "player_rank_points", "opponent_id", "won",
        "matches_before", "serve_matches_before", "return_matches_before",
    ] + [f"hist_{c}" for c in STYLE_FEATURES + PERFORMANCE_FEATURES]

    return x[keep].copy()


def construir_matchups_modelo(historial: pd.DataFrame, min_historial: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convierte las dos filas jugador-partido en A/B sin usar ganador/perdedor."""
    x = historial.copy()
    # A/B se define por id, no por resultado. Así la etiqueta no está codificada en el lado.
    x["side"] = np.where(x["player_id"].astype(str) < x["opponent_id"].astype(str), "a", "b")

    comunes = ["id_partido", "fecha", "anio", "tourney_id", "tourney_name", "surface", "tourney_level", "indoor", "round", "best_of"]
    features_player = [
        "player_id", "player_name", "hand", "backhand", "height_cm", "ioc", "player_age",
        "player_rank", "player_rank_points", "matches_before", "serve_matches_before", "return_matches_before",
    ] + [f"hist_{c}" for c in STYLE_FEATURES + PERFORMANCE_FEATURES]

    a = x[x["side"] == "a"][comunes + features_player + ["won"]].copy()
    b = x[x["side"] == "b"][["id_partido"] + features_player].copy()
    a = a.rename(columns={c: f"a_{c}" for c in features_player})
    a = a.rename(columns={"won": "target_a_wins"})
    b = b.rename(columns={c: f"b_{c}" for c in features_player})

    matchups = a.merge(b, on="id_partido", how="inner", validate="one_to_one")
    matchups["rank_diff_a_minus_b"] = matchups["a_player_rank"] - matchups["b_player_rank"]
    matchups["rank_points_diff_a_minus_b"] = matchups["a_player_rank_points"] - matchups["b_player_rank_points"]

    for f in STYLE_FEATURES + PERFORMANCE_FEATURES:
        matchups[f"diff_{f}_a_minus_b"] = matchups[f"a_hist_{f}"] - matchups[f"b_hist_{f}"]

    matchups["eligible_model"] = (
        (matchups["a_serve_matches_before"] >= min_historial)
        & (matchups["b_serve_matches_before"] >= min_historial)
        & (matchups["a_return_matches_before"] >= min_historial)
        & (matchups["b_return_matches_before"] >= min_historial)
        & matchups["a_player_rank"].notna()
        & matchups["b_player_rank"].notna()
        & matchups[[f"a_hist_{f}" for f in STYLE_FEATURES]].notna().all(axis=1)
        & matchups[[f"b_hist_{f}" for f in STYLE_FEATURES]].notna().all(axis=1)
    )

    modelo = matchups[matchups["eligible_model"]].copy().reset_index(drop=True)
    return matchups.reset_index(drop=True), modelo
