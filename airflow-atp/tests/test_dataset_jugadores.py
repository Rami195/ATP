"""Pruebas del modulo dataset_jugadores.

Usa DataFrames sinteticos para verificar las 6 reglas obligatorias:
1. Exclusion de Carpet
2. Filtro de minimo 20 partidos
3. Una fila por jugador
4. Titulos correctos
5. Totales = suma de superficies
6. Sin porcentajes
"""

from __future__ import annotations

import pandas as pd
import pytest

from atp import dataset_jugadores


# ---------------------------------------------------------------------------
# Helpers para construir datos sinteticos
# ---------------------------------------------------------------------------

def _partido(
    tourney_id: str = "2024-001",
    tourney_name: str = "TestOpen",
    surface: str = "Hard",
    tourney_level: str = "250",
    tourney_date: str = "20240101",
    match_num: int = 1,
    winner_id: str = "P001",
    winner_name: str = "Jugador Uno",
    loser_id: str = "P002",
    loser_name: str = "Jugador Dos",
    round_: str = "R32",
    score: str = "6-3 6-4",
    minutes: float = 90.0,
    **stats,
) -> dict:
    """Crea un dict con la estructura de una fila del consolidado."""
    base_stats = {
        "w_ace": 5, "w_df": 2, "w_svpt": 60, "w_1stIn": 40,
        "w_1stWon": 30, "w_2ndWon": 10, "w_SvGms": 10, "w_bpSaved": 3, "w_bpFaced": 5,
        "l_ace": 3, "l_df": 3, "l_svpt": 55, "l_1stIn": 35,
        "l_1stWon": 25, "l_2ndWon": 8, "l_SvGms": 9, "l_bpSaved": 2, "l_bpFaced": 4,
    }
    base_stats.update(stats)
    return {
        "tourney_id": tourney_id,
        "tourney_name": tourney_name,
        "surface": surface,
        "tourney_level": tourney_level,
        "tourney_date": tourney_date,
        "match_num": match_num,
        "winner_id": winner_id,
        "winner_name": winner_name,
        "winner_hand": "R",
        "winner_ht": 185,
        "winner_ioc": "ARG",
        "winner_age": 25.0,
        "loser_id": loser_id,
        "loser_name": loser_name,
        "loser_hand": "R",
        "loser_ht": 180,
        "loser_ioc": "USA",
        "loser_age": 27.0,
        "round": round_,
        "score": score,
        "best_of": 3,
        "minutes": minutes,
        "indoor": "I",
        "draw_size": 32,
        "winner_seed": None,
        "loser_seed": None,
        "winner_entry": None,
        "loser_entry": None,
        "winner_rank": 10,
        "winner_rank_points": 2000,
        "loser_rank": 50,
        "loser_rank_points": 800,
        "anio_archivo": 2024,
        "fecha": "2024-01-01",
        "anio": 2024,
        "orden_ronda": 12,
        "id_partido": f"{tourney_id}-{match_num}",
        **base_stats,
    }


def _generar_partidos(
    jugador_id: str,
    oponente_id: str,
    n: int,
    surface: str = "Hard",
    tourney_level: str = "250",
    incluir_final: bool = False,
) -> list[dict]:
    """Genera n partidos donde jugador_id gana todos."""
    partidos = []
    for i in range(n):
        es_final = incluir_final and i == n - 1
        partidos.append(_partido(
            tourney_id=f"T-{surface[:2]}-{jugador_id}-{i}",
            surface=surface,
            tourney_level=tourney_level,
            match_num=i + 1,
            winner_id=jugador_id,
            loser_id=oponente_id,
            round_="F" if es_final else "R32",
            score="6-3 6-4",
        ))
    return partidos


# ---------------------------------------------------------------------------
# Prueba 1 — Carpet excluido
# ---------------------------------------------------------------------------

