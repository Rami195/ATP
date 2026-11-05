# ATP — Proyecto Integrador, Ciencia de Datos UTN FRM 2026

## Versión final · Entrega 4

La aplicación, los gráficos Altair y las instrucciones de reproducción están en
[`entrega4/README.md`](entrega4/README.md). Incluye exploración de estilos y un
simulador de enfrentamientos: elegís superficie y dos jugadores, y compara el estilo
de cada uno con lo que dice el ranking.

La pregunta predictiva se completa en
[`Entrega3_ATP_Ampliacion_Ganadores.ipynb`](entrega3/Entrega3_ATP_Ampliacion_Ganadores.ipynb):
agregar estilos al ranking no muestra una mejora clara en los 4.773 partidos de
test de 2023–2025. La diferencia de accuracy es−0,29 puntos porcentuales y su
intervalo incluye cero. Se conserva el notebook de clustering original.

La guía de defensa está en [`entrega4/GUIA_DEFENSA.md`](entrega4/GUIA_DEFENSA.md).

Pipeline de datos del circuito ATP: descarga automatizada, consolidación y
dataset a nivel partido para estudiar qué predice el ganador de un partido.

**Pregunta del proyecto:** ¿existen estilos de juego diferenciables entre los
tenistas según sus patrones de saque y resto? ¿Hay estilos globalmente
superiores, y el emparejamiento de estilos predice el ganador por encima del
ranking?

**Una fila = un partido.** 77.474 partidos ATP entre 2000 y 2025.

## Grupo 5K10-05

Ariza, Alvaro · Cabrero, Daniel · Hansen, Matias · Leyes, Agustin ·
Marquesini, Luciano · Martinez, Ramiro

## Estructura

```
├── airflow-atp/      # DAG de Airflow (Entrega 1) — el pipeline orquestado
│   ├── dags/atp_ingest.py
│   └── include/atp/  # descarga, consolidación y configuración
└── proyecto-atp/     # pipeline original en Python puro + feature engineering
    ├── pipeline.py
    └── src/          # incluye features.py (historial sin fuga, dataset A/B)
```

## Cómo correrlo

**Con Airflow** (lo que se defiende en la Entrega 1):

```bash
cd airflow-atp
astro dev start
```

Abrí la interfaz, despausá `atp_ingest` y disparalo. Tarda ~90 s la primera
vez; las corridas siguientes reutilizan la capa bronce y no vuelven a pedirle
nada a la fuente.

**Como script** (la versión original, sin orquestador):

```bash
cd proyecto-atp
pip install -r requirements.txt
python pipeline.py
```

## Fuente

[Portal de datos de Tennis My Life](https://stats.tennismylife.org/tennis-match-database)
— un CSV por temporada (1968–2026) más tablas auxiliares de jugadores.
Reemplaza a `JeffSackmann/tennis_atp`, que fue dado de baja.

La descarga es por **URL directa**: un `GET` por archivo contra
`https://stats.tennismylife.org/data/<archivo>.csv`, sin API key y sin clonar
ningún repositorio. El portal publica además un catálogo JSON en
[`/api/data-files`](https://stats.tennismylife.org/api/data-files). Licencia
MIT, declarada en el metadato `schema.org/Dataset` de la página.

## Datos

Los datasets **no se versionan**: los genera el pipeline. Corriendo cualquiera
de las dos versiones se reconstruyen en `airflow-atp/include/output/` o en
`proyecto-atp/datos/`.

| Salida | Filas | Columnas |
|---|---|---|
| `partidos_consolidado.csv` | 77.474 | 55 |
| `informe_calidad.csv` | 15 | 3 |

Detalle de cada capa y de cada tarea del DAG en
[`airflow-atp/README.md`](airflow-atp/README.md); detalle del feature
engineering y las fugas de datos que evita en
[`proyecto-atp/README.md`](proyecto-atp/README.md).
