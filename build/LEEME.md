# Cómo se trabaja

Desde el 16/11/2026 la app se edita directo acá (ya no en el artefacto de Claude).

- **App publicada:** https://chotxs.github.io/chongdashboard/ (`index.html`)
- **Prueba:** https://chotxs.github.io/chongdashboard/prueba/ (`prueba/index.html`)

La prueba lleva un cartel rojo «PRUEBA», usa sus propios datos (arranca con una copia de los
datos reales de ese dispositivo) y su propio archivo en Drive (`chongdashboard-prueba.json`),
así lo que se prueba no toca la app de verdad.

## Pasos

1. Los cambios se hacen en `prueba/index.html` y se suben a `main` (GitHub Pages publica en ~1 minuto).
2. Cuando el dueño da el OK: `python3 build/prueba.py publicar` → pasa la prueba a `index.html`
   y renueva la copia offline (`sw.js`). Subir a `main`.
3. Para rehacer la prueba desde la app publicada: `python3 build/prueba.py crear`.

Si `prueba.py` corta con «ANCHOR …», un cambio tocó una de las líneas que distinguen la prueba
de la app: ajustar la lista `PAIRS` en `build/prueba.py`.

## Antes (referencia)

`build/build.py` convertía el HTML del artefacto de Claude en la app (Google Drive en vez de Claude).
Ya no hace falta salvo que se vuelva a trabajar en el artefacto.
