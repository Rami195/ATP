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


def descargar_anios(
    desde: int,
    hasta: int,
    forzar: bool = False,
    dir_destino: Path | None = None,
) -> list[Path]:
    """Baja un CSV por temporada. Devuelve las rutas efectivamente disponibles."""
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Descargando temporadas {desde}-{hasta} desde TML-Database")
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
            "si el repositorio TML-Database sigue publico."
        )

    print(f"      {len(disponibles)} temporadas disponibles\n")
    return disponibles


def descargar_auxiliares(forzar: bool = False, dir_destino: Path | None = None) -> dict[str, Path]:
    """Baja las tablas auxiliares (biografias y torneos en curso)."""
    dir_destino = dir_destino or config.DIR_CRUDO
    dir_destino.mkdir(parents=True, exist_ok=True)

    resultado: dict[str, Path] = {}
    for clave, archivo in (
        ("bios", config.ARCHIVO_BIOS),
        ("en_curso", config.ARCHIVO_EN_CURSO),
    ):
        destino = dir_destino / archivo
        _, mensaje = _descargar_archivo(f"{config.BASE_TML}/{archivo}", destino, forzar)
        print(mensaje)
        if destino.exists():
            resultado[clave] = destino

    print()
    return resultado
