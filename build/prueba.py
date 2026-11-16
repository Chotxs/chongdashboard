import sys, os, re, hashlib
# Uso:
#   python3 build/prueba.py crear     -> arma prueba/index.html a partir de index.html (la app publicada)
#   python3 build/prueba.py publicar  -> pasa prueba/index.html a index.html (la app publicada)
# La prueba usa sus propios datos (copia inicial de los reales) y su propio archivo en Drive,
# así lo que se prueba no toca los datos de la app.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'index.html')
TEST = os.path.join(ROOT, 'prueba', 'index.html')

BANNER = ('<div id="prueba-flag" style="position:fixed;top:env(safe-area-inset-top,0px);left:50%;transform:translateX(-50%);'
          'z-index:99999;background:#E5484D;color:#fff;font:600 11px -apple-system,BlinkMacSystemFont,sans-serif;'
          'letter-spacing:.08em;padding:2px 10px;border-radius:0 0 8px 8px;pointer-events:none">PRUEBA</div>')

PAIRS = [  # (app publicada, prueba, veces)
    ('<title>Chongdashboard</title>', '<title>Chongdashboard · PRUEBA</title>', 1),
    ('href="manifest.webmanifest"', 'href="../manifest.webmanifest"', 1),
    ('href="icons/', 'href="../icons/', 2),
    ("const APP_FILE = 'chongdashboard.json';", "const APP_FILE = 'chongdashboard-prueba.json';", 1),
    ("const LS_KEY = 'mi-ruleta-social:v1';",
     "const LS_KEY = 'mi-ruleta-social:prueba'; /* PRUEBA: arranca con una copia de los datos reales */ "
     "try { if (!localStorage.getItem(LS_KEY) && localStorage.getItem('mi-ruleta-social:v1')) localStorage.setItem(LS_KEY, localStorage.getItem('mi-ruleta-social:v1')); } catch (e) {}", 1),
    ("  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});",
     "  /* PRUEBA: sin copia offline */", 1),
    ('<body>\n', '<body>\n' + BANNER + '\n', 1),
]

def swap(text, a_to_b):
    for a, b, n in PAIRS:
        old, new = (a, b) if a_to_b else (b, a)
        c = text.count(old)
        if c != n:
            sys.exit(f'ANCHOR x{c} (esperado {n}): {old[:90]!r}')
        text = text.replace(old, new)
    return text

mode = sys.argv[1] if len(sys.argv) > 1 else ''
if mode == 'crear':
    t = swap(open(MAIN, encoding='utf-8').read(), True)
    os.makedirs(os.path.dirname(TEST), exist_ok=True)
    open(TEST, 'w', encoding='utf-8').write(t)
    print('prueba creada', len(t))
elif mode == 'publicar':
    t = swap(open(TEST, encoding='utf-8').read(), False)
    for mark in ('prueba-flag', 'mi-ruleta-social:prueba', 'chongdashboard-prueba.json', '/* PRUEBA'):
        assert mark not in t, 'quedó algo de la prueba: ' + mark
    open(MAIN, 'w', encoding='utf-8').write(t)
    sw = os.path.join(ROOT, 'sw.js')
    s = open(sw, encoding='utf-8').read()
    s = re.sub(r"chongdashboard-v[\w-]+", 'chongdashboard-v' + hashlib.sha1(t.encode()).hexdigest()[:8], s)
    open(sw, 'w', encoding='utf-8').write(s)
    print('publicada', len(t))
else:
    sys.exit('uso: prueba.py crear | publicar')
