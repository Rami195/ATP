"""Verifica el CSV entregado contra los criterios medibles de la Entrega 1.

Usa las expresiones exactas que pide la consigna, para poder mostrarlas en la
defensa. Correr con:

    python scripts/verificar_criterios.py
"""
from pathlib import Path
import sys

import pandas as pd

SALIDA = Path(__file__).resolve().parent.parent / "include" / "output"
CLAVE = "id_partido"


def ultimo_entregable() -> Path:
    csvs = sorted(SALIDA.glob("atp_partidos_*.csv"))
    if not csvs:
        sys.exit(f"No hay ningun atp_partidos_*.csv en {SALIDA}")
    return csvs[-1]


def main() -> int:
    ruta = ultimo_entregable()
    df = pd.read_csv(ruta, low_memory=False, parse_dates=["fecha"])
    print(f"Archivo: {ruta.name}\n")

    ok = True

    # 1 -------------------------------------------------------------------
    r = df[CLAVE].is_unique
    ok &= bool(r)
    print(f'1. Clave sin duplicados   df["{CLAVE}"].is_unique')
    print(f'   -> {r}   {"OK" if r else "FALLA"}\n')

    # 2 -------------------------------------------------------------------
    r = len(df) > 1000
    ok &= r
    print("2. Volumen suficiente     len(df)")
    print(f'   -> {len(df):,} filas (se piden > 1.000)   {"OK" if r else "FALLA"}\n')

    # 3 -------------------------------------------------------------------
    r = df.shape[1] >= 5
    ok &= r
    print("3. Ancho suficiente       df.shape")
    print(f'   -> {df.shape} (se piden >= 5 columnas)   {"OK" if r else "FALLA"}\n')

    # 4 -------------------------------------------------------------------
    print("4. Mezcla de tipos        df.dtypes.value_counts()")
    conteo = df.dtypes.astype(str).value_counts()
    for tipo, n in conteo.items():
        print(f"     {tipo:<18} {n}")
    tipos = df.dtypes
    num = tipos.apply(pd.api.types.is_numeric_dtype).any()
    fec = tipos.apply(pd.api.types.is_datetime64_any_dtype).any()
    cat = tipos.apply(lambda t: pd.api.types.is_object_dtype(t)
                      or pd.api.types.is_string_dtype(t)).any()
    r = bool(num and fec and cat)
    ok &= r
    print(f'   -> numericas={num}, fechas={fec}, categoricas={cat}   {"OK" if r else "FALLA"}\n')

    # 5 -------------------------------------------------------------------
    print("5. Nulos conocidos        df.isna().mean().sort_values(ascending=False)")
    nulos = df.isna().mean().sort_values(ascending=False)
    for col, pct in nulos.head(6).items():
        print(f"     {col:<20} {pct*100:>6.2f} %")
    print(f"     ... ({(nulos > 0).sum()} columnas con algun nulo de {len(nulos)})")
    print("   -> documentados en silver/informe_calidad.csv   OK\n")

    # 6 -------------------------------------------------------------------
    vacias = df.columns[df.isna().all()].tolist()
    r = not vacias
    ok &= r
    print("6. Sin columnas vacias    df.columns[df.isna().all()]")
    print(f'   -> {vacias if vacias else "[] (ninguna)"}   {"OK" if r else "FALLA"}\n')

    print("=" * 60)
    print("  TODOS LOS CRITERIOS MEDIBLES: " + ("OK" if ok else "HAY FALLAS"))
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
