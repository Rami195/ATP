# Verificación de la entrega

4 de noviembre de 2026. Todo se corrió sobre el `dist/` que incluye el simulador de
enfrentamientos, con la cadena regenerada de punta a punta.

| Prueba | Resultado |
|---|---|
| `python crear_notebooks.py` | Pasó. Los dos notebooks se ejecutaron enteros, sin celdas con error |
| `python build.py` | Pasó. Generó datos, parámetros, auditoría y 13 gráficos Altair |
| `node test_app.cjs` | Pasó. 1.224 asignaciones; 4.773 partidos con dos modelos; error máximo Python/JS 7,8e−16; 18 cruces contra Python; simetría A/B; valores inválidos rechazados; perfil extremo advertido |
| `node test_charts.cjs` | Pasó. Los 13 gráficos compilan sin warnings; render SVG; filtros y búsqueda sin coincidencias |
| `node test_dom.cjs` | Pasó. Controles del simulador, ejemplos, buscador de jugadores y números de la portada leídos del informe. Usa gráficos simulados |
| `node test_browser.cjs` | Pasó en Chrome real, servida por HTTP. Carga en unos 2,5 s; 13 gráficos con ancho correcto, también abriendo los desplegables; puntos dibujados iguales al contador al filtrar; clic en un punto; ejemplo que cambia al favorito; buscador de jugadores con teclado y mouse; sin errores de consola ni recursos faltantes; sin desborde horizontal a 390 y 768 px |
| `python ../entrega3/test_temporal.py` | Pasó. Exclusión de estadísticas actuales y futuras, y de todos los partidos de la misma fecha |

Además se recorrió la página con capturas a 1366 y 390 px de ancho.

## Lo que encontró la prueba en navegador

Las pruebas anteriores pasaban y no podían ver esto:

- Los dos gráficos del simulador tenían **ancho 0** al cargar. Nacían dentro de un bloque
  oculto y `view.resize()` no vuelve a medir el contenedor. Corregido.
- Faltaba el favicon (404 en consola). Corregido.
- La pista de «escribí un apellido» era falsa: el selector sólo busca por el inicio del
  texto y la lista estaba ordenada por nombre de pila. Ahora cada jugador se elige en un
  campo de texto que busca por cualquier parte del nombre, sin importar tildes.
- El jugador B tenía dos colores según el gráfico. Ahora tiene uno solo.
- Ejes en formato inglés y con hasta 21 marcas; leyenda de `comparacion` con formas que
  no coincidían; títulos y leyendas cortados en celular. Corregidos.

## Límites

- Se probó sólo Chrome en Windows, sin ventana. **No se probó Firefox, Safari ni un
  teléfono real**: 390 y 768 px son anchos emulados.
- **La URL pública todavía sirve la versión anterior.** Ver `PUBLICACION.md`.
- El gráfico de victorias se reformuló después de ver el test. Es descriptivo y no cambia
  ningún modelo; está declarado en el notebook y en la guía de defensa.
- Reejecutar E3 cambió bytes de `modelo_prediccion.json` y `predicciones_test.csv` por
  ruido de punto flotante: Δ coeficiente máximo 9e−15, ningún estilo ni favorito distinto.
