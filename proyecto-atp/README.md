# Pipeline ATP — Proyecto Integrador Ciencia de Datos 2026

Pipeline automatizado que produce un dataset a nivel partido para responder:

> ¿En qué medida el ranking, la forma reciente y el rendimiento histórico por
> superficie permiten predecir el ganador de un partido ATP — y el rendimiento
> bajo presión (break points, tie-breaks, sets decisivos) aporta poder
> predictivo por encima del ranking?

## Uso

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

python pipeline.py                            # temporadas 2000-2025
python pipeline.py --desde 1991 --hasta 2025  # más volumen
python pipeline.py --forzar-descarga          # ignora la caché local
```

No requiere ninguna intervención manual: descarga, consolida y escribe.
Re-ejecutarlo es barato porque los CSV crudos quedan cacheados en `datos/crudo/`.

## Fuente

**[Tennismylife/TML-Database](https://github.com/Tennismylife/TML-Database)** —
un CSV por temporada (1968–2026), 50 columnas, ~3.000 partidos por año.

> ⚠️ El repositorio que suele recomendarse para esto, `JeffSackmann/tennis_atp`,
> **fue dado de baja** (404, igual que `tennis_wta` y `tennis_slam_pointbypoint`).
> TML-Database usa el mismo esquema de columnas más `indoor`, y sigue
> actualizándose. Si algún tutorial les manda al repo de Sackmann, está viejo.

Tablas auxiliares que el pipeline también baja:

| Archivo | Contenido |
|---|---|
| `ATP_Database.csv` | 7.643 jugadores: altura, peso, mano, **tipo de revés**, entrenadores, lugar de nacimiento |
| `ongoing_tourneys.csv` | Partidos del torneo en curso, fuera de los CSV anuales |

**Nota sobre 2026:** al momento de armar esto, `2026.csv` cubre hasta el 17/01 y
el resto está en `ongoing_tourneys.csv`. Por eso el rango por defecto termina en
2025. No armen la app asumiendo datos de esta semana sin verificar.

## Salidas

Todo en `datos/procesado/`:

| Archivo | Unidad de observación | Para qué sirve |
|---|---|---|
| `partidos_consolidado.csv` | un partido | Entrega 1: el dataset crudo consolidado |
| `jugador_partido.csv` | un jugador en un partido | Entrega 2: exploración, evolución de un jugador |
| `dataset_modelado.csv` | un partido (A vs B) | Entrega 3: dataset completo, 94 columnas |
| `dataset_reducido.csv` | un partido (A vs B) | Entrega 3: **empezá por acá**, 26 columnas |
| `informe_calidad.csv` | una columna | Entrega 1: nulos y cobertura |
| `jugadores_bio.csv` | un jugador | features extra por join |

## Las dos fugas de datos que el pipeline evita

Son el punto que decide la nota de la Entrega 3. Si alguien del grupo tiene que
explicar una sola cosa en la defensa, que sea esta.

### 1. Fuga por el formato `winner_` / `loser_`

Las columnas de la fuente vienen etiquetadas por resultado: `winner_rank`,
`loser_rank`. **El orden de las columnas ya contiene la respuesta.** Entrenar
así da 100 % de accuracy y cero aprendizaje.

El pipeline reasigna cada partido a **jugador A / jugador B con una moneda al
aire** (semilla fija, reproducible) y el target pasa a ser `gana_a`. El control
automático verifica que el balance quede en ~0.500.

### 2. Fuga temporal

`w_ace`, `w_bpSaved`, `minutes` describen el partido **que queremos predecir**:
no existen antes de jugarlo. Todas las features históricas se calculan como
suma acumulada **excluyendo la fila actual**.

Detalle fino: dentro de un mismo torneo todos los partidos comparten
`tourney_date`, así que ordenar solo por fecha dejaría la final "antes" de una
primera ronda. El pipeline ordena por `fecha, orden_ronda` (ver
`ORDEN_RONDA` en `src/config.py`).

`pipeline.py` corre `control_de_fuga()` en cada ejecución: verifica que no
queden columnas `m_` (stats del partido en curso), que el target esté
balanceado, y que ninguna feature separe las clases casi perfectamente.

## Features construidas

Todas miran **hacia atrás**. Cada una existe como `_a`, `_b` y `dif_` (la
diferencia A − B, que suele funcionar mejor que los valores absolutos porque
un partido es una comparación).

**Presión** — el corazón de la hipótesis:
`bp_salvados_pct`, `bp_convertidos_pct`, `tb_winrate`, `decisivos_winrate`,
`indice_presion` (promedio de las cuatro, derivado).

**Forma y trayectoria:**
`n_partidos`, `winrate_hist`, `winrate_10` (últimos 10), `winrate_sup` y
`n_partidos_sup` (por superficie), `partidos_en_anio`, `dias_descanso`.

**Saque y resto:**
`ace_pct`, `df_pct`, `primer_saque_in_pct`, `primer_saque_gan_pct`,
`segundo_saque_gan_pct`, `pts_saque_ganados_pct`.

**Enfrentamiento directo:** `h2h_ganados`, `h2h_jugados`.

**Ranking:** `jugador_rank`, `jugador_rank_pts`, `log_rank` y `dif_log_rank`
(el ranking es no lineal: la distancia entre el 1 y el 10 no es la del 101 al 110).

**Contexto:** `surface`, `indoor`, `tourney_level`, `round`, `best_of`, `fecha`.

## Por qué hay una versión reducida

`dataset_reducido.csv` — **64.755 filas × 26 columnas**, de las cuales 20 son
features. No es por prolijidad: las 94 columnas del dataset completo tienen
**colinealidad perfecta por construcción**, porque `dif_x` es exactamente
`x_a − x_b`. Pasarle las tres a una regresión logística deja el sistema
indeterminado y los coeficientes dejan de ser interpretables.

El reducido se queda con las `dif_` (un partido es una comparación, no dos
jugadores sueltos), descarta lo que midió AUC < 0,55 (`dias_descanso`,
`jugador_ht`, `jugador_edad`, `df_pct`, `primer_saque_in_pct`) y ya viene
filtrado por `historial_suficiente`.

Sigue cumpliendo el criterio 6 con holgura: 20 features contra un piso de 5,
mezclando numéricas (`dif_*`), categóricas (`surface`, `round`,
`tourney_level`, `indoor`) y fecha. Nulos por debajo del 1,1 % en todas las
columnas salvo `indoor` (4,0 %).

Empezá modelando con este. Si el modelo se queda corto, volvés al completo.

## Cómo usarlo en la Entrega 3

```python
import pandas as pd

