"""Construye y ejecuta los notebooks de cierre usando los módulos de producción."""
from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parent
md=nbf.v4.new_markdown_cell
code=nbf.v4.new_code_cell


def save_run(path,cells):
    n=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    NotebookClient(n,timeout=600,kernel_name='python3',resources={'metadata':{'path':str(path.parent)}}).execute()
    nbf.write(n,path)
    print('Ejecutado:',path.name)


e3=[
md('''# Entrega 3 · Ampliación: estilos, victorias y ganadores

**Grupo 5K10-05 · Ciencia de Datos · UTN FRM · noviembre 2026**

Completa las preguntas que el clustering descriptivo no contestaba. No sustituye
ni borra `Entrega3_ATP_Estilos_de_juego.ipynb`.

1. ¿Las participaciones de los estilos tienen la misma tasa de victoria?
2. ¿El estilo de ambos jugadores mejora la predicción por encima del ranking?

Una asociación no prueba superioridad causal. Un resultado negativo también responde
la pregunta. Este notebook ejecuta el mismo módulo que genera los parámetros de la app.'''),
md('''## 1. Protocolo fijado antes de evaluar

Entrenar con 2000–2018, elegir C con 2019–2022 y evaluar una vez en 2023–2025.
Las dos alternativas son regresiones logísticas regularizadas comparables: ranking
+ contexto frente a ranking + contexto + estilos. C ∈ {0,01; 0,1; 1; 10}, menor
log-loss en validación. Tras elegir, reajustar hasta 2022. No elegir usando test.

Los centros de carrera completa de E3 incluyen años futuros: **no se usan aquí**.
Se reajusta K-means con perfiles acumulados sólo hasta 2018 y se congela. El criterio
k=3 proviene del estudio descriptivo previo; esta ampliación es retrospectiva y no
un experimento prerregistrado ni una validación externa completamente independiente.

El CSV informa fecha de inicio de torneo. Cada historial excluye todos los partidos
con esa misma fecha, sin intentar inferir el orden diario. No usa estadísticas del
encuentro ni el rol winner/loser como entrada. A/B se asigna al azar, semilla 42.
Requisitos para ambos: ≥20 partidos previos por superficie, coberturas ≥80 %, siete
tasas definidas y rankings válidos. Se excluyen walkovers; retirados conservan su desenlace.'''),
code('''from pathlib import Path
import json, sys
import pandas as pd
import numpy as np
import altair as alt
from IPython.display import display, Markdown
from completar_prediccion import main

informe = main()  # regenera historia, ajustes, selección y evaluación
OUT = Path('resultados/prediccion')
modelo = json.loads((OUT/'modelo_prediccion.json').read_text(encoding='utf-8'))
pd.Series(informe['counts'], name='Cantidad')'''),
md('''## 2. Historial, grupos y modelos

El script `completar_prediccion.py` es parte de esta entrega, no una caja negra:
`participations` valida los bloques; `history` suma por fecha y resta toda la fecha
actual; `rates` calcula las siete tasas; `fit_styles` ajusta medias/desvíos por
superficie y K-means sobre un perfil por jugador–superficie; `features` arma el contraste.

La base usa `log(rank_B/rank_A)` y sus interacciones con polvo de ladrillo, césped
y best_of=5. El ampliado suma un contraste con signo para cada pareja distinta de
estilos, separado por superficie. No hay intercepto: invertir A/B cambia el signo
de las entradas y hace que P(B)=1−P(A). Emparejamientos iguales aportan cero al
contraste de estilos. Regularización L2 limita los coeficientes.

El escalador y los centros están ajustados hasta 2018, incluso después del reajuste
logístico hasta 2022. No es necesario que las etiquetas coincidan con las de carreras
completas del mapa. Las predicciones de test se hacen en secuencia retrospectiva:
un partido ya disputado en 2023 puede formar el historial de uno de 2024.'''),
code('''display(pd.DataFrame(informe['candidates']))
display(pd.DataFrame(modelo['styles']['centers'], columns=modelo['styles']['columns'], index=modelo['styles']['names']))
display(Markdown('**Seleccionado por validación:** '+informe['selected_by_validation']))'''),
md('''## 3. ¿Hay estilos con más victorias?

Sólo test; una fila es una participación. Cada partido aporta una victoria y una
derrota. Se muestran también resultados por superficie. Los intervalos remuestrean
torneos completos 1.000 veces, evitando tratar todas las participaciones como independientes.
No corrigen todas las dependencias entre años de un mismo jugador. No se equiparan
ranking, rivales o nivel: esto es descriptivo, no una estimación causal.'''),
code('''asociacion = pd.DataFrame(informe['association'])
display(asociacion)
sys.path.insert(0, str(Path('../entrega4').resolve()))
from build import predictive_charts
graficos = predictive_charts(informe)
alt.Chart.from_dict(graficos['victorias']).properties(width=700)'''),
md('''### El ranking del partido como control

Los estilos no llegan parejos a los partidos: los restadores son el mejor rankeado
mucho más seguido que saque frágil. Por eso el gráfico abre la tasa de victoria según
quién llega mejor rankeado. La distancia entre filas (más de 20 puntos) supera la que
hay entre estilos dentro de una fila (menos de 10), y entre los peor rankeados el orden
se invierte, con intervalos solapados.

**Este corte se agregó al armar la app, después de ver el test.** Es descriptivo: no
interviene en la selección de C ni del modelo y no cambia ningún coeficiente. Controla
una sola variable y de forma gruesa; no tiene en cuenta la distancia de ranking ni el rival.'''),
code('''display(pd.DataFrame(informe['association_rank']).round(4))
display(pd.Series(informe['best_ranked_share'], name='Llega como mejor rankeado').round(4))'''),
md('''## 4. ¿Aporta el estilo sobre el ranking?

Se comparan exactamente los mismos partidos en ambas alternativas. El piso
determinista «gana el mejor rankeado» tiene accuracy, pero no probabilidades
calibradas para calcular log-loss. Se incluye además P=0,5 como piso probabilístico.
En ese piso, el desempate de accuracy elige A, por eso no da exactamente 50 %.'''),
code('''display(pd.DataFrame(informe['metrics']).T)
display(pd.Series(informe['comparison']))
alt.Chart.from_dict(graficos['rendimiento']).properties(width=700)'''),
code("alt.Chart.from_dict(graficos['calibracion']).properties(width=650)"),
md('''### Dónde cambia algo sumar estilos

Dos modelos sólo difieren en accuracy en los partidos donde eligen favoritos distintos.
Contar esos partidos muestra el tamaño real de la diferencia: el saldo entre lo que
ganan y pierden los estilos en esos casos es exactamente la Δ accuracy.'''),
code('''cambios = informe['favorite_changes']
n = informe['counts']['test']
display(pd.Series(cambios))
assert abs(cambios['net_matches']/n - informe['comparison']['delta_accuracy']) < 1e-12
display(Markdown(f"Sumar estilos cambia al favorito en **{cambios['changed']} de {n}** partidos ({cambios['share']:.2%}). Ahí acierta el ranking {cambios['ranking_right']} veces y los estilos {cambios['styles_right']}: saldo de {cambios['net_matches']} partidos."))'''),
md('''## 5. Conclusión y límites

La calibración muestra probabilidades medias y frecuencias reales en ocho grupos
cuantiles; no se ajusta un calibrador con el test. Los intervalos de diferencias
son pareados por torneo (2.000 repeticiones, 290 torneos).

El estilo es una descripción útil. En este protocolo, agregarlo no muestra mejora
clara por encima del ranking. El intervalo incluye cero: no demuestra igualdad,
superioridad causal ni que los estilos jamás puedan aportar. El ampliado ganó en
validación y se conserva como modelo elegido, aunque no mejore en test.

Limitaciones: cobertura restringida a jugadores con historial; cambios de época;
fecha de torneo conservadora; clasificación de estilos débil; k heredado de la
exploración retrospectiva; dependencia entre jugadores; sólo regresión logística
y esta familia de interacciones evaluadas. No prometer acertar un encuentro particular.'''),
code('''a=informe['metrics']['Ranking + contexto']['accuracy']
b=informe['metrics']['Ranking + contexto + estilos']['accuracy']
ci=informe['comparison']['accuracy_ci95']
display(Markdown(f"**Resultado:** ranking + contexto {a:.2%}; + estilos {b:.2%}. Diferencia {(b-a)*100:+.3f} puntos porcentuales; IC95 % [{ci[0]*100:+.3f}; {ci[1]*100:+.3f}]."))
test = pd.read_csv(OUT/'predicciones_test.csv')
display(test[['fecha','nombre_a','nombre_b','estilo_a','estilo_b','p_ranking','p_estilos','gana_a']].tail(10))'''),
md('''## 6. Lo que llega a la Entrega 4

`modelo_prediccion.json` contiene escalador, centros y coeficientes; `informe.json`
contiene el protocolo, las métricas y los intervalos; `predicciones_test.csv` lleva
casos históricos con las tasas previas. `test_temporal.py` verifica exclusión actual/
futura; `entrega4/test_app.cjs` compara las probabilidades Python y JavaScript.
Los datos crudos se identifican por SHA-256. La app nunca reentrena al mover un filtro.''')]

