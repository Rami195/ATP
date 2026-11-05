# Guía para defender la entrega · 25 minutos

Todos deben poder explicar todo. El reparto siguiente organiza el recorrido,
no asigna preguntas exclusivas a integrantes.

## Una oración para abrir

«Encontramos tres estilos de saque y devolución. Sirven para describir 1.224
perfiles, pero agregar esos estilos al ranking no mejora claramente la predicción
en los 4.773 partidos posteriores que pudimos evaluar».

## Los 25 minutos

| Min. | Momento | Qué hacer |
|---|---|---|
| 0–2 | Qué cambió | Dos oraciones, ver abajo |
| 2–10 | El tallo | Portada, datos, hallazgo y modelo, en orden. Como si el docente no conociera el proyecto |
| 10–15 | La copa | **El docente toma el mouse.** Explora los datos y prueba el modelo con un caso propio |
| 15–22 | Preguntas | Dirigidas a integrantes puntuales, sobre cualquier parte de la app o del repositorio |
| 22–25 | Devolución | Anotar qué hay que corregir antes del 25/11 |

Llegar con la URL pública y el repositorio con el README ya abiertos.

**Completar antes de entrar:** «Qué cambió» y «Lo que te marcamos en la Entrega 3» dependen
de la devolución del docente, que no está en el repositorio. Sumarla acá, con lo resuelto
o la explicación de por qué no se pudo. Lo que sí cambió desde E3: se agregó la pregunta
de ganadores, con validación temporal y clustering congelado hasta 2018.

## Por qué cada título afirma lo que afirma

| Sección | Título | Número que lo sostiene |
|---|---|---|
| Portada | Tres estilos describen 1.224 perfiles; sumarlos al ranking no muestra una mejora clara | 1.224; 64,47 %; 64,17 % |
| Los datos | Sólo 1.224 de 3.470 perfiles tienen evidencia suficiente | 3.470 con partidos, 1.304 con ≥20, 1.224 con cobertura ≥80 % |
| Lo que encontramos | Sacar fuerte y devolver bien tiran en sentidos opuestos | r = −0,50 en 1.224 perfiles; −0,58 con ≥50 partidos |
| El modelo | Acierta el 64 % de los partidos, y los estilos no lo mejoran | 64,47 % contra 64,17 %, 14 partidos de diferencia, piso 64,47 % |

El título de «Lo que encontramos» es H5, que quedó **inconclusa**: el signo se cumple, pero
−0,58 no llega al umbral de −0,6 que fijamos antes. La palabra «opuestos» describe el signo,
no un compromiso fuerte, y por eso el texto dice «tendencia, no regla». Decirlo antes de
que lo pregunten. Las hipótesis para citar: H2 se sostuvo (r = 0,86) y H6 no (r = −0,05).

## Los números que hay que saber ubicar

- 77.474 partidos de fuente, 2000–2025; Silver con 1.450 jugadores y 157 columnas.
- 4.350 combinaciones candidatas = 1.450×3 (incluyen combinaciones sin partidos).
- 1.224 perfiles confiables, de 582 jugadores: cemento 514, clay 451, grass 259.
- Tres estilos: 326 sacadores, 496 restadores, 402 saque frágil.
- Silhouette 0,171: estructura débil; 73,4 % por debajo de 0,25; 6,9 % negativo.
- PCA dos componentes = 58,83 %. K-means opera en siete dimensiones.
- Nuevo test: 4.773 de 8.423 partidos con superficie válida y sin walkover.
- Victorias en ese test: restadores 51,42 %, sacadores 48,61 %, saque frágil42,35 %.
  Son participaciones, no porcentajes de jugadores únicos.
- Llegan como mejor rankeado: restadores 53,8 %, sacadores 45,1 %, saque frágil 33,4 %.
- Victorias como mejor rankeado: 66,0 / 61,6 / 56,4 %. Como peor rankeado: 34,4 / 37,9 / 35,3 %.
- Validación, media ± desvío entre cuatro años: log-loss 0,6316 ± 0,0114 base y
  0,6289 ± 0,0126 ampliado. La diferencia es mucho menor que el desvío.
- Sin ranking, log-loss 0,692, casi como el azar (0,693). Sin estilos, 0,6295: mejor
  que el modelo completo (0,6306). El modelo se apoya en el ranking.
- Acierta 54,5 % con rankings parecidos y 76,3 % con rankings lejanos. Cuando gana el
  peor rankeado acierta 2,9 %: sigue al ranking, así que no ve las sorpresas.
- Accuracy: ranking 64,47 %; + estilos 64,17 %. Diferencia −0,293pp.
  IC95 [−0,730; +0,114]pp: incluye cero.
