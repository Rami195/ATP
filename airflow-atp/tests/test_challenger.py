"""Pruebas para la descarga y consolidacion de datos Challenger."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from atp import config, consolidar, descarga


def _partido_challenger(
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


def test_consolidar_archivos_challenger(tmp_path: Path):
    """Verifica que consolidar procese correctamente archivos con sufijo _challenger."""
    df_2023 = pd.DataFrame([
        _partido_challenger(tourney_id="2023-C01", match_num=1, tourney_date="20230501"),
        _partido_challenger(tourney_id="2023-C01", match_num=2, tourney_date="20230502"),
    ])
    df_2024 = pd.DataFrame([
        _partido_challenger(tourney_id="2024-C01", match_num=1, tourney_date="20240501"),
    ])

    p2023 = tmp_path / "2023_challenger.csv"
    p2024 = tmp_path / "2024_challenger.csv"
    df_2023.to_csv(p2023, index=False)
    df_2024.to_csv(p2024, index=False)

    consolidado = consolidar.consolidar([p2023, p2024])

    assert len(consolidado) == 3
    assert set(consolidado["anio_archivo"].unique()) == {2023, 2024}
    assert "id_partido" in consolidado.columns
    assert consolidado["id_partido"].is_unique


def test_descargar_temporada_challenger_cache(tmp_path: Path):
    """Verifica que descargar_temporada_challenger reusa el archivo si ya existe."""
    archivo_local = tmp_path / "2024_challenger.csv"
    archivo_local.write_text("tourney_id,tourney_name\n2024-C01,Test", encoding="utf-8")

    # Sin forzar: no debe intentar hacer requests
    res = descarga.descargar_temporada_challenger(2024, forzar=False, dir_destino=tmp_path)
    assert res == archivo_local
    assert res.exists()


def test_consolidar_archivos_quali(tmp_path: Path):
    """Verifica que consolidar procese correctamente archivos atp_quali."""
    df_2024 = pd.DataFrame([
        _partido_challenger(tourney_id="2024-Q01", match_num=1, tourney_date="20240101"),
        _partido_challenger(tourney_id="2024-Q01", match_num=2, tourney_date="20240102"),
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


def test_descargar_temporada_quali_cache(tmp_path: Path):
    """Verifica que descargar_temporada_quali reusa el archivo si ya existe."""
    archivo_local = tmp_path / "2024_atp_quali.csv"
    archivo_local.write_text("tourney_id,tourney_name\n2024-Q01,Test", encoding="utf-8")

    res = descarga.descargar_temporada_quali(2024, forzar=False, dir_destino=tmp_path)
    assert res == archivo_local
    assert res.exists()

