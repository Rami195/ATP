# Refactor ATP para responder la pregunta de negocio

Pregunta:

> ¿Existen estilos de juego diferenciables entre los tenistas del circuito ATP según sus patrones de saque y golpeo? ¿Hay estilos globalmente superiores, y el emparejamiento de estilos predice el ganador de un partido por encima del ranking?

## Por qué hay dos granularidades finales

No conviene reemplazar todos los datos por una sola tabla.

- Para descubrir estilos: **1 fila = 1 tenista** (`player_style_dataset.csv`).
- Para probar si el emparejamiento predice el ganador por encima del ranking: **1 fila = 1 partido A/B** (`matchups_modelo.csv`).

La tabla `winner_` / `loser_` se conserva sólo como Silver, porque sirve como fuente intermedia pero genera leakage si se usa directamente para predecir el ganador.

## Flujo

```text
Bronze (CSV por temporada + biografías)
        |
        v
Silver: partidos_consolidado.csv
1 fila = partido
        |
        v
Gold intermedio: player_match_long.csv
2 filas = partido, una por cada jugador
        |
        +------------------------------+
        |                              |
        v                              v
player_style_dataset.csv         matchups_modelo.csv
1 fila = tenista                 1 fila = partido A/B
clustering de estilos            predicción / comparación ranking
```

## Transformaciones nuevas

### 1. Normalización ganador/perdedor -> jugador/rival

Cada partido se duplica en dos registros. Las columnas `w_*` y `l_*` pasan a nombres neutrales (`aces`, `service_points`, etc.). Se agrega `won` únicamente en la tabla intermedia.

### 2. Biografías

Se agrega `backhand` desde `ATP_Database.csv` y se usan `hand`, `height` e `ioc` como metadatos descriptivos. La tabla de biografías tiene algunos IDs duplicados por variantes de nombre; se conserva la fila más completa por `player_id`.

### 3. Features de saque

- `ace_rate`
- `double_fault_rate`
- `first_serve_in_pct`
- `first_serve_win_pct`
- `second_serve_win_pct`
- `bp_save_pct`

También se calculan `service_points_won_pct` como medida de rendimiento, pero no se recomienda usarla para definir los clusters de estilo.

### 4. Proxies de golpeo/resto

La fuente no posee winners, errores no forzados ni longitud de peloteos. Por eso se usan proxies construidos a partir del saque del rival:

- `first_return_win_pct`
- `second_return_win_pct`
- `break_conversion_pct`

También se calcula `return_points_won_pct` como medida agregada de rendimiento.

### 5. Agregación por tenista

Las tasas de carrera no se calculan como promedio de porcentajes por partido. Se usa:

```text
suma(numerador) / suma(denominador)
```

Así un partido de 20 puntos de saque no pesa lo mismo que uno de 150.

Por defecto se exigen 20 partidos con estadísticas válidas de saque y resto para entrar en `player_style_dataset.csv`.

### 6. Perfiles por superficie

`player_surface_profiles.csv` permite estudiar si el estilo cambia entre Hard, Clay, Grass y Carpet, evitando confundir diferencias de superficie con diferencias de jugador.

### 7. Features históricas pre-partido

Para el dataset predictivo, cada característica del jugador se calcula usando sólo partidos anteriores al partido actual. No se utiliza información futura.

### 8. A/B neutral

`matchups_modelo.csv` no usa winner/loser para decidir los lados. A y B se asignan ordenando `player_id`, y el objetivo es `target_a_wins`.

Esto evita que el nombre de las columnas revele directamente quién ganó.

## Features recomendadas para clustering

Definidas en `atp.features.STYLE_FEATURES`:

```text
ace_rate
double_fault_rate
first_serve_in_pct
first_serve_win_pct
second_serve_win_pct
bp_save_pct
first_return_win_pct
second_return_win_pct
break_conversion_pct
```

No usar para formar los clusters:

- `win_rate`
- `best_rank`
- `last_rank`
- `last_rank_points`
- `service_points_won_pct`
- `return_points_won_pct`

Estas variables pueden usarse **después** para evaluar si un estilo es globalmente superior.

## Comparación predictiva sugerida

Usar exactamente la misma muestra de `matchups_modelo.csv` para comparar:

1. Modelo base: ranking (`a_player_rank`, `b_player_rank` o su diferencia).
2. Modelo de estilos: features históricas de estilo A/B o sus diferencias.
3. Modelo combinado: ranking + estilo.

Si el modelo combinado mejora de forma consistente al modelo de ranking, hay evidencia de que el emparejamiento de estilos agrega información predictiva por encima del ranking.

## Resultado con los archivos proporcionados

Con 2000-2025 y los valores por defecto:

- `partidos_consolidado.csv`: 77.474 partidos.
- `player_match_long.csv`: 154.948 filas jugador-partido.
- Jugadores totales: 2.732.
- `player_style_dataset.csv`: 671 jugadores con al menos 20 partidos con estadísticas suficientes.
- `matchups_modelo.csv`: 56.692 partidos donde ambos jugadores tienen al menos 20 partidos previos con estadísticas y ambos rankings están disponibles.
- La asignación neutral A/B deja `target_a_wins` en ~50,8%, señal de que el lado A no está codificando al ganador.