class TestCarpetExcluido:
    """Partidos en Carpet no deben aparecer en ninguna estadistica."""

    def test_carpet_no_en_totales(self):
        """Partidos Carpet no se cuentan en partidos-totales."""
        partidos = (
            _generar_partidos("A1", "B1", 20, surface="Hard")
            + _generar_partidos("A1", "B1", 10, surface="Carpet")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        # A1 gano 20 en Hard, 10 en Carpet. Solo deben contar los 20 Hard.
        assert totales.loc["A1", "partidos-totales"] == 20

    def test_sin_columnas_carpet(self):
        """No deben existir columnas con 'carpet' en el nombre."""
        partidos = (
            _generar_partidos("A1", "B1", 20, surface="Hard")
            + _generar_partidos("A1", "B1", 5, surface="Carpet")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        por_sup = dataset_jugadores.calcular_estadisticas_por_superficie(participaciones)
        cols_carpet = [c for c in por_sup.columns if "carpet" in c.lower()]
        assert cols_carpet == [], f"Columnas carpet encontradas: {cols_carpet}"

    def test_titulos_sin_carpet(self):
        """Titulos en Carpet no deben contarse."""
        partidos = (
            _generar_partidos("A1", "B1", 1, surface="Hard", tourney_level="250", incluir_final=True)
            + _generar_partidos("A1", "B1", 1, surface="Carpet", tourney_level="250", incluir_final=True)
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        titulos = dataset_jugadores.calcular_titulos_por_superficie(df)

        if "A1" in titulos.index:
            assert titulos.loc["A1", "titulos-250-cemento"] == 1
            cols_carpet = [c for c in titulos.columns if "carpet" in c.lower()]
            assert cols_carpet == []
        else:
            # Si no hay titulos, no debe haber columnas carpet
            cols_carpet = [c for c in titulos.columns if "carpet" in c.lower()]
            assert cols_carpet == []


# ---------------------------------------------------------------------------
# Prueba 2 — Minimo de partidos
# ---------------------------------------------------------------------------

class TestMinimoPartidos:
    """Jugadores con menos de 20 partidos validos deben quedar excluidos."""

    def test_19_partidos_excluido(self):
        """Jugador con 19 partidos queda fuera."""
        partidos = _generar_partidos("X1", "Y1", 19, surface="Hard")
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=20)
        assert "X1" not in resultado.index

    def test_20_partidos_incluido(self):
        """Jugador con 20 partidos queda incluido."""
        partidos = _generar_partidos("X2", "Y2", 20, surface="Hard")
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=20)
        assert "X2" in resultado.index

    def test_carpet_no_cuenta_para_minimo(self):
        """Un jugador con 25 partidos pero 10 de Carpet solo tiene 15 validos."""
        partidos = (
            _generar_partidos("Z1", "W1", 15, surface="Hard")
            + _generar_partidos("Z1", "W1", 10, surface="Carpet")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=20)
        assert "Z1" not in resultado.index


# ---------------------------------------------------------------------------
# Prueba 3 — Una fila por jugador
# ---------------------------------------------------------------------------

class TestUnaFilaPorJugador:
    """El dataset final no debe tener IDs duplicados."""

    def test_sin_duplicados(self):
        """Cada jugador aparece exactamente una vez."""
        partidos = (
            _generar_partidos("J1", "J2", 25, surface="Hard")
            + _generar_partidos("J1", "J3", 10, surface="Clay")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        # J1 aparece en muchos partidos como ganador, no debe duplicarse
        assert totales.index.is_unique
        assert totales.index.duplicated().sum() == 0


# ---------------------------------------------------------------------------
# Prueba 4 — Titulos
# ---------------------------------------------------------------------------

class TestTitulos:
    """Verificar que los titulos se cuentan correctamente."""

    def test_titulo_250_cemento(self):
        """Ganador de una final ATP 250 en Hard: titulos-250-cemento == 1."""
        partidos = [
            _partido(
                tourney_id="T-250-HARD",
                surface="Hard",
                tourney_level="250",
                winner_id="CHAMP",
                loser_id="RUNNER",
                round_="F",
                match_num=1,
            ),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        titulos = dataset_jugadores.calcular_titulos_por_superficie(df)

        assert "CHAMP" in titulos.index
        assert titulos.loc["CHAMP", "titulos-250-cemento"] == 1

    def test_titulo_no_en_otra_superficie(self):
        """Titulo en Hard no se cuenta en Clay ni Grass."""
        partidos = [
            _partido(
                tourney_id="T-250-HARD",
                surface="Hard",
                tourney_level="250",
                winner_id="CHAMP",
                loser_id="RUNNER",
                round_="F",
            ),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        titulos = dataset_jugadores.calcular_titulos_por_superficie(df)

        assert titulos.loc["CHAMP", "titulos-250-clay"] == 0
        assert titulos.loc["CHAMP", "titulos-250-grass"] == 0

    def test_perdedor_no_tiene_titulo(self):
        """El perdedor de la final no debe tener titulo."""
        partidos = [
            _partido(
                tourney_id="T-250-HARD",
                surface="Hard",
                tourney_level="250",
                winner_id="CHAMP",
                loser_id="RUNNER",
                round_="F",
            ),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        titulos = dataset_jugadores.calcular_titulos_por_superficie(df)

        if "RUNNER" in titulos.index:
            assert titulos.loc["RUNNER", "titulos-250-cemento"] == 0
        # Si RUNNER no esta, tampoco tiene titulo — OK

    def test_victoria_no_final_no_es_titulo(self):
        """Una victoria en R32 no cuenta como titulo."""
        partidos = [
            _partido(
                tourney_id="T-250-HARD",
                surface="Hard",
                tourney_level="250",
                winner_id="PLAYER",
                loser_id="OPP",
                round_="R32",
            ),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        titulos = dataset_jugadores.calcular_titulos_por_superficie(df)

        if "PLAYER" in titulos.index:
            assert titulos.loc["PLAYER", "titulos-250-cemento"] == 0


# ---------------------------------------------------------------------------
# Prueba 5 — Totales = suma de superficies
# ---------------------------------------------------------------------------

class TestTotalesConsistentes:
    """partidos-totales debe ser igual a la suma de partidos por superficie."""

    def test_totales_iguales_suma_superficies(self):
        partidos = (
            _generar_partidos("M1", "M2", 15, surface="Hard")
            + _generar_partidos("M1", "M3", 10, surface="Clay")
            + _generar_partidos("M1", "M4", 5, surface="Grass")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)

        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        por_sup = dataset_jugadores.calcular_estadisticas_por_superficie(participaciones)

        stats = totales.join(por_sup, how="left").fillna(0)

        # M1 gano todos, asi que tiene 30 partidos como ganador
        assert stats.loc["M1", "partidos-totales"] == 30
        suma = (
            stats.loc["M1", "partidos-cemento"]
            + stats.loc["M1", "partidos-clay"]
            + stats.loc["M1", "partidos-grass"]
        )
        assert stats.loc["M1", "partidos-totales"] == suma

        # Verificar tambien victorias
        suma_vic = (
            stats.loc["M1", "victorias-cemento"]
            + stats.loc["M1", "victorias-clay"]
            + stats.loc["M1", "victorias-grass"]
        )
        assert stats.loc["M1", "victorias-totales"] == suma_vic


# ---------------------------------------------------------------------------
# Prueba 6 — Sin porcentajes
# ---------------------------------------------------------------------------

class TestSinPorcentajes:
    """No debe haber columnas que representen porcentajes."""

    def test_sin_columnas_porcentaje(self):
        partidos = _generar_partidos("P1", "P2", 25, surface="Hard")
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        por_sup = dataset_jugadores.calcular_estadisticas_por_superficie(participaciones)
        stats = totales.join(por_sup, how="left")

        todas_cols = list(stats.columns)
        cols_pct = [
            c for c in todas_cols
            if any(p in c.lower() for p in ("porcentaje", "pct", "percent", "ratio"))
        ]
        assert cols_pct == [], f"Columnas de porcentaje encontradas: {cols_pct}"
