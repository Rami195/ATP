"""Pruebas del modulo dataset_jugadores.

Usa DataFrames sinteticos para verificar las reglas del Silver de jugadores:
1. Exclusion de Carpet
2. Filtro de minimo 3 partidos
3. Una fila por jugador
4. Titulos correctos
5. Totales = suma de superficies
6. Tasas, devolucion y cobertura
"""

from __future__ import annotations

import pandas as pd
import pytest

from atp import consolidar, dataset_jugadores


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
    """Jugadores con menos de 3 partidos validos deben quedar excluidos."""

    def test_2_partidos_excluido(self):
        """Jugador con 2 partidos queda fuera."""
        partidos = _generar_partidos("X1", "Y1", 2, surface="Hard")
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=3)
        assert "X1" not in resultado.index

    def test_3_partidos_incluido(self):
        """Jugador con 3 partidos queda incluido."""
        partidos = _generar_partidos("X2", "Y2", 3, surface="Hard")
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=3)
        assert "X2" in resultado.index

    def test_filtro_por_defecto_es_3(self):
        """El valor por defecto de filtrar_minimo_partidos es 3."""
        partidos = (
            _generar_partidos("P_DOS", "OPP1", 2, surface="Hard")
            + _generar_partidos("P_TRES", "OPP2", 3, surface="Clay")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales)
        assert "P_DOS" not in resultado.index
        assert "P_TRES" in resultado.index

    def test_carpet_no_cuenta_para_minimo(self):
        """Un jugador con 4 partidos pero 2 de Carpet solo tiene 2 validos."""
        partidos = (
            _generar_partidos("Z1", "W1", 2, surface="Hard")
            + _generar_partidos("Z1", "W1", 2, surface="Carpet")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        resultado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=3)
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
    """Las proporciones no usan nombres ambiguos como pct o porcentaje."""

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


