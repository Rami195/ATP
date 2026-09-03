"""Pipeline ATP - Proyecto Integrador Ciencia de Datos 2026 (UTN FRM).

Descarga automatizada -> consolidacion -> dataset de modelado, sin
intervencion humana en ningun paso.

Uso:
    python pipeline.py                          # 2000-2025
    python pipeline.py --desde 2010 --hasta 2025
    python pipeline.py --forzar-descarga        # ignora la cache local
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src import config, consolidar, descarga, features


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pipeline de datos ATP a nivel partido.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--desde", type=int, default=config.ANIO_DESDE_DEFECTO,
                   help="primera temporada a descargar")
    p.add_argument("--hasta", type=int, default=config.ANIO_HASTA_DEFECTO,
                   help="ultima temporada a descargar")
    p.add_argument("--forzar-descarga", action="store_true",
                   help="vuelve a bajar los CSV aunque esten en cache")
    p.add_argument("--min-historial", type=int, default=config.MIN_HISTORIAL_DEFECTO,
                   help="partidos previos minimos por jugador para marcar la fila como usable")
    p.add_argument("--semilla", type=int, default=config.SEMILLA,
                   help="semilla de la asignacion aleatoria A/B")
    p.add_argument("--salida", type=Path, default=config.DIR_PROCESADO,
                   help="carpeta donde escribir los datasets")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if args.desde < config.ANIO_MIN_DISPONIBLE:
        print(f"La fuente arranca en {config.ANIO_MIN_DISPONIBLE}.", file=sys.stderr)
        return 1
    if args.desde > args.hasta:
        print("--desde no puede ser mayor que --hasta.", file=sys.stderr)
        return 1

    arranque = time.perf_counter()
    args.salida.mkdir(parents=True, exist_ok=True)

    print("=" * 66)
    print("  PIPELINE ATP  ·  Proyecto Integrador Ciencia de Datos 2026")
    print("=" * 66)

    # 1 - Descarga
    rutas = descarga.descargar_anios(args.desde, args.hasta, args.forzar_descarga)
    auxiliares = descarga.descargar_auxiliares(args.forzar_descarga)

    # 2 - Consolidacion
    partidos = consolidar.consolidar(rutas)
    informe = consolidar.informe_calidad(partidos)

    # 3 - Formato jugador-partido + historial
    largo = features.a_formato_largo(partidos)
    largo = features.agregar_historial(largo)

    # 4 - Dataset de modelado
    dataset = features.a_formato_ab(largo, args.semilla, args.min_historial)
    reducido = features.reducir_columnas(dataset)
    features.control_de_fuga(dataset)

    # --- Escritura -------------------------------------------------------
    salidas = {
        "partidos_consolidado.csv": partidos,
        "jugador_partido.csv": largo,
        "dataset_modelado.csv": dataset,
        "dataset_reducido.csv": reducido,
        "informe_calidad.csv": informe,
    }
    bios = consolidar.cargar_bios(auxiliares.get("bios"))
    if bios is not None:
        salidas["jugadores_bio.csv"] = bios

    print("      Escribiendo resultados:")
    for nombre, df in salidas.items():
        ruta = args.salida / nombre
        df.to_csv(ruta, index=False, encoding="utf-8")
        mb = ruta.stat().st_size / 1024 / 1024
        print(f"        {nombre:<28} {len(df):>8,} filas  {len(df.columns):>3} cols  {mb:>6.1f} MB")

    print(f"\n      Listo en {time.perf_counter() - arranque:.1f} s")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
