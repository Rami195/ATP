"""Paso 1 del pipeline: descarga automatizada de la fuente cruda.

Sin intervencion humana (criterio 4 del kit de arranque). Usa solo stdlib
para que la descarga no dependa de paquetes externos.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config


def _descargar_archivo(url: str, destino: Path, forzar: bool = False) -> tuple[bool, str]:
    """Descarga `url` a `destino`. Devuelve (se_descargo, mensaje).

    Si el archivo ya existe y `forzar` es False, no vuelve a pedirlo: el
    pipeline es re-ejecutable sin castigar al servidor.
    """
    if destino.exists() and not forzar:
        kb = destino.stat().st_size / 1024
        return False, f"  cache   {destino.name:<24} ({kb:,.0f} KB)"

    ultimo_error = None
    for intento in range(1, config.REINTENTOS + 1):
        try:
            pedido = urllib.request.Request(
                url, headers={"User-Agent": config.USER_AGENT}
            )
            with urllib.request.urlopen(pedido, timeout=config.TIMEOUT_SEG) as resp:
                contenido = resp.read()

            if not contenido:
                raise ValueError("respuesta vacia")

            destino.parent.mkdir(parents=True, exist_ok=True)
            # Escritura atomica: si se corta la descarga no queda un CSV
            # truncado que despues rompa la consolidacion en silencio.
            temporal = destino.with_suffix(destino.suffix + ".parcial")
            temporal.write_bytes(contenido)
            temporal.replace(destino)

            kb = len(contenido) / 1024
            return True, f"  OK      {destino.name:<24} ({kb:,.0f} KB)"

        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            ultimo_error = exc
            if intento < config.REINTENTOS:
                time.sleep(config.ESPERA_ENTRE_REINTENTOS_SEG * intento)

    return False, f"  FALLO   {destino.name:<24} ({ultimo_error})"


def descargar_temporada(
    anio: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> Path:
    """Descarga (o reusa la cache de) el CSV de una unica temporada ATP Tour.

    Es la version de `descargar_anios` para una tarea mapeada de Airflow: cada
    instancia de `land_bronze` baja un anio, asi que necesita esta unidad mas
    chica en lugar del loop completo.
    """
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)
    destino = dir_destino / f"{anio}.csv"

    _, mensaje = _descargar_archivo(f"{config.BASE_TML}/{anio}.csv", destino, forzar)
    print(mensaje)

    if not destino.exists():
        raise RuntimeError(f"No se pudo descargar la temporada {anio}: {mensaje}")
    return destino


def descargar_temporada_challenger(
    anio: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> Path:
    """Descarga (o reusa la cache de) el CSV de una unica temporada Challenger.

    Es la version para la tarea mapeada `land_bronze_challenger` en Airflow.
    """
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)
    nombre_archivo = f"{anio}_challenger.csv"
    destino = dir_destino / nombre_archivo

    _, mensaje = _descargar_archivo(f"{config.BASE_TML}/{nombre_archivo}", destino, forzar)
    print(mensaje)

    if not destino.exists():
        raise RuntimeError(f"No se pudo descargar la temporada challenger {anio}: {mensaje}")
    return destino


def descargar_temporada_quali(
    anio: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> Path | None:
    """Descarga (o reusa la cache de) el CSV de una temporada ATP Qualifying (disponible desde 2007).

    Es la version para la tarea mapeada `land_bronze_quali` en Airflow.
    """
    if anio < config.ANIO_MIN_QUALI:
        print(f"  INFO    Qualifying no disponible para el anio {anio} (disponible desde {config.ANIO_MIN_QUALI})")
        return None

    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)
    nombre_archivo = f"{anio}_atp_quali.csv"
    destino = dir_destino / nombre_archivo
    url = f"{config.BASE_TML}/atp_quali/{nombre_archivo}"

    _, mensaje = _descargar_archivo(url, destino, forzar)
    print(mensaje)

    if not destino.exists():
        raise RuntimeError(f"No se pudo descargar la temporada qualifying {anio}: {mensaje}")
    return destino


def descargar_anios_quali(
    desde: int,
    hasta: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> list[Path]:
    """Baja un CSV por temporada ATP Qualifying. Devuelve las rutas efectivamente disponibles."""
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Descargando temporadas {desde}-{hasta} Qualifying desde stats.tennismylife.org")
    disponibles: list[Path] = []

    for anio in range(max(desde, config.ANIO_MIN_QUALI), hasta + 1):
        destino = descargar_temporada_quali(anio, forzar=forzar, dir_destino=dir_destino)
        if destino and destino.exists():
            disponibles.append(destino)
        time.sleep(config.PAUSA_ENTRE_DESCARGAS_SEG)

    return disponibles


def descargar_anios(
    desde: int,
    hasta: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> list[Path]:
    """Baja un CSV por temporada ATP Tour. Devuelve las rutas efectivamente disponibles."""
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Descargando temporadas {desde}-{hasta} ATP Tour desde stats.tennismylife.org")
    disponibles: list[Path] = []

    for anio in range(desde, hasta + 1):
        destino = dir_destino / f"{anio}.csv"
        descargado, mensaje = _descargar_archivo(
            f"{config.BASE_TML}/{anio}.csv", destino, forzar
        )
        print(mensaje)
        if destino.exists():
            disponibles.append(destino)
        if descargado:
            time.sleep(config.PAUSA_ENTRE_DESCARGAS_SEG)

    if not disponibles:
        raise RuntimeError(
            "No se pudo descargar ninguna temporada. Revisa la conexion o "
            "si stats.tennismylife.org sigue disponible."
        )

    print(f"      {len(disponibles)} temporadas disponibles\n")
    return disponibles


def descargar_anios_challenger(
    desde: int,
    hasta: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> list[Path]:
    """Baja un CSV por temporada Challenger. Devuelve las rutas efectivamente disponibles."""
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Descargando temporadas {desde}-{hasta} Challenger desde stats.tennismylife.org")
    disponibles: list[Path] = []

    for anio in range(desde, hasta + 1):
        nombre_archivo = f"{anio}_challenger.csv"
        destino = dir_destino / nombre_archivo
        descargado, mensaje = _descargar_archivo(
            f"{config.BASE_TML}/{nombre_archivo}", destino, forzar
        )
        print(mensaje)
        if destino.exists():
            disponibles.append(destino)
        if descargado:
            time.sleep(config.PAUSA_ENTRE_DESCARGAS_SEG)

    if not disponibles:
        raise RuntimeError(
            "No se pudo descargar ninguna temporada challenger. Revisa la conexion o "
            "si stats.tennismylife.org sigue disponible."
        )

    print(f"      {len(disponibles)} temporadas challenger disponibles\n")
    return disponibles


def descargar_auxiliares(forzar: bool = False, dir_destino: Path | None = None) -> dict[str, Path]:
    """Baja las tablas auxiliares (biografias y torneos en curso)."""
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)

    resultado: dict[str, Path] = {}
    for clave, archivo in (
        ("bios", config.ARCHIVO_BIOS),
        ("en_curso", config.ARCHIVO_EN_CURSO),
        ("en_curso_challenger", config.ARCHIVO_EN_CURSO_CHALLENGER),
    ):
        destino = dir_destino / archivo
        _, mensaje = _descargar_archivo(f"{config.BASE_TML}/{archivo}", destino, forzar)
        print(mensaje)
        if destino.exists():
            resultado[clave] = destino

    print()
    return resultado