class TestTasasDevolucionYCobertura:
    """Verifica las features reutilizables que deben quedar en Silver."""

    def _stats_tres_partidos(self) -> pd.DataFrame:
        df = pd.DataFrame(_generar_partidos("P1", "P2", 3, surface="Hard"))
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        por_superficie = dataset_jugadores.calcular_estadisticas_por_superficie(participaciones)
        return dataset_jugadores.agregar_tasas_y_cobertura(
            totales.join(por_superficie, how="left")
        )

    def test_tasas_generales_se_calculan_desde_totales(self):
        stats = self._stats_tres_partidos()

        assert stats.loc["P1", "tasa-victorias-totales"] == pytest.approx(1.0)
        assert stats.loc["P1", "tasa-aces-totales"] == pytest.approx(15 / 180)
        assert stats.loc["P1", "tasa-dobles-faltas-totales"] == pytest.approx(6 / 180)
        assert stats.loc["P1", "tasa-primer-saque-dentro-totales"] == pytest.approx(120 / 180)
        assert stats.loc["P1", "efectividad-primer-saque-totales"] == pytest.approx(90 / 120)
        assert stats.loc["P1", "efectividad-segundo-saque-totales"] == pytest.approx(30 / 60)
        assert stats.loc["P1", "tasa-break-points-salvados-totales"] == pytest.approx(9 / 15)

    def test_devolucion_se_deriva_del_saque_del_rival(self):
        stats = self._stats_tres_partidos()

        assert stats.loc["P1", "puntos-resto-jugados-totales"] == 165
        assert stats.loc["P1", "puntos-resto-ganados-totales"] == 66
        assert stats.loc["P1", "tasa-puntos-ganados-resto-totales"] == pytest.approx(66 / 165)
        assert stats.loc["P1", "break-points-oportunidades-totales"] == 12
        assert stats.loc["P1", "break-points-convertidos-totales"] == 6
        assert stats.loc["P1", "tasa-break-points-convertidos-totales"] == pytest.approx(0.5)

    def test_cobertura_general_y_por_superficie(self):
        stats = self._stats_tres_partidos()

        assert stats.loc["P1", "cobertura-saque-totales"] == pytest.approx(1.0)
        assert stats.loc["P1", "cobertura-resto-totales"] == pytest.approx(1.0)
        assert stats.loc["P1", "tasa-aces-cemento"] == pytest.approx(15 / 180)
        assert stats.loc["P1", "tasa-puntos-ganados-resto-cemento"] == pytest.approx(66 / 165)
        assert stats.loc["P1", "cobertura-saque-cemento"] == pytest.approx(1.0)
        assert stats.loc["P1", "cobertura-resto-cemento"] == pytest.approx(1.0)

    def test_faltante_del_rival_no_inventa_estadisticas_de_resto(self):
        partidos = [
            _partido(
                winner_id="P1", loser_id="P2", match_num=i,
                l_svpt=float("nan"),
            )
            for i in range(1, 4)
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        stats = dataset_jugadores.agregar_tasas_y_cobertura(totales)

        assert stats.loc["P1", "partidos-validos-totales"] == 3
        assert stats.loc["P1", "partidos-validos-resto-totales"] == 0
        assert pd.isna(stats.loc["P1", "puntos-resto-ganados-totales"])
        assert stats.loc["P1", "cobertura-resto-totales"] == pytest.approx(0.0)
        assert pd.isna(stats.loc["P1", "tasa-puntos-ganados-resto-totales"])


# ---------------------------------------------------------------------------
# Prueba 7 — Validacion del dataset (minimo 3 partidos)
# ---------------------------------------------------------------------------

class TestValidarDataset:
    """Valida que validar_dataset verifique el minimo de 3 partidos."""

    def _armar_dataset_valido(self) -> pd.DataFrame:
        """Crea un dataset minimo valido para pasar todas las validaciones."""
        cols_titulos = {}
        for cat in dataset_jugadores.CATEGORIAS_TITULO.values():
            for suf in dataset_jugadores.SUFIJOS_SUPERFICIE:
                cols_titulos[f"titulos-{cat}-{suf}"] = [0]

        data = {
            "id-jugador": ["P001"],
            "nombre-jugador": ["Test Player"],
            "partidos-totales": [3],
            "partidos-validos-totales": [3],
            "victorias-totales": [2],
            "derrotas-totales": [1],
            "partidos-cemento": [3],
            "partidos-validos-cemento": [3],
            "victorias-cemento": [2],
            "derrotas-cemento": [1],
            "partidos-clay": [0],
            "partidos-validos-clay": [0],
            "victorias-clay": [0],
            "derrotas-clay": [0],
            "partidos-grass": [0],
            "partidos-validos-grass": [0],
            "victorias-grass": [0],
            "derrotas-grass": [0],
            **cols_titulos,
        }
        return pd.DataFrame(data)

    def test_dataset_con_3_partidos_valida_ok(self):
        df = self._armar_dataset_valido()
        dataset_jugadores.validar_dataset(df)

    def test_dataset_con_menos_de_3_partidos_falla(self):
        df = self._armar_dataset_valido()
        df["partidos-totales"] = [2]
        with pytest.raises(ValueError, match=r"\[filtro\] 1 jugadores con menos de 3 partidos"):
            dataset_jugadores.validar_dataset(df)


# ---------------------------------------------------------------------------
# Prueba 8 — Multiples archivos (Tour, Challenger, Quali)
# ---------------------------------------------------------------------------

class TestMultiplesArchivos:
    """Verifica que partidos de distintos archivos se acumulen para alcanzar el minimo de 3."""

    def test_jugador_con_partidos_en_quali_y_tour(self, tmp_path):
        """2 partidos en quali + 1 en ATP Tour -> 3 partidos en total -> se incluye."""
        # P_MULTI juega 2 partidos en Quali y 1 en ATP Tour
        df_quali = pd.DataFrame([
            _partido(tourney_id="2024-Q01", winner_id="P_MULTI", loser_id="OPP1", match_num=1),
            _partido(tourney_id="2024-Q01", winner_id="P_MULTI", loser_id="OPP2", match_num=2),
        ])
        df_tour = pd.DataFrame([
            _partido(tourney_id="2024-001", winner_id="P_MULTI", loser_id="OPP3", match_num=1),
            # OPP_SOLO_TOUR tiene solo 1 partido
            _partido(tourney_id="2024-001", winner_id="OPP4", loser_id="OPP_SOLO_TOUR", match_num=2),
        ])

        p_quali = tmp_path / "2024_atp_quali.csv"
        p_tour = tmp_path / "2024.csv"
        df_quali.to_csv(p_quali, index=False)
        df_tour.to_csv(p_tour, index=False)

        # Consolidar ambos archivos
        consolidado = consolidar.consolidar([p_tour, p_quali])
        
        # Procesar con dataset_jugadores
        df_norm = dataset_jugadores.normalizar_superficies(consolidado)
        df_norm = dataset_jugadores._agregar_sets_games(df_norm)
        participaciones = dataset_jugadores.unificar_participaciones(df_norm)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        
        # P_MULTI jugo 3 partidos en total (2 quali + 1 tour)
        assert totales.loc["P_MULTI", "partidos-totales"] == 3
        # OPP_SOLO_TOUR jugo solo 1 partido
        assert totales.loc["OPP_SOLO_TOUR", "partidos-totales"] == 1

        filtrado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=3)
        assert "P_MULTI" in filtrado.index
        assert "OPP_SOLO_TOUR" not in filtrado.index