e4=[
md('''# Entrega 4 · Entre líneas: tres estilos, una misma cancha

**Grupo 5K10-05 · Ciencia de Datos · UTN FRM · 2026**

**Idea central:** tres estilos describen 1.224 perfiles ATP; al predecir partidos
posteriores, agregarlos al ranking no muestra una mejora clara.

Este notebook comparte las funciones de datos y gráficos con la app: los números de
acá y los de la página salen de los mismos archivos. La historia completa y la
interacción están en `dist/index.html`, servida por HTTP. El README
explica reproducción y publicación; `GUIA_DEFENSA.md` explica la gramática.'''),
code('''from pathlib import Path
import json
import pandas as pd
import altair as alt
from IPython.display import display, Markdown
from build import prepare, charts, predictive_charts
ROOT=Path.cwd()
df, calidad, modelo, stats = prepare(ROOT/'inputs/jugadores.csv', ROOT/'inputs/modelo_exacto.json', ROOT/'inputs/estilos_referencia.csv')
informe=json.loads((ROOT/'inputs/informe.json').read_text(encoding='utf-8'))
specs=charts(df,calidad,stats) | predictive_charts(informe)
display(pd.Series(stats))'''),
md('''## 1. No todos los perfiles tienen la misma evidencia

Se transforma el Silver ancho a jugador–superficie. Se filtra por ≥20 partidos,
≥80 % de cobertura en saque/resto y tasas completas, como E3. Las combinaciones
candidatas incluyen superficies sin partidos. Barras apiladas desde cero:
superficie nominal a y, cantidad cuantitativa a x, calidad nominal al color.'''),
code("alt.Chart.from_dict(specs['calidad']).properties(width=750)"),
md('''## 2. Ganar más no prueba un estilo superior

Cada punto es la proporción de victorias de un estilo asignado antes del partido,
sólo sobre test 2023–2025, en todos los partidos y según el jugador llegue como mejor
o peor rankeado. Marcas de punto y regla; x para tasa e intervalo, y para la condición,
yOffset, color y forma para el estilo. Escala de 20 a 80 %, igual en las tres filas:
son puntos, no barras. El bootstrap agrupa por torneo.

Lo que prueba el título: los restadores ganan más, pero también llegan mejor rankeados.
La distancia entre filas supera a la distancia entre estilos. Sigue siendo una asociación:
el corte controla una sola variable, y entre los mejor rankeados los restadores siguen arriba.'''),
code('''display(pd.DataFrame(informe['association_rank']).round(4))
display(pd.Series(informe['best_ranked_share'], name='Llega como mejor rankeado').round(4))
alt.Chart.from_dict(specs['victorias']).properties(width=750)'''),
md('''## 3. Agregar estilos no muestra una mejora clara sobre el ranking

Comparación sobre el mismo test posterior. Barras desde cero, texto con el valor
exacto y un intervalo de la diferencia en la evidencia: se evita exagerar 0,29pp.
Las probabilidades y el método completo están en la ampliación de E3. La diferencia
tiene un tamaño concreto: son los partidos donde los modelos eligen favoritos distintos.'''),
code("display(pd.DataFrame(informe['metrics']).T)\ndisplay(pd.Series(informe['comparison']))\ndisplay(pd.Series(informe['favorite_changes']))\nalt.Chart.from_dict(specs['rendimiento']).properties(width=750)"),
md('''## 4. La copa: panorama, filtro y detalle

PC1 y PC2 son posiciones cuantitativas; estilo tiene color y forma constantes;
tooltip incluye nombre, superficie, partidos y resultado. El modelo usa siete
dimensiones, PCA sólo visualiza 58,83 %. Los controles HTML actualizan parámetros
Altair (`superficie`, `estiloFiltro`, `minPartidos`, `busqueda`) leídos por
`transform_filter`. Los dominios permanecen fijos para no alterar comparaciones.
El clic en un punto y el selector de perfil fijan el detalle, también con teclado.'''),
code("alt.Chart.from_dict(specs['grupos']).properties(width=750)"),
code("alt.Chart.from_dict(specs['centros']).properties(width=750)"),
md('''## 5. El simulador de enfrentamientos

El usuario elige superficie, temporada y dos jugadores. La app toma del catálogo las
siete tasas acumuladas al cierre de ese año, asigna el estilo de cada uno y compara tres
lecturas: ranking + contexto, el cruce de estilos con los rankings igualados, y ranking +
estilos. La fila del medio no es un tercer modelo: es el modelo ampliado con rank A = rank B.
Si comparten estilo da 50/50.

Las probabilidades de abajo las calcula Python en `generar_enfrentamientos.py`.
`test_app.cjs` comprueba que JavaScript las reproduce. Es un escenario hipotético:
el modelo se aprendió hasta 2022, y la evaluación válida es la del test.'''),
code('''catalogo = json.loads((ROOT/'inputs/enfrentamientos.json').read_text(encoding='utf-8'))
filas = []
for e in catalogo['ejemplos']:
    perfiles = {p['id']: p for p in catalogo['profiles'] if p['season']==e['season'] and p['surface']==e['surface']}
    a, b = perfiles[e['a']], perfiles[e['b']]
    filas.append({'A': e['nombre_a'], 'B': e['nombre_b'], 'superficie': e['surface'], 'temporada': e['season'],
                  'ranking A': a['ranking'], 'ranking B': b['ranking'], 'estilo A': a['estilo'], 'estilo B': b['estilo'],
                  'P(A) ranking': e['ranking'], 'P(A) estilos, ranking igualado': e['equal_ranking'], 'P(A) ranking + estilos': e['combined'],
                  'cambia el favorito': (e['ranking']>=.5)!=(e['combined']>=.5)})
pd.DataFrame(filas).round(4)'''),
code('''# Mismo gráfico de la app, con el cruce donde los estilos cambian al favorito.
e = catalogo['ejemplos'][1]
metodos = [('Ranking + contexto', e['ranking']), ('Estilos · ranking igualado', e['equal_ranking']), ('Ranking + estilos', e['combined'])]
filas = [{'metodo': m, 'jugador': e['nombre_a'], 'lado': 'A', 'probabilidad': p} for m, p in metodos]
filas += [{'metodo': m, 'jugador': e['nombre_b'], 'lado': 'B', 'probabilidad': 1-p} for m, p in metodos]
alt.Chart.from_dict(specs['enfrentamiento'] | {'datasets': {'enfrentamiento': filas}}).properties(width=750)'''),
md('''## 6. Dos usos más del modelo

El formulario descriptivo aplica los centros de E3 a siete tasas de una superficie.
La asignación es al centro más cercano, sin inventar una probabilidad. Se avisa
ante rangos no vistos, gran distancia conjunta y frontera entre centros.

El formulario supervisado permite editar rankings, superficie, formato y siete tasas
previas de cada jugador. Usa el clustering congelado hasta 2018 y la regresión
elegida en validación. No usa el mapa de carreras completas para pronosticar el pasado.
Los parámetros exportados se comprueban contra todos los casos en `test_app.cjs`.'''),
md('''## 7. Auditoría y revisión de diseño

Se encontraron 12 tasas distintas en tres perfiles entre Silver actual y E3 guardada.
Se conserva la instantánea de E3 para el mapa, reconstruyendo tasas desde Z y
escalador exacto. La predicción nueva parte del CSV de partidos. No se atribuye
una causa no verificada. Ver la auditoría debajo.

La primera versión de la app cerraba el relato con una nube PCA de tres estilos.
Tras incorporar la pregunta faltante de ganadores, se cambió el gráfico principal
final a la comparación con/sin estilos. La nube pasa a evidencia y exploración.
La conclusión ahora responde la pregunta completa, no sólo muestra clusters.

El gráfico de victorias también cambió. La primera versión tenía un punto por estilo en
una escala de 0 a 100 %: mostraba que los estilos difieren, pero no que eso no alcanzara,
que es lo que dice el título. La versión actual abre cada tasa según quién llega mejor
rankeado y recorta la escala a 20–80 %, lo que además deja leer los intervalos.'''),
code("display(pd.DataFrame(json.loads((ROOT/'inputs/auditoria_versiones.json').read_text(encoding='utf-8'))))\nalt.Chart.from_dict(specs['relacion']).properties(width=750)"),
md('''## 8. Cadena reproducible

Airflow → CSV partidos/jugadores → EDA → clustering y ampliación predictiva →
catálogo de enfrentamientos → `build.py` → JSON de datos/modelos y Altair → `dist/` →
publicación estática. El README tiene comandos exactos. Las bibliotecas se sirven
localmente, sin CDN. `VERIFICACION.md` detalla las pruebas, incluida la de Chrome real.''')]

if __name__=='__main__':
    save_run(ROOT.parent/'entrega3/Entrega3_ATP_Ampliacion_Ganadores.ipynb',e3)
    save_run(ROOT/'Entrega4_ATP_Visualizacion.ipynb',e4)
    original=ROOT.parent/'entrega3/Entrega3_ATP_Estilos_de_juego.ipynb'
    n=nbf.read(original,as_version=4)
    marker='## Ampliación de noviembre: victorias y ganadores'
    if not any(marker in c.source for c in n.cells):
        n.cells.append(md(marker+'\n\nLa pregunta sobre superioridad y predicción se completa en [Entrega3_ATP_Ampliacion_Ganadores.ipynb](Entrega3_ATP_Ampliacion_Ganadores.ipynb). Incluye historiales anteriores al partido, clustering ajustado hasta 2018, comparación con el ranking, validación temporal, probabilidades y calibración. Agregar estilos no muestra una mejora clara en test. Se conservan las celdas originales como registro del análisis descriptivo.'))
        nbf.write(n,original)
