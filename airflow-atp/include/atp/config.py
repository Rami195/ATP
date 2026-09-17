"""Configuracion central del pipeline ATP en Airflow."""

from pathlib import Path

# --- Capas -----------------------------------------------------------------
OUTPUT_DIR = Path("/usr/local/airflow/include/output")
DIR_CRUDO = OUTPUT_DIR / "bronze"
DIR_PROCESADO = OUTPUT_DIR / "silver"
DIR_ANALITICO = OUTPUT_DIR / "gold"

# --- Fuente ----------------------------------------------------------------
BASE_TML = "https://stats.tennismylife.org/data"
ANIO_MIN_DISPONIBLE = 1968
ANIO_DESDE_DEFECTO = 2000
ANIO_HASTA_DEFECTO = 2025

ARCHIVO_BIOS = "ATP_Database.csv"
ARCHIVO_EN_CURSO = "ongoing_tourneys.csv"

# --- Descarga --------------------------------------------------------------
USER_AGENT = "proyecto-integrador-utnfrm-cienciadatos/1.0 (uso academico)"
TIMEOUT_SEG = 60
REINTENTOS = 3
ESPERA_ENTRE_REINTENTOS_SEG = 2.0
PAUSA_ENTRE_DESCARGAS_SEG = 0.3

# --- Parametros analiticos -------------------------------------------------
SEMILLA = 42
MIN_PARTIDOS_ESTILO = 20
MIN_HISTORIAL_PREMATCH = 20
MIN_PARTIDOS_SUPERFICIE = 10

# Orden de ronda para preservar secuencia temporal dentro de un torneo.
ORDEN_RONDA = {
    "Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3,
    "ER": 4, "BR": 5, "RR": 6,
    "R128": 10, "R64": 11, "R32": 12, "R16": 13,
    "QF": 14, "SF": 15, "F": 16,
}
ORDEN_RONDA_DEFECTO = 9

STATS_PARTIDO = [
    "ace", "df", "svpt", "1stIn", "1stWon", "2ndWon",
    "SvGms", "bpSaved", "bpFaced",
]
