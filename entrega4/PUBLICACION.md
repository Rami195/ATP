# Publicación

## Estado

**Pendiente de republicar.** `dist/` tiene la versión final, con el simulador de
enfrentamientos, pero la URL pública sigue sirviendo la versión 1, sin simulador.

URL pública: <https://atp-estilos-5k10-entrega4.superpoppy259.chatgpt.site>

Último despliegue confirmado (versión 1), 4 de noviembre de 2026, 21:22
(America/Argentina/Buenos_Aires). Estado devuelto por Sites: **succeeded**. Acceso: **public**.

- Proyecto: `appgprj_6aebc6a4f75081919b70e1158086f8c6`
- Versión: `appgprj_6aebc6a4f75081919b70e1158086f8c6~appgver_1c608f1756a48191817c54e7c367f7d0`
- Despliegue: `appgdep_6aebcc4153b48191a8f76b2b51511087`
- Commit publicado: `049e10fe02a4f51e0736a1805194334ca7cbf21a`

## Cómo actualizarla

La copia de trabajo Git de Sites se conserva fuera del repositorio académico, en
`CienciaDatos/_publicacion_sites/atp-estilos/`, y ya está sincronizada con la versión
final. Así `Proyecto/entrega4` sigue siendo una carpeta normal que el grupo puede
versionar en su repositorio.

Para publicar, solicitar una credencial temporal y seguir el helper del mismo Site, como
indica `plan/CONTINUAR_ENTREGA4.md`. Esas herramientas son de Codex. No crear otro Site
ni guardar tokens en archivos.

`dist/` es un sitio estático: también puede publicarse en cualquier hosting estático,
como GitHub Pages. Si se cambia de hosting, actualizar la URL en este archivo.

Después de publicar, abrir la URL desde otra computadora y sin sesión, y comprobar que
aparece la sección «Tu cancha. Tu enfrentamiento.». También se puede correr
`node test_browser.cjs <url>` contra la URL pública.