# ---------------------------------------------------------------------------
# Prueba 9 — Proteccion contra NaN y preservacion de 0 reales
# ---------------------------------------------------------------------------

class TestProteccionValoresFaltantes:
    """Verifica el filtrado por partido y la preservacion estricta de NaN vs 0."""

    def test_nan_en_stats_excluye_partido_de_stats_saque(self):
        """Un partido con w_ace = NaN no debe sumar a aces ni a partidos validos."""
        partidos = [
            _partido(winner_id="P1", loser_id="P2", match_num=1, w_ace=5),
            _partido(
                winner_id="P1", loser_id="P2", match_num=2,
                w_ace=float("nan"), w_df=float("nan"), w_svpt=float("nan"),
                w_1stIn=float("nan"), w_1stWon=float("nan"), w_2ndWon=float("nan"),
                w_SvGms=float("nan"), w_bpSaved=float("nan"), w_bpFaced=float("nan"),
            ),
            _partido(winner_id="P1", loser_id="P2", match_num=3, w_ace=7),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["P1", "partidos-totales"] == 3
        assert totales.loc["P1", "partidos-validos-totales"] == 2
        assert totales.loc["P1", "aces-totales"] == 12  # 5 + 7, el NaN no suma 0 ni distorsiona

    def test_cero_legitimo_se_preserva_como_dato_valido(self):
        """Un partido con w_ace = 0 (y bloque completo) debe ser partido valido y sumar 0."""
        partidos = [
            _partido(winner_id="P1", loser_id="P2", match_num=1, w_ace=0),
            _partido(winner_id="P1", loser_id="P2", match_num=2, w_ace=4),
            _partido(winner_id="P1", loser_id="P2", match_num=3, w_ace=0),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["P1", "partidos-totales"] == 3
        assert totales.loc["P1", "partidos-validos-totales"] == 3
        assert totales.loc["P1", "aces-totales"] == 4

    def test_ejemplo_promedio_aces_4_partidos(self):
        """Ejemplo exacto del usuario: 5, 8, NaN, 6 -> promedio = 19 / 3 = 6.333."""
        partidos = [
            _partido(winner_id="P1", loser_id="P2", match_num=1, w_ace=5),
            _partido(winner_id="P1", loser_id="P2", match_num=2, w_ace=8),
            _partido(
                winner_id="P1", loser_id="P2", match_num=3,
                w_ace=float("nan"), w_df=float("nan"), w_svpt=float("nan"),
                w_1stIn=float("nan"), w_1stWon=float("nan"), w_2ndWon=float("nan"),
                w_SvGms=float("nan"), w_bpSaved=float("nan"), w_bpFaced=float("nan"),
            ),
            _partido(winner_id="P1", loser_id="P2", match_num=4, w_ace=6),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["P1", "partidos-totales"] == 4
        assert totales.loc["P1", "partidos-validos-totales"] == 3
        assert totales.loc["P1", "aces-totales"] == 19
        promedio_aces = totales.loc["P1", "aces-totales"] / totales.loc["P1", "partidos-validos-totales"]
        assert pytest.approx(promedio_aces, 0.01) == 6.33

    def test_jugador_sin_estadisticas_tiene_nan_en_saque(self):
        """Un jugador con 3 partidos donde ninguno tiene stats de saque queda con NaN (no 0)."""
        partidos = [
            _partido(
                winner_id="P_NO_STATS", loser_id="P2", match_num=i,
                w_ace=float("nan"), w_df=float("nan"), w_svpt=float("nan"),
                w_1stIn=float("nan"), w_1stWon=float("nan"), w_2ndWon=float("nan"),
                w_SvGms=float("nan"), w_bpSaved=float("nan"), w_bpFaced=float("nan"),
            )
            for i in range(1, 4)
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["P_NO_STATS", "partidos-totales"] == 3
        assert totales.loc["P_NO_STATS", "partidos-validos-totales"] == 0
        assert pd.isna(totales.loc["P_NO_STATS", "aces-totales"])

    def test_bloque_parcial_incompleto_se_descarta(self):
        """Si falta una sola estadistica del bloque (ej. w_svpt = NaN), se descarta el partido de las stats."""
        partidos = [
            _partido(winner_id="P1", loser_id="P2", match_num=1, w_ace=5, w_svpt=float("nan")),
            _partido(winner_id="P1", loser_id="P2", match_num=2, w_ace=4, w_svpt=60),
            _partido(winner_id="P1", loser_id="P2", match_num=3, w_ace=3, w_svpt=55),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["P1", "partidos-totales"] == 3
        assert totales.loc["P1", "partidos-validos-totales"] == 2
        # El primer partido tenia w_ace=5 pero w_svpt=NaN -> no cuenta, total = 4 + 3 = 7
        assert totales.loc["P1", "aces-totales"] == 7

    def test_separacion_estricta_ganador_perdedor(self):
        """Ganador y perdedor reciben exclusivamente sus estadisticas w_* y l_*."""
        partidos = [
            _partido(
                winner_id="WINNER", loser_id="LOSER", match_num=1,
                w_ace=10, l_ace=2,
            ),
            _partido(
                winner_id="WINNER", loser_id="LOSER", match_num=2,
                w_ace=8, l_ace=1,
            ),
            _partido(
                winner_id="WINNER", loser_id="LOSER", match_num=3,
                w_ace=12, l_ace=3,
            ),
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["WINNER", "victorias-totales"] == 3
        assert totales.loc["WINNER", "derrotas-totales"] == 0
        assert totales.loc["WINNER", "aces-totales"] == 30

        assert totales.loc["LOSER", "victorias-totales"] == 0
        assert totales.loc["LOSER", "derrotas-totales"] == 3
        assert totales.loc["LOSER", "aces-totales"] == 6

    def test_consistencia_partidos_validos_superficies(self):
        """partidos-validos-totales debe ser igual a la suma por superficie."""
        partidos = (
            _generar_partidos("M1", "M2", 5, surface="Hard")
            + _generar_partidos("M1", "M3", 3, surface="Clay")
            + _generar_partidos("M1", "M4", 2, surface="Grass")
        )
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)

        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)
        por_sup = dataset_jugadores.calcular_estadisticas_por_superficie(participaciones)
        stats = totales.join(por_sup, how="left").fillna(0)

        assert stats.loc["M1", "partidos-validos-totales"] == 10
        suma_validos = (
            stats.loc["M1", "partidos-validos-cemento"]
            + stats.loc["M1", "partidos-validos-clay"]
            + stats.loc["M1", "partidos-validos-grass"]
        )
        assert stats.loc["M1", "partidos-validos-totales"] == suma_validos

    def test_jugador_sin_stats_protegidas_es_excluido_por_filtro(self):
        """Un jugador con 5 partidos pero 0 partidos validos con stats debe ser excluido."""
        partidos = [
            _partido(
                winner_id="P_NO_STATS", loser_id="P_VALID", match_num=i,
                w_ace=float("nan"), w_df=float("nan"), w_svpt=float("nan"),
                w_1stIn=float("nan"), w_1stWon=float("nan"), w_2ndWon=float("nan"),
                w_SvGms=float("nan"), w_bpSaved=float("nan"), w_bpFaced=float("nan"),
                l_ace=5, l_df=2, l_svpt=60, l_1stIn=40, l_1stWon=30, l_2ndWon=10, l_SvGms=10, l_bpSaved=2, l_bpFaced=4,
            )
            for i in range(1, 6)
        ]
        df = pd.DataFrame(partidos)
        df = dataset_jugadores.normalizar_superficies(df)
        df = dataset_jugadores._agregar_sets_games(df)
        participaciones = dataset_jugadores.unificar_participaciones(df)
        totales = dataset_jugadores.calcular_estadisticas_totales(participaciones)

        assert totales.loc["P_NO_STATS", "partidos-totales"] == 5
        assert totales.loc["P_NO_STATS", "partidos-validos-totales"] == 0
        assert totales.loc["P_VALID", "partidos-totales"] == 5
        assert totales.loc["P_VALID", "partidos-validos-totales"] == 5

        filtrado = dataset_jugadores.filtrar_minimo_partidos(totales, minimo=3)
        assert "P_VALID" in filtrado.index
        assert "P_NO_STATS" not in filtrado.index

    def test_informe_calidad_incluye_todas_las_columnas(self):
        """El informe de calidad debe contener exactamente todas las columnas del dataset."""
        df_dummy = pd.DataFrame({
            "col1": [1, 2, float("nan")],
            "col2": ["a", "b", "c"],
            "col3": [float("nan"), float("nan"), float("nan")],
            "col4": [10.5, 20.0, 30.5],
        })
        informe = dataset_jugadores.informe_calidad_jugadores(df_dummy)
        assert set(informe["columna"]) == set(df_dummy.columns)
        assert len(informe) == len(df_dummy.columns)
        
        # Verificar conteo de nulos
        fila_col1 = informe[informe["columna"] == "col1"].iloc[0]
        assert fila_col1["nulos"] == 1
        assert fila_col1["pct_nulos"] == 33.33

        fila_col3 = informe[informe["columna"] == "col3"].iloc[0]
        assert fila_col3["nulos"] == 3
        assert fila_col3["pct_nulos"] == 100.0



