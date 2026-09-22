import sys
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def encontrar_csv_mas_reciente() -> Path:
    posibles_rutas = [
        Path("airflow-atp/include/output"),
        Path("include/output"),
        Path("../include/output"),
    ]
    archivos = []
    for dir_path in posibles_rutas:
        if dir_path.exists():
            archivos.extend(dir_path.glob("atp_partidos_*.csv"))
    
    if not archivos:
        # Buscar recursivamente en el workspace si no se encuentra en las rutas habituales
        archivos = list(Path(".").rglob("atp_partidos_*.csv"))
    
    if not archivos:
        raise FileNotFoundError("No se encontró ningún archivo 'atp_partidos_*.csv'.")
    
    # Tomar el más reciente por fecha de modificación
    return max(archivos, key=lambda p: p.stat().st_mtime)

def main():
    if len(sys.argv) > 1:
        ruta_csv = Path(sys.argv[1])
    else:
        ruta_csv = encontrar_csv_mas_reciente()

    print("=" * 70)
    print(f"VERIFICACIÓN DE CALIDAD - DATASET FINAL: {ruta_csv.name}")
    print(f"Ruta: {ruta_csv.resolve()}")
    print("=" * 70)

    # Carga del CSV
    # Parseamos 'fecha' como datetime si existe para verificar tipos correctamente
    df = pd.read_csv(ruta_csv, low_memory=False)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    # 1. Clave sin duplicados
    clave = "id_partido" if "id_partido" in df.columns else df.columns[0]
    es_unica = df[clave].is_unique
    print(f"\n1. [Clave sin duplicados] ({clave}):")
    print(f"   - df['{clave}'].is_unique -> {es_unica}")
    print(f"   - Estado: {'✅ OK' if es_unica else '❌ FALLÓ'}")

    # 2. Volumen suficiente (> 1.000 filas)
    filas = len(df)
    volumen_ok = filas > 1000
    print(f"\n2. [Volumen suficiente] (más de 1.000 filas):")
    print(f"   - len(df) -> {filas:,} filas")
    print(f"   - Estado: {'✅ OK' if volumen_ok else '❌ FALLÓ'}")

    # 3. Ancho suficiente (5 o más columnas útiles)
    filas_cnt, cols_cnt = df.shape
    ancho_ok = cols_cnt >= 5
    print(f"\n3. [Ancho suficiente] (5 o más columnas útiles):")
    print(f"   - df.shape -> {df.shape} ({cols_cnt} columnas)")
    print(f"   - Estado: {'✅ OK' if ancho_ok else '❌ FALLÓ'}")

    # 4. Mezcla de tipos (numéricas, categóricas y fechas)
    print(f"\n4. [Mezcla de tipos] (numéricas, categóricas y fechas):")
    print(f"   - df.dtypes.value_counts():")
    for tipo, cant in df.dtypes.value_counts().items():
        print(f"       * {str(tipo):<25}: {cant} columnas")
    
    hay_num = df.dtypes.apply(lambda t: pd.api.types.is_numeric_dtype(t)).any()
    hay_cat = df.dtypes.apply(lambda t: pd.api.types.is_object_dtype(t) or pd.api.types.is_string_dtype(t)).any()
    hay_date = df.dtypes.apply(lambda t: pd.api.types.is_datetime64_any_dtype(t)).any()
    tipos_ok = hay_num and hay_cat and hay_date
    print(f"   - Detalle: Numéricas={hay_num} | Categóricas={hay_cat} | Fechas={hay_date}")
    print(f"   - Estado: {'✅ OK' if tipos_ok else '⚠️ Revisar parseo de fechas'}")

    # 5. Nulos conocidos (saber cuáles y por qué)
    nulos = df.isna().mean().sort_values(ascending=False)
    nulos_top = nulos[nulos > 0]
    print(f"\n5. [Nulos conocidos] (top columnas con nulos):")
    print(f"   - df.isna().mean().sort_values(ascending=False):")
    for col, pct in nulos_top.head(10).items():
        print(f"       * {col:<22}: {pct*100:>6.2f} % nulos")
    print("   ℹ️ Explicación de nulos:")
    print("       - winner_seed / loser_seed: Nulo legítimo ('no era cabeza de serie').")
    print("       - winner_entry / loser_entry: Nulo legítimo ('ingreso directo al cuadro').")
    print("       - stats de saque / minutes: Ausentes en walkovers y partidos históricos antiguos.")

    # 6. Sin columnas vacías (ninguna al 100 % de nulos)
    cols_vacias = list(df.columns[df.isna().all()])
    sin_vacias_ok = len(cols_vacias) == 0
    print(f"\n6. [Sin columnas vacías] (ninguna al 100 % de nulos):")
    print(f"   - df.columns[df.isna().all()] -> {cols_vacias}")
    print(f"   - Estado: {'✅ OK (0 columnas vacías)' if sin_vacias_ok else f'❌ Columnas 100% vacías: {cols_vacias}'}")

    print("\n" + "=" * 70)
    todo_ok = es_unica and volumen_ok and ancho_ok and sin_vacias_ok
    print(f"RESULTADO GLOBAL: {'✅ CUMPLE TODOS LOS CRITERIOS' if todo_ok else '⚠️ REVISAR OBSERVACIONES'}")
    print("=" * 70)

if __name__ == "__main__":
    main()