- Sumar estilos cambia al favorito en 112 de 4.773 partidos (2,35 %). Ahí acierta el
  ranking 63 veces y los estilos 49. Ese saldo de 14 partidos **es** el −0,293pp:
  14 / 4.773 = 0,293 %.
- El ampliado ganó validación, pero no test. Se mantiene la selección de validación.

## Leer un gráfico componente por componente

| Vista | Datos y transformación | Marca y mapeo | Escalas y motivo |
|---|---|---|---|
| Calidad | Perfil candidato; conteo por superficie/estado | Barras; cantidad→x, superficie→y, estado→color | Lineal desde 0: compara longitudes |
| Aces/resto (sección 2) | Tasas z dentro de cada superficie; regresión Altair | Puntos+recta; aces→x, resto→y | Lineal, no parte de 0: son puntos |
| Coeficientes | Coeficientes del modelo ampliado | Barras; coeficiente→x, variable→y, bloque→color | −0,6 a 0,6, simétrica: a la derecha favorece al primero del par |
| Victorias (evidencia) | Participación de test por condición y estilo; media de resultado, bootstrap por torneo | Punto+regla; tasa→x, condición→y, estilo→yOffset/color/forma; intervalo→x y x2 | 20–80 %, igual en las tres filas; son puntos, no barras; referencia 50 % |
| Comparación | Mismos partidos, proporción correcta del piso y los dos modelos | Barras+texto; accuracy→x, modelo→y | 0–100 %; no agrandar 0,29pp con eje cortado |
| PCA | Perfiles z; proyección sólo para mostrar | Puntos; PC1/PC2→posición, estilo→color y forma | Dominios globales fijos incluso al filtrar |
| Centros | Medias z por estilo/rasgo | Puntos; z→x, rasgo→y, estilo→color/forma | Misma escala de desvíos para siete rasgos |
| Calibración | Predicciones test; 8 bins cuantiles | Puntos+línea; p media→x, frecuencia→y | Ambos 0–1; diagonal ideal |
| Distancias | Caso nuevo estandarizado; norma euclídea | Barras; distancia→x, estilo→y/color | Desde0; menor es más cercano, no probabilidad |
| Enfrentamiento | Tres lecturas de P(A) y su complemento, calculadas en el navegador | Barras apiladas; probabilidad→x, método→y, lado→color | 0–100 % fijo; cada fila suma 100 % |
| Rasgos del cruce | Siete tasas de los dos jugadores, estandarizadas | Puntos; z→x, rasgo→y, lado→color/forma | Misma escala de desvíos para los siete rasgos |

El color nominal conserva la paleta original de E3: naranja sacadores, celeste
restadores, verde saque frágil. Forma redundante en PCA ayuda a distinguir sin color.
Los grises/verdes oscuros de calidad o modelos no son categorías de estilo.
El jugador A es siempre verde oscuro y el B siempre gris, en los dos gráficos del simulador.

## Qué toca cada control

Superficie, estilo, mínimo de partidos y búsqueda cambian **parámetros**, que lee
`transform_filter` en Altair. Cambian las filas visibles. No cambian los centros ni
reentrenan. El tooltip agrega detalle en el mapeo. El selector permite ver ese detalle
sin mouse, y el clic en un punto lo fija. El formulario es inferencia: transforma
valores y calcula el resultado.

En el simulador los controles no tocan un parámetro: superficie, año y jugadores cambian
los **datos** del gráfico. JavaScript recalcula el modelo y reemplaza las filas con
`vega.changeset()`. Marca, mapeo y escalas quedan fijos, y por eso la escala 0–100 % no
se mueve entre un cruce y otro. Formato (3 o 5 sets) entra al modelo como interacción.
El campo de cada jugador sólo busca en la lista: el gráfico cambia recién al elegir a alguien.

## Cómo llega el modelo a la app

`completar_prediccion.py` exporta medias, desvíos, centros y coeficientes a JSON.
`web/modelo.js` hace las mismas cuentas en el navegador: estandariza, busca el centro
más cercano y aplica la logística. No hay servidor ni modelo sustituto. `test_app.cjs`
compara contra Python las 1.224 asignaciones y las 4.773 × 2 probabilidades, con error
máximo menor a 1e−15.

La fila «estilos con ranking igualado» es el mismo modelo ampliado con rank A = rank B.
No es un tercer modelo y no tiene accuracy propia. Si te preguntan por qué Nadal y
Federer dan 50/50: comparten estilo, y el contraste de estilos vale cero.

## Por qué hubo que volver a calcular estilos para predecir

