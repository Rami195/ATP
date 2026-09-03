# airflow-atp — Entrega 1, Proyecto Integrador Ciencia de Datos 2026

DAG de Airflow que envuelve el pipeline de `../proyecto-atp/` (descarga +
consolidación) para la Entrega 1. La lógica de descarga y consolidación es la
misma que ya está validada en `proyecto-atp/src/` — acá vive copiada y
adaptada en `include/atp/` para correr dentro del contenedor de Airflow.

## Uso

```bash
cd airflow-atp
astro dev start
```

Abrí la URL que imprime Astro al terminar (usuario/contraseña `admin`/`admin`),
despausá `atp_ingest` y disparalo. Con los parámetros por defecto
(`anio_desde=2000`, `anio_hasta=2025`) tarda ~90 segundos la primera vez.

## Qué hace cada tarea

| Tarea | Capa | Qué hace |
|---|---|---|
| `discover_seasons` | — | Arma la lista de años a procesar según los parámetros de la corrida |
| `land_bronze` (×26, una por año) | Bronce | Descarga el CSV de una temporada; si ya está en disco, no la vuelve a pedir |
| `land_bronze_aux` | Bronce | Descarga las tablas auxiliares (biografías, torneos en curso) |
| `consolidate` | Plata | Une las temporadas, tipa columnas, deduplica, arma `id_partido` único |
| `quality_report` | — | Valida los 6 criterios de la Entrega 1 (clave única, volumen, ancho, mezcla de tipos, sin columnas vacías) y escribe el informe de nulos |
| `save` | — | Copia el dataset final a `atp_partidos_<fecha>.csv` |

## Dónde queda todo

```
include/output/
├── bronze/                      # CSV crudos por temporada + auxiliares
├── silver/
│   ├── partidos_consolidado.csv # un partido por fila (77.474 filas, 55 columnas)
│   └── informe_calidad.csv      # % de nulos por columna clave
└── atp_partidos_<fecha>.csv     # el entregable de la corrida
```

## Por qué no hay sensor ni branching

A diferencia de `fifa_ingest` (la práctica de la Unidad 1), TML-Database es un
repositorio de GitHub estático: no hay Cloudflare, ni caídas intermitentes que
esperar. Agregar un sensor acá copiaría un patrón sin que resuelva un problema
real de esta fuente — punto que conviene tener claro para la defensa.

## Qué falta para las próximas entregas

`src/features.py` de `proyecto-atp/` (formato jugador-partido, historial sin
fuga, dataset A/B para modelado) queda **fuera de esta entrega a propósito**:
son insumos de la Entrega 2/3, no del dataset crudo consolidado que pide la
Entrega 1.
