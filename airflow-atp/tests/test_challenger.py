"""Pruebas para la descarga y consolidacion de datos Challenger y Qualifying."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from atp import config, consolidar, dataset_jugadores, descarga


def _partido_ejemplo(
    tourney_id: str = "2024-C001",
    tourney_name: str = "ChallengerBuenosAires",
    surface: str = "Clay",
    tourney_level: str = "C",
    tourney_date: str = "20240115",
    match_num: int = 1,
    winner_id: str = "P101",
    winner_name: str = "Challenger Winner",
    loser_id: str = "P102",
    loser_name: str = "Challenger Loser",
    round_: str = "R32",
    score: str = "6-4 6-4",
    minutes: float = 85.0,
    **stats,
) -> dict:
    fila = {
        "tourney_id": tourney_id,
        "tourney_name": tourney_name,
        "surface": surface,
        "draw_size": 32,
        "tourney_level": tourney_level,
        "indoor": 0,
        "tourney_date": tourney_date,
        "match_num": match_num,
        "winner_id": winner_id,
        "winner_seed": stats.get("winner_seed", ""),
        "winner_entry": stats.get("winner_entry", ""),
        "winner_name": winner_name,
        "winner_hand": "R",
        "winner_ht": 185,
        "winner_ioc": "ARG",
        "winner_age": 22.5,
        "winner_rank": 150,
        "winner_rank_points": 400,
        "loser_id": loser_id,
        "loser_seed": stats.get("loser_seed", ""),
        "loser_entry": stats.get("loser_entry", ""),
        "loser_name": loser_name,
        "loser_hand": "R",
        "loser_ht": 180,
        "loser_ioc": "BRA",
        "loser_age": 24.1,
        "loser_rank": 200,
        "loser_rank_points": 280,
        "score": score,
        "best_of": 3,
        "round": round_,
        "minutes": minutes,
        "w_ace": stats.get("w_ace", 5),
        "w_df": stats.get("w_df", 2),
        "w_svpt": stats.get("w_svpt", 60),
        "w_1stIn": stats.get("w_1stIn", 40),
        "w_1stWon": stats.get("w_1stWon", 30),
        "w_2ndWon": stats.get("w_2ndWon", 12),
        "w_SvGms": stats.get("w_SvGms", 10),
        "w_bpSaved": stats.get("w_bpSaved", 3),
        "w_bpFaced": stats.get("w_bpFaced", 4),
        "l_ace": stats.get("l_ace", 2),
        "l_df": stats.get("l_df", 4),
        "l_svpt": stats.get("l_svpt", 55),
        "l_1stIn": stats.get("l_1stIn", 35),
        "l_1stWon": stats.get("l_1stWon", 22),
        "l_2ndWon": stats.get("l_2ndWon", 8),
        "l_SvGms": stats.get("l_SvGms", 10),
        "l_bpSaved": stats.get("l_bpSaved", 2),
        "l_bpFaced": stats.get("l_bpFaced", 5),
    }
    return fila


def test_consolidar_archivos_challenger_y_tour(tmp_path: Path):
    """Verifica que consolidar procese correctamente archivos ATP Tour y Challenger juntos."""
    df_tour = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-001", tourney_level="A", match_num=1, tourney_date="20240101"),
    ])
    df_ch = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-C01", tourney_level="C", match_num=1, tourney_date="20240102"),
    ])

    ptour = tmp_path / "2024.csv"
    pch = tmp_path / "2024_challenger.csv"
    df_tour.to_csv(ptour, index=False)
    df_ch.to_csv(pch, index=False)

    consolidado = consolidar.consolidar([ptour, pch])

    assert len(consolidado) == 2
    assert set(consolidado["anio_archivo"].unique()) == {2024}
    assert "id_partido" in consolidado.columns
    assert consolidado["id_partido"].is_unique


def test_descargar_temporada_challenger_cache(tmp_path: Path):
    """Verifica que descargar_temporada_challenger reusa el archivo si ya existe."""
    archivo_local = tmp_path / "2024_challenger.csv"
    archivo_local.write_text("tourney_id,tourney_name\n2024-C01,Test", encoding="utf-8")

    res = descarga.descargar_temporada_challenger(2024, forzar=False, dir_destino=tmp_path)
    assert res == archivo_local
    assert res.exists()


def test_consolidar_archivos_quali(tmp_path: Path):
    """Verifica que consolidar procese correctamente archivos atp_quali."""
    df_2024 = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-Q01", match_num=1, tourney_date="20240101"),
        _partido_ejemplo(tourney_id="2024-Q01", match_num=2, tourney_date="20240102"),
    ])

    p2024 = tmp_path / "2024_atp_quali.csv"
    df_2024.to_csv(p2024, index=False)

    consolidado = consolidar.consolidar([p2024])

    assert len(consolidado) == 2
    assert set(consolidado["anio_archivo"].unique()) == {2024}
    assert "id_partido" in consolidado.columns
    assert consolidado["id_partido"].is_unique


def test_descargar_temporada_quali_anio_invalido(tmp_path: Path):
    """Verifica que anios anteriores a 2007 retornen None en quali."""
    res = descarga.descargar_temporada_quali(2000, dir_destino=tmp_path)
    assert res is None


def test_descargar_extras_sin_seleccion(tmp_path: Path):
    """Verifica que descargar_extras retorne lista vacia si no se pide ninguno."""
    res = descarga.descargar_extras([2024], incluir_challengers=False, incluir_qualis=False, dir_destino=tmp_path)
    assert res == []


def test_descargar_extras_con_archivos_en_cache(tmp_path: Path):
    """Verifica que descargar_extras cargue los archivos solicitados si estan en cache."""
    pch = tmp_path / "2024_challenger.csv"
    pqu = tmp_path / "2024_atp_quali.csv"
    pch.write_text("tourney_id,tourney_name\n2024-C01,Test", encoding="utf-8")
    pqu.write_text("tourney_id,tourney_name\n2024-Q01,Test", encoding="utf-8")

    res = descarga.descargar_extras(
        [2024],
        incluir_challengers=True,
        incluir_qualis=True,
        forzar=False,
        dir_destino=tmp_path,
    )
    assert len(res) == 2
    assert pch in res
    assert pqu in res


def test_dataset_jugadores_con_tour_challenger_y_quali(tmp_path: Path):
    """Verifica que un jugador con 1 partido en Tour, 1 en Challenger y 1 en Quali sume 3 partidos."""
    df_tour = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-001", winner_id="P_ALL", loser_id="OPP1", match_num=1, tourney_date="20240101"),
    ])
    df_ch = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-C01", winner_id="P_ALL", loser_id="OPP2", match_num=1, tourney_date="20240102"),
    ])
    df_qu = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-Q01", winner_id="P_ALL", loser_id="OPP3", match_num=1, tourney_date="20240103"),
        # P_INSUF solo tiene 2 partidos (1 quali, 1 challenger)
        _partido_ejemplo(tourney_id="2024-Q01", winner_id="P_INSUF", loser_id="OPP4", match_num=2, tourney_date="20240103"),
    ])
    df_ch2 = pd.DataFrame([
        _partido_ejemplo(tourney_id="2024-C02", winner_id="P_INSUF", loser_id="OPP5", match_num=1, tourney_date="20240104"),
    ])

    ptour = tmp_path / "2024.csv"
    pch = tmp_path / "2024_challenger.csv"
    pqu = tmp_path / "2024_atp_quali.csv"
    df_tour.to_csv(ptour, index=False)
    pd.concat([df_ch, df_ch2]).to_csv(pch, index=False)
    df_qu.to_csv(pqu, index=False)

    consolidado = consolidar.consolidar([ptour, pch, pqu])
    df_norm = dataset_jugadores.normalizar_superficies(consolidado)
    df_norm = dataset_jugadores._agregar_sets_games(df_norm)
    participaciones = dataset_jugadores.unificar_participaciones(df_norm)
    totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
    tasas = dataset_jugadores.agregar_tasas_y_cobertura(totales)

    assert totales.loc["P_ALL", "partidos-totales"] == 3
    assert totales.loc["P_INSUF", "partidos-totales"] == 2
    assert tasas.loc["P_ALL", "tasa-victorias-totales"] == pytest.approx(1.0)
    assert tasas.loc["P_ALL", "tasa-aces-totales"] == pytest.approx(5 / 60)
    assert tasas.loc["P_ALL", "cobertura-saque-totales"] == pytest.approx(1.0)
    assert tasas.loc["P_ALL", "cobertura-resto-totales"] == pytest.approx(1.0)

    filtrado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=3)
    assert "P_ALL" in filtrado.index
    assert "P_INSUF" not in filtrado.index