La E3 descriptiva usa la carrera de 2000–2025. Usarla para predecir un encuentro de
2023 dejaría entrar estadísticas de 2024/2025. La ampliación ajusta el escalador y
centros sólo hasta 2018, los congela y asigna cada caso con sus tasas previas.
K=3 viene de la investigación retrospectiva original: no presentar este análisis
como prerregistro ni como validación completamente externa de esa decisión.

La fecha disponible es inicio de torneo, no día de cada encuentro. Por prudencia
se excluye toda la fecha actual. Se pierde algo de información que podría estar
disponible en rondas posteriores, a cambio de no inventar un orden temporal fiable.

## Por qué no decimos «el mejor estilo»

Los restadores ganan más en la muestra, pero no se asignaron estilos aleatoriamente:
pueden tener mejores rankings, otros rivales y diferente permanencia. Además, las
tasas de rendimiento ya se relacionan con nivel. La comparación supervisada pregunta
si el estilo añade información al ranking en este protocolo, no si causa victorias.

No encontrar mejora tampoco prueba que nunca sirva: sólo probamos esta familia de
modelos, tasas y períodos, con estructura de estilos débil y cobertura limitada.

## Una revisión de diseño real de esta implementación

La primera versión de E4 cerraba con una nube PCA y «tres estilos, ninguna isla».
Era útil para clustering, pero no respondía la pregunta faltante de ganadores que
se incorporó después. Se pasó el mapa a evidencia/exploración y se puso como gráfico
final la comparación de aciertos con/sin estilos, con la misma población de test.
Se mantuvieron barras desde cero y se añadieron etiquetas/intervalo: truncar el eje
haría parecer grande una diferencia de apenas 0,29 puntos porcentuales.

El gráfico de victorias también cambió. La primera versión tenía un punto por estilo
en una escala de 0 a 100 %. Mostraba que los estilos difieren, pero no que eso no
alcanzara, que es lo que afirma el título; además, los intervalos casi no se veían. La
versión actual abre cada tasa según quién llega mejor rankeado y recorta la escala a
20–80 %. Se puede recortar porque son puntos: la posición no depende de una longitud.
Este corte se agregó después de ver el test. Es descriptivo y no toca ningún modelo:
decirlo antes de que lo pregunten.

Después ese gráfico salió del tallo. Al leer la consigna completa, la sección dos tenía que
cerrar la Entrega 2 y estaba mostrando un resultado de E3. Su lugar lo tomó aces contra resto,
que estaba escondido en un desplegable, y victorias pasó a la evidencia del modelo.

Esto describe una revisión del artefacto; no afirmar que cada integrante hizo un
ensayo anterior que no hizo. Cada uno debe practicar el gráfico que le pregunten.

## Casos raros y probabilidades

K-means siempre asigna al más cercano. Eso no significa que el caso sea típico.
Se rechazan tasas imposibles, faltantes y superficies desconocidas. Se avisa por
rango marginal no visto y, en el formulario descriptivo, distancia conjunta mayor
al percentil 95 y frontera entre dos centros. Una distancia no es una probabilidad.

La logística da P(A), con P(B)=1−P(A). Un favorito de 60 % puede perder 40 % de las
veces bajo buena calibración. El formulario usa rangos conocidos como advertencia,
no como garantía de que cualquier combinación sea habitual. No interpreta el
partido precargado como futuro real: es un ejemplo histórico con features previas.

## Auditoría que conviene poder explicar

Hay 12 valores diferentes en 3 perfiles entre Silver local y Z guardado en E3.
Se registra la diferencia, sin inventar la causa. El mapa conserva el snapshot E3
y el análisis nuevo usa partidos con su hash. La app publica esa auditoría.
La correlación estandarizada de la nube mostrada es−0,5025, no el−0,58 citado para
otra etapa/filtro del EDA. Los números se calculan sobre la población del gráfico.

## Si cambian los datos

```powershell
cd entrega4
python build.py --pipeline ../airflow-atp/include/output
```

Toma los CSV del DAG, reentrena con semilla 42 y genera `dist/`. Después hay que correr las
pruebas, subir `dist/` y revisar los textos de conclusión. Las hipótesis de E2 requieren
reejecutar ese notebook.

## Antes de ir al aula

Abrir la URL pública desde otro dispositivo y sin sesión. Probar filtros, un caso
sin coincidencias, un caso nuevo normal y uno extremo, y los tres ejemplos del simulador.
Leer README y ejecutar reproducción una vez. `test_browser.cjs` prueba la página en
Chrome, pero no reemplaza que cada integrante la recorra y pueda explicarla.
