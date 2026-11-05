# Entrega 4 · Entre líneas: estilos ATP

Grupo 5K10-05 · Ciencia de Datos · UTN FRM · 2026.

**Idea central:** tres estilos describen 1.224 perfiles ATP; al predecir partidos
posteriores, agregarlos al ranking no muestra una mejora clara.

La aplicación está en `dist/`. Es una web estática con gráficos **construidos en
Python con Altair**, exportados como especificaciones Vega-Lite. La inferencia
K-means y logística corre en JavaScript con los parámetros exportados. No hay
servidor de modelos ni que instalar Python para visitar la URL pública.

## Abrir localmente

Desde esta carpeta:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

Abrir <http://127.0.0.1:8765>. No abrir `index.html` con doble clic: el navegador
bloquea las lecturas `fetch` desde `file://`. Ctrl+C detiene el servidor.
Las bibliotecas Vega se incluyen en `dist/vendor/`: no dependen de un CDN en clase.

## Regenerar la misma aplicación

Probado con Python 3.14, Node 24 y las versiones de `requirements.txt`.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python build.py
node test_app.cjs
node test_charts.cjs
```

Las otras dos pruebas necesitan paquetes que no son parte de la app. Con el servidor
local en marcha y Chrome instalado (`CHROME_PATH` cambia la ruta del ejecutable):

```powershell
npm install --no-save jsdom puppeteer-core
node test_dom.cjs
node test_browser.cjs
```

`test_browser.cjs` es la que abre la app en Chrome real. Detecta lo que las demás no
ven: gráficos con ancho 0, errores de consola, recursos que faltan y desbordes en
pantallas chicas. Si cambiás algo de la página, corré ésa antes de publicar.

Los snapshots de `inputs/` permiten reconstruir la entrega sin descargar nada.
`build.py` copia `web/`, prepara los datos, calcula métricas, exporta los gráficos,
y escribe `dist/trazabilidad.json`. Las salidas siempre derivan de datos; no hay
asignaciones inventadas para los ejemplos. Los textos numéricos del protocolo y
las conclusiones son editoriales: si se cambia el experimento, revisar esos textos.

## Regenerar la cadena cuando cambian los datos

1. En `../airflow-atp`, ejecutar `astro dev start`, disparar `atp_ingest` con las
   temporadas deseadas y obtener ambos CSV fechados en `include/output/`.
2. Ejecutar EDA y clustering en los notebooks de `../entrega2` y `../entrega3`.
   Mantener el filtro de calidad y exportar Z, nombres, medias, desvíos y centros.
3. Para la parte predictiva, desde esta carpeta:

```powershell
python ../entrega3/completar_prediccion.py --partidos ../airflow-atp/include/output/atp_partidos_2026-09-23.csv
python ../entrega3/test_temporal.py
python ../entrega3/generar_enfrentamientos.py --partidos ../airflow-atp/include/output/atp_partidos_2026-09-23.csv
```

4. Actualizar `inputs/jugadores.csv`, `inputs/estilos_referencia.csv` y
   `inputs/modelo_exacto.json` con **la misma ejecución** de E3. El último JSON
   tiene los mismos campos que `estilos_config.json`, con medias y desvíos sin
   redondear. `build.py` copia las salidas predictivas de E3 a `inputs/` si están
   disponibles; si no, usa los snapshots incluidos.
5. Ejecutar `python build.py`, las cuatro pruebas Node y `python crear_notebooks.py`.
   Leer `auditoria_versiones.json`, revisar resultados/conclusiones, publicar todo
   `dist/` y probar la URL desde otra computadora. No reutilizar métricas de otro corte.

El nuevo análisis es reproducible en
`../entrega3/Entrega3_ATP_Ampliacion_Ganadores.ipynb`; se agrega sin borrar la E3
original. La referencia a esta ampliación queda también en el notebook original.

## Dos modelos de estilos, dos alcances

- **Descriptivo E3:** carreras agregadas 2000–2025, 1.224 perfiles / 582 jugadores.
  Se usa en el mapa y el primer formulario. Silhouette 0,171293; PCA 58,83 % en dos
  componentes; tamaños 326 / 496 / 402. No pronostica partidos históricos.
- **Predictivo:** otro ajuste de la misma metodología, sólo hasta 2018 y congelado.
  Se aplica a historiales disponibles antes de cada fecha de inicio de torneo.
  Alimenta la comparación de victorias y la regresión logística. Puede asignar
  otro estilo a un mismo jugador; no se mezclan los centros de carrera completa.

El formato A/B es aleatorio, semilla 42. La historia excluye **todos** los partidos
con la misma fecha, porque esa fecha es de inicio del torneo y no una fecha diaria
fiable. Se controla cobertura de bloques, denominadores y consistencia. Rankings
se conocen al inicio del torneo. Walkovers fuera; retirados incluidos como resultado.

Entrenamiento 2000–2018: 29.781; validación 2019–2022: 5.714;
test 2023–2025: 4.773. Sólo se evalúan casos con historial suficiente de ambos.
Representan 56,67 % de los 8.423 partidos del período con superficie válida y sin W/O.

Se selecciona C por log-loss de validación entre 0,01 / 0,1 / 1 / 10. Se reajusta
hasta 2022 con el clustering congelado. Se elige el ampliado por validación y se
conserva esa elección aunque no mejore en test. No se usa test para elegirlo.

| Modelo en test | Accuracy | AUC | Log-loss | Brier |
|---|---:|---:|---:|---:|
| Ranking + contexto | 64,47 % | 0,6975 | 0,62967 | 0,22007 |
| Ranking + contexto + estilos | 64,17 % | 0,6962 | 0,63063 | 0,22050 |
| Gana el mejor rankeado | 64,47 % | — | — | — |

Δ accuracy: −0,293 puntos porcentuales; IC95 % [−0,730; +0,114].
Δ log-loss: +0,000957; IC95 % [−0,000414; +0,002367]. Bootstrap pareado por torneo,
2.000 repeticiones. No hay mejora clara; tampoco es una prueba de equivalencia.
Los intervalos no modelan toda la dependencia entre jugadores a lo largo de años.

El test mide qué pasa cuando los modelos discrepan. Sumar estilos cambia al favorito
en 112 de los 4.773 partidos (2,35 %): en ésos acierta el ranking 63 veces y los
estilos 49. Ese saldo de 14 partidos es exactamente la diferencia de accuracy.

Reejecutar `completar_prediccion.py` puede cambiar los últimos bytes de
`modelo_prediccion.json` y `predicciones_test.csv`: se comprobó que es ruido de punto
flotante (Δ coeficiente máximo 9e−15), sin ningún estilo ni favorito distinto.

## El simulador de enfrentamientos

`generar_enfrentamientos.py` arma un catálogo con el perfil de cada jugador al cierre
de cada año entre 2019 y 2025: 2.572 perfiles de 292 jugadores. El ranking es la última
aparición registrada de ese año, con su fecha; no es el ranking actual. El usuario elige
superficie, año y dos jugadores, y la app compara tres lecturas:

- **Ranking + contexto:** el modelo base.
- **Cruce de estilos:** el modelo ampliado con los dos rankings iguales. **No es un
  tercer modelo entrenado ni tiene accuracy propia.** Si comparten estilo da 50/50.
- **Ranking + estilos:** el modelo ampliado, que es el elegido en validación.

Es un escenario hipotético. El modelo se aprendió hasta 2022 y sus centros hasta 2018,
así que elegir 2019 no reproduce un pronóstico hecho en 2019. Tres cruces de ejemplo
muestran cada caso: mismo estilo, estilos que cambian al favorito, y estilos distintos
con el mismo favorito. La respuesta general sigue siendo la del test.

## Auditoría de la entrega anterior

Se detectaron **12 tasas en 3 perfiles** diferentes entre el Silver local y la
instantánea guardada de E3: Safiullin/clay, Tiafoe/clay y Kukushkin/grass.
No se inventó una causa para la diferencia. El mapa usa el Z guardado y los
parámetros completos del `pipeline_estilos.joblib` original; las tasas originales
se recuperan mediante `x = z * desvío + media`. La diferencia se publica en
`auditoria_versiones.json`. La pertenencia al universo se comprueba por ID/superficie.
El análisis nuevo utiliza los partidos actuales, con su SHA-256 en el informe.

La correlación aces/resto en la instantánea estandarizada de los 1.224 perfiles
es **−0,5025**. No se copió el ≈−0,58 de otra etapa/filtro de EDA al gráfico nuevo.

## Consigna y Unidad 4

- Portada: una conclusión y tres números que sostienen sus dos mitades.
- Tallo: calidad del universo; asociación estilo-victorias, con el ranking como
  control; aporte predictivo. Cada sección tiene título afirmativo, gráfico y
  evidencia cerrada por defecto.
- Copa: simulador de enfrentamientos por superficie y jugadores; panorama de todos
  los perfiles, filtros de superficie/estilo/experiencia/nombre, detalle por tooltip,
  clic y selector accesible; asignación de un caso nuevo.
- Modo avanzado del simulador: casos históricos con features previas y posibilidad
  de editar 14 tasas, dos rankings, superficie y formato.
- Gramática: `build.py` declara datos, tipos, marcas, transformaciones y escalas.
  Color y forma del estilo permanecen constantes. Barras desde cero. Incertidumbre
  visible. Los controles cambian `transform_filter`, no la escala ni el modelo.
- El material aplicado es `Teoria/Unidad4/Visualización de datos.html` y
  `Practica/Unidad_4_Practica.ipynb`: gramática, posiciones, capas, escalas,
  Shneiderman y copa de martini. El recurso de ejemplo del campus no pudo abrirse
  desde la herramienta web; se trabajó con la consigna y los materiales locales.

## Archivos para revisar

| Archivo | Función |
|---|---|
| `build.py` | Preparación, auditoría, especificaciones Altair y paquete estático |
| `web/modelo.js` | Asignación K-means y predicción logística portable |
| `web/app.js` | Interacciones, filtros, detalle y validación de entradas |
| `inputs/` | Snapshots que hacen reproducible esta versión |
| `Entrega4_ATP_Visualizacion.ipynb` | Métricas y gráficos de la misma app |
| `GUIA_DEFENSA.md` | Explicación oral y preguntas del docente |
| `test_app.cjs` | Equivalencia completa Python/JavaScript y casos inválidos |
| `test_charts.cjs` | Compilación/ejecución de gráficos y filtros sin navegador |
| `test_dom.cjs` | Controles HTML en jsdom, con gráficos simulados |
| `test_browser.cjs` | La app completa en Chrome real, en tres anchos de pantalla |
| `../entrega3/generar_enfrentamientos.py` | Catálogo de perfiles por año y cruces de ejemplo |
| `VERIFICACION.md` | Resultado de pruebas y límites de revisión |

Documentación técnica: [exportación Altair a JSON/HTML](https://altair-viz.github.io/user_guide/saving_charts.html).
Las bibliotecas de `web/vendor/` son Vega 6.2.0, Vega-Lite 6.4.1 y Vega-Embed 7.1.0,
descargadas de jsDelivr, paquetes oficiales. Licencias BSD-3-Clause conservadas en
`web/vendor/`. No se usa una imagen de un gráfico como sustituto de Altair.

## Publicación

Servir todo `dist/` desde la raíz del hosting estático. La configuración de Sites
queda en `.openai/hosting.json`; no crear un segundo proyecto para actualizarlo.
La URL y el estado confirmado de publicación se registran en `PUBLICACION.md`.
La consigna exige acceso público sin instalar nada; un enlace privado no la cumple.
