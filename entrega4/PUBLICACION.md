# Publicación

## Estado

**Pendiente.** La consigna admite GitHub Pages o Streamlit Community Cloud, desde el
repositorio del grupo. Esta app es una página HTML, así que corresponde **GitHub Pages**.
La URL va a ser <https://rami195.github.io/ATP/>.

La versión de `chatgpt.site` fue un paso intermedio: está desactualizada y no es una de
las dos formas de la consigna. No usarla para la entrega.

## Cómo publicar

Con `dist/` ya generada y commiteada en `main`, desde la carpeta `Proyecto`:

```powershell
git subtree push --prefix entrega4/dist origin gh-pages
```

Después, una sola vez, en <https://github.com/Rami195/ATP/settings/pages>: en **Source**
elegir **Deploy from a branch**, en **Branch** elegir `gh-pages` y `/ (root)`, y **Save**.
GitHub tarda uno o dos minutos.

Cada vez que cambie la app hay que regenerar, commitear, pushear `main` y repetir el
`git subtree push`.

## Antes de la entrega

Abrir la URL desde otra computadora y sin sesión, y comprobar que carga. También se puede
correr `node test_browser.cjs https://rami195.github.io/ATP/`.
