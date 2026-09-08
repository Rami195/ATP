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
| `validate` | — | Valida las 5 dimensiones de calidad (unicidad, completitud, precisión, consistencia, actualidad) con umbrales elegidos a partir del profiling. Si un chequeo crítico falla, `save` no corre. Los problemas menores quedan como avisos y no frenan |
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

## La validación: qué se chequea y con qué umbral

`validate` cubre las cinco dimensiones de calidad y va **entre `consolidate` y
`save`**: si un chequeo crítico falla, `save` no corre y el dato malo no llega
al entregable.

Los umbrales salen de perfilar el dataset real, no de copiar un número de otro
proyecto. Al lado de cada uno está la medición que lo justifica:

| Dimensión | Qué se chequea | Umbral | Por qué ese número |
|---|---|---|---|
| **Unicidad** | `id_partido` sin duplicados | cero | Es el test operativo de la unidad de análisis: si la clave repite, o la unidad está mal definida o el pipeline duplica |
| **Completitud** | 5 columnas obligatorias sin nulos | cero | Medido: hoy `id_partido`, `winner_id`, `loser_id`, `fecha` y `tourney_id` tienen 0 nulos |
| **Completitud** | Partidos **por temporada** | ≥ 1.200 | La temporada más flaca es 2020 con 1.466 (acortada por COVID); la mediana es 3.012. Un piso global de 1.000 filas se cumpliría con **una sola** temporada de las 26 |
| **Actualidad** | Están todas las temporadas pedidas | cero faltantes | Atrapa la descarga que falló en silencio |
| **Precisión** | Rangos físicos (altura, edad, ranking, minutos) | ver constantes | Holgados sobre lo observado: alturas 155–211 cm se validan contra 140–230. `minutes` admite 0 porque son los 51 walkovers, y llega a 720 porque el máximo real es Isner–Mahut 2010 (665 min) |
| **Precisión** | Dominios cerrados | `best_of ∈ {3,5}`, `surface ∈ {Hard, Clay, Grass, Carpet}` | Un valor nuevo acá significa que la fuente cambió |
| **Consistencia** | 10 cruces (`ace ≤ svpt`, `bpSaved ≤ bpFaced`, …) | ≤ 0,05 % | **No es cero**: la fuente ya trae 7 filas rotas sobre 71.055 comparables (0,004 %). El umbral deja ~12× de margen sobre ese ruido conocido y atrapa una rotura sistemática, que movería el número a decenas de puntos |

### Lo que avisa pero no frena

> *Lo crítico frena; lo que es sólo observabilidad, avisa.*

- Las 7 filas inconsistentes de la fuente quedan como aviso en el log.
- Columnas con más de 10 % de nulos. El umbral va apenas por encima de la banda
  conocida (8,3 % las stats de saque, 9,3 % `minutes`) para que sea una alarma
  real: hoy no suena, y suena si la cobertura empeora.
- `winner_seed`, `loser_seed`, `winner_entry` y `loser_entry` quedan **excluidas**
  del aviso aunque tengan 59–87 % de nulos: ahí el nulo no es un dato faltante,
  significa "no era cabeza de serie" y "entró directo".

### Cómo sabemos que la validación sirve

Se probó contra cuatro datasets rotos a propósito, y los atrapa todos:

| Falla simulada | La atrapa |
|---|---|
| Sólo 2 de 26 temporadas descargadas | Actualidad |
| 500 filas duplicadas | Unicidad |
| Columnas de stats corridas un lugar | Consistencia (99,98 % de violaciones) |
| Alturas de 300 cm, superficie "Padel" | Precisión |

## Por qué no hay sensor ni branching

A diferencia de `fifa_ingest` (la práctica de la Unidad 1), el portal de Tennis
My Life sirve archivos estáticos: un `GET` a `/data/<archivo>.csv` devuelve el
CSV directamente, sin Cloudflare, sin JavaScript y sin login. No hay una espera
real que modelar, así que un sensor acá copiaría un patrón sin resolver ningún
problema de esta fuente — punto que conviene tener claro para la defensa.

Sí es un servidor propio (nginx) y no un CDN, de modo que puede tener caídas
puntuales. Eso lo cubre `_descargar_archivo` con 3 reintentos y backoff, más la
caché de la capa bronce: si una tarea falla, el reintento no volvería a pedir
los años que ya bajaron.

## Qué falta para las próximas entregas

`src/features.py` de `proyecto-atp/` (formato jugador-partido, historial sin
fuga, dataset A/B para modelado) queda **fuera de esta entrega a propósito**:
son insumos de la Entrega 2/3, no del dataset crudo consolidado que pide la
Entrega 1.