df = pd.read_csv("datos/procesado/dataset_modelado.csv", parse_dates=["fecha"])
df = df[df.historial_suficiente == 1]

# Split TEMPORAL, no aleatorio: predecir el pasado con el futuro no vale.
train = df[df.fecha <  "2023-01-01"]
test  = df[df.fecha >= "2023-01-01"]

y_train, y_test = train.gana_a, test.gana_a
```

**Baseline obligatorio:** "gana el mejor rankeado" (`dif_log_rank < 0`) acierta
alrededor del 65 %. Si el modelo no le gana a eso, no aporta nada. Reportar AUC
**y calibración** (`sklearn.calibration.calibration_curve`) — en predicción
deportiva una probabilidad bien calibrada vale más que el accuracy.

**Para la Entrega 2**, la pregunta interesante: ¿el "clutch" persiste? Correlacionar
`bp_salvados_pct` de cada jugador entre temporadas consecutivas. Si la correlación
es baja, es ruido y no una habilidad — y ese hallazgo negativo es un resultado
perfectamente válido y mucho más interesante de defender que un gráfico lindo.

## Resultados de la corrida de referencia (2000–2025)

Números medidos, no estimados. Sirven como control: si al reproducir el
pipeline dan muy distinto, algo se rompió.

```
partidos consolidados        77.474
filas jugador-partido       154.948   (2.732 jugadores)
con historial >= 10 part.    64.755
balance del target            0.503
tiempo total                    67 s
```

Cordura de las métricas derivadas, contra los valores reales del circuito:

| Métrica | Medido | Real ATP |
|---|---|---|
| Break points salvados | 60,7 % | ~61 % |
| Break points convertidos | 39,7 % | ~40 % |
| Puntos ganados con el saque | 62,9 % | ~63 % |
| Primer saque dentro | 60,4 % | ~60 % |
| Tie-breaks ganados | 50,2 % | 50 % por construcción |

**Baseline "gana el mejor rankeado": 64,65 %** (n = 64.532). Ese es el número a
superar en la Entrega 3.

AUC de cada feature por sí sola, sobre las 64.755 filas usables. Nada cerca de
1,0 ⇒ no hay fuga:

| Feature | AUC | Cobertura |
|---|---|---|
| `dif_jugador_rank_pts` | 0,702 | 99,7 % |
| `dif_winrate_hist` | 0,689 | 100 % |
| `dif_winrate_sup` | 0,680 | 98,9 % |
| `dif_winrate_10` | 0,656 | 100 % |
| `dif_segundo_saque_gan_pct` | 0,640 | 99,5 % |
| **`dif_indice_presion`** | **0,636** | 100 % |
| `dif_decisivos_winrate` | 0,610 | 99,9 % |
| `dif_bp_salvados_pct` | 0,601 | 99,5 % |
| `dif_h2h_ganados` | 0,584 | 100 % |
| `dif_tb_winrate` | 0,581 | 99,9 % |
| `dif_dias_descanso` | 0,504 | 100 % (inútil) |

(`dif_log_rank` da 0,295, que es 0,705 invertido: menor número de ranking =
mejor jugador.)

Las features de presión predicen por encima del azar pero **por debajo del
ranking**. O sea: la hipótesis del proyecto tiene con qué discutirse, que es
justo lo que hace falta. Si el clutch fuera irrelevante (AUC 0,50) o dominante
(0,80) no habría pregunta.

**Anticipo de la Entrega 2:** la correlación del % de break points salvados de un
jugador entre temporadas consecutivas es **0,454** (n = 1.980 pares
jugador-temporada, filtrando ≥ 100 bp enfrentados y ≥ 20 partidos). Ni ruido
puro (0) ni habilidad estable (0,7+): hay algo, pero mucho menos de lo que dice
el relato televisivo. Ahí tienen un hallazgo defendible.

## Estructura

```
proyecto-atp/
├── pipeline.py            # orquestador (CLI)
├── requirements.txt
├── src/
│   ├── config.py          # rutas, URLs, semilla, orden de rondas
│   ├── descarga.py        # paso 1 - descarga con caché y reintentos
│   ├── consolidar.py      # paso 2 - unión, tipado, control de calidad
│   └── features.py        # pasos 3-4 - historial sin fuga + dataset A/B
└── datos/
    ├── crudo/             # CSV tal como vienen de la fuente
    └── procesado/         # salidas del pipeline
```

## Pendiente

- **Scraper del leaderboard de ATP** como segunda fuente (validación cruzada de
  las métricas de presión). Requiere Playwright: `atptour.com` renderiza todo por
  JavaScript y está detrás de Cloudflare — sin `User-Agent` de navegador
  devuelve 403, y con él el HTML llega sin la tabla. Los endpoints internos
  (`/-/www/stats/...`) responden 302.
- Elo por superficie como feature (suele superar al ranking ATP).
