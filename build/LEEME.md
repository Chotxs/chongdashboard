# Cómo se publica

La app se diseña en el artefacto de Claude «Chongdashboard»:
https://claude.ai/artifact/9HCtPgYYCzvYgAGmh6qe93

Para publicar una versión nueva:

1. Bajar el HTML actual del artefacto a un archivo (por ejemplo /tmp/artefacto.html).
2. `python3 build/build.py /tmp/artefacto.html "$PWD/index.html"`
   (reemplaza lo que depende de Claude por Google Drive y OpenStreetMap, y renueva la copia offline).
3. Revisar que no haya errores y subir a `main`. GitHub Pages publica solo en ~1 minuto:
   https://chotxs.github.io/chongdashboard/

Si `build.py` corta con «ANCHOR …», un cambio del artefacto tocó una parte que el build reemplaza: ajustar ese reemplazo en `build.py`.
