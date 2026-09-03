"""Configuracion central del pipeline ATP, adaptada para correr dentro de Airflow.

Es la misma configuracion que proyecto-atp/src/config.py: unica diferencia,
las rutas apuntan a include/output dentro del contenedor, con la misma
separacion bronce/plata que se usa en el resto de la materia (ver
fifa_ingest.py de la Unidad 1).
"""

from pathlib import Path

# --- Rutas -----------------------------------------------------------------
# BRONCE: los CSV de temporada tal como los devuelve la fuente, sin interpretar.
# PLATA: el dataset consolidado, un partido por fila, ya tipado.
OUTPUT_DIR = Path("/usr/local/airflow/include/output")
DIR_CRUDO = OUTPUT_DIR / "bronze"
DIR_PROCESADO = OUTPUT_DIR / "silver"

# --- Fuente principal: TML-Database --------------------------------------
# Reemplazo vivo del repo JeffSackmann/tennis_atp (dado de baja: devuelve 404).
# Mismo esquema de columnas + la columna `indoor`.
BASE_TML = "https://raw.githubusercontent.com/Tennismylife/TML-Database/master"

ANIO_MIN_DISPONIBLE = 1968
ANIO_DESDE_DEFECTO = 2000
ANIO_HASTA_DEFECTO = 2025  # 2026 esta incompleto en la fuente, ver README

# Tabla de biografias de jugadores (7.643 filas): altura, peso, mano, reves,
# entrenadores, lugar de nacimiento. Se joinea por id de jugador.
ARCHIVO_BIOS = "ATP_Database.csv"

# Torneos en curso, fuera de los CSV anuales.
ARCHIVO_EN_CURSO = "ongoing_tourneys.csv"

# --- Descarga ------------------------------------------------------------
USER_AGENT = "proyecto-integrador-utnfrm-cienciadatos/1.0 (uso academico)"
TIMEOUT_SEG = 60
REINTENTOS = 3
ESPERA_ENTRE_REINTENTOS_SEG = 2.0
PAUSA_ENTRE_DESCARGAS_SEG = 0.3  # cortesia con el servidor

# --- Modelado (no se usa en la Entrega 1, queda para consistencia con
# proyecto-atp/src/config.py y las entregas siguientes) ---------------------
SEMILLA = 42
MIN_HISTORIAL_DEFECTO = 10

# Orden de rondas: desempata partidos del mismo torneo (misma tourney_date).
# Sin esto, las features historicas filtran resultados entre rondas del mismo
# torneo, que es una fuga de datos silenciosa.
ORDEN_RONDA = {
    "Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3,
    "ER": 4, "BR": 5, "RR": 6,
    "R128": 10, "R64": 11, "R32": 12, "R16": 13,
    "QF": 14, "SF": 15, "F": 16,
}
ORDEN_RONDA_DEFECTO = 9

# Columnas de estadisticas de partido, por lado (w_ = winner, l_ = loser).
STATS_PARTIDO = [
    "ace", "df", "svpt", "1stIn", "1stWon", "2ndWon",
    "SvGms", "bpSaved", "bpFaced",
]
