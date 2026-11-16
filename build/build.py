import re, sys, json, os
# Uso: python3 build.py ARTEFACTO.html SALIDA/index.html
# Convierte el HTML del artefacto de Claude en la app independiente (Google Drive en vez de Claude).
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else 'orig.html'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'index.html'
os.chdir(HERE)
src = open(SRC, encoding='utf-8').read()
# si viene con la envoltura del visor, quedarse con el documento de adentro
if src.count('<!DOCTYPE html>') == 1 and not src.lstrip().startswith('<!DOCTYPE html>'):
    src = src[src.index('<!DOCTYPE html>'):]
    src = src[:src.rindex('</html>') + len('</html>')] + '\n'
t = src

def rep(old, new, count=1):
    global t
    n = t.count(old)
    if n != count:
        sys.exit(f'ANCHOR x{n} (esperado {count}): {old[:90]!r}')
    t = t.replace(old, new)

def cut_between(start, end, new, keep_end=True):
    global t
    i = t.index(start); j = t.index(end, i)
    t = t[:i] + new + (t[j:] if keep_end else t[j + len(end):])

client_id = os.environ.get('GOOGLE_CLIENT_ID', '439653384390-if8q4e0v72apn5568r2skgtghcjv5r6a.apps.googleusercontent.com')

# ---------- cabecera: título, PWA, iOS ----------
rep('<title>Chongdashboard (Copy)</title>', '''<title>Chongdashboard</title>
<meta name="description" content="Tu ruleta social: a quién ver, cuándo y dónde.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Chongdashboard">''')

# ---------- módulos de Google antes del almacenamiento ----------
google = open('parts/google.js', encoding='utf-8').read().replace('__GOOGLE_CLIENT_ID__', client_id)
rep('/* ===== Almacenamiento: navegador (siempre) + base de datos privada de la cuenta (si está disponible) ===== */',
    google + '/* ===== Almacenamiento: este dispositivo (siempre) + copia en tu Google Drive (si iniciaste sesión) ===== */')

# ---------- estado interno del Store ----------
rep("state: null, backend: 'navegador', syncStatus: 'local', db: null, col: null,\n    synced: {}, timer: null, flushing: false, again: false,",
    "state: null, backend: 'navegador', syncStatus: 'local', fileId: null, fileReady: false, remoteModified: null,\n    lastPushed: null, timer: null, flushing: false, again: false,")
rep("weekly: { enabled: false, day: 0, last: null },\n      },",
    "weekly: { enabled: false, day: 0, last: null },\n        igDrive: { auto: true, lastCheck: null, lastSync: null, seen: [] },\n      },")
rep("out.settings.weekly = { ...d.settings.weekly, ...((s.settings || {}).weekly || {}) };",
    "out.settings.weekly = { ...d.settings.weekly, ...((s.settings || {}).weekly || {}) };\n    out.settings.igDrive = { ...d.settings.igDrive, ...((s.settings || {}).igDrive || {}) };")
cut_between('  // --- documentos remotos: core + uno por amigo + uno por año de encuentros ---',
            '/* ===== Utilidades ===== */',
            open('parts/store_remote.js', encoding='utf-8').read() + '\n')

# ---------- funciones que usaban Claude ----------
rep("_sample = (window.claude && typeof window.claude.use === 'function')\n      ? window.claude.use('sample').catch(() => null)\n      : Promise.resolve(null);",
    "_sample = Promise.resolve(null); // fuera de Claude: el nombre se deduce en el teléfono")
rep("let claudeBlocked = false;", "let claudeBlocked = true;")

geo_new = '''/**
 * Ubica lugares con OpenStreetMap (Nominatim), de a uno y respetando su límite de 1 consulta por segundo.
 * items: [{id, text}] → { id: {lat, lng} | null }
 */
async function claudeGeocode(items, refText, signal) {
  const out = {};
  const ask = async q => {
    const u = 'https://nominatim.openstreetmap.org/search?' + new URLSearchParams({ q, format: 'jsonv2', limit: '1', 'accept-language': 'es' });
    const r = await fetch(u, { signal, headers: { Accept: 'application/json' } });
    if (!r.ok) throw { code: 'geo_http' };
    const j = await r.json();
    const g = j && j[0] ? { lat: Number(j[0].lat), lng: Number(j[0].lon) } : null;
    return validGeo(g) ? g : null;
  };
  const wait = () => new Promise(res => setTimeout(res, 1100));
  let first = true;
  for (const it of items) {
    const text = String(it.text || '').replace(/\\bCABA\\b/gi, 'Ciudad Autónoma de Buenos Aires');
    const tries = [text];
    if (refText && it.id !== 'me' && !text.includes(',')) tries.push(`${text}, ${refText}`);
    if (!/argentina/i.test(text)) tries.push(`${text}, Argentina`);
    let g = null;
    for (const q of tries) {
      if (!first) await wait(); first = false;
      try { g = await ask(q); } catch (e) { if (e && e.name === 'AbortError') throw e; g = null; }
      if (g) break;
    }
    out[String(it.id)] = g;
  }
  return out;
}
'''
cut_between('/**\n * Pide a Claude coordenadas estimadas para varios lugares en una sola consulta.', '/* ===== Vistas ===== */', geo_new + '\n')
rep("Las posiciones las estima Claude a partir del texto de cada ubicación", "Las posiciones salen de OpenStreetMap a partir del texto de cada ubicación")

# ---------- descargas ----------
rep("""    const dl = window.claude && window.claude.use ? await window.claude.use('downloads') : null;
    if (dl) { await dl.save({ filename, data }); toast(`${label} guardado`); return; }
  } catch (e) {
    if (e && e.code === 'declined') return;""",
"""    const type = /\\.csv$/i.test(filename) ? 'text/csv' : 'application/json';
    const file = new File([data], filename, { type });
    if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file], title: label }); return; }
    const url = URL.createObjectURL(file), a = document.createElement('a');
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000); toast(`${label} guardado`); return;
  } catch (e) {
    if (e && e.name === 'AbortError') return;""")

# ---------- ajustes: cuenta de Google ----------
rep("""      const syncTxt = Store.backend === 'cuenta'
        ? ({ ok: 'Guardado en tu cuenta de Claude: lo ves desde cualquier dispositivo.', pendiente: 'Guardando en tu cuenta…', error: 'No se pudo guardar en tu cuenta; quedó guardado en este navegador.', lleno: 'Tu espacio en la cuenta está lleno; quedó guardado en este navegador.' }[Store.syncStatus] || 'Guardado en tu cuenta.')
        : 'Guardado en este navegador. Abrí la app desde claude.ai con tu cuenta para sincronizar entre dispositivos.';""",
"""      const syncTxt = Store.backend === 'cuenta'
        ? ({ ok: 'Guardado en tu Google Drive: lo ves desde cualquier dispositivo donde entres con tu cuenta.', pendiente: 'Guardando en tu Google Drive…', error: 'No se pudo guardar en Drive; quedó guardado en este dispositivo y se reintenta solo.', auth: 'Tu sesión de Google venció; quedó guardado en este dispositivo.' }[Store.syncStatus] || 'Guardado en tu Google Drive.')
        : 'Guardado solo en este dispositivo. Conectá Google para tenerlo en la nube y en todos tus dispositivos.';""")
rep("""        <div class="hr"></div><h3>Tus datos</h3>""",
"""        <div class="hr"></div><h3>Cuenta de Google</h3>
        ${!GOOGLE_READY ? '<p class="small muted">Falta configurar el acceso a Google en la app.</p>'
          : GAuth.token() ? `<p class="small" style="margin:6px 0 10px">Conectada. Tus datos se guardan en una carpeta privada de tu Drive y la app lee ahí las exportaciones de Instagram.</p><button class="btn sm ghost" data-a="g-out">Desconectar Google</button>`
          : `<p class="small" style="margin:6px 0 10px">${GAuth.error ? esc(GAuth.error) + ' ' : ''}Conectá tu cuenta para guardar todo en la nube y leer las exportaciones de Instagram de tu Drive.</p><button class="btn sm primary" data-a="g-in">Conectar con Google</button>`}
        <div class="hr"></div><h3>Tus datos</h3>""")

# ---------- importar de Instagram: recuadro de Drive ----------
rep("function openIgImport() {\n  const L = { busy: false, err: '', result: null };",
    open('parts/igdrive.js', encoding='utf-8').read() +
    "function openIgImport() {\n  const L = { busy: false, err: '', result: null, dBusy: false, dMsg: '', dErr: false };")
rep("""    title: 'Importar de Instagram',
    render() {
      const igc = st().igContacts;""",
"""    title: 'Importar de Instagram',
    actions: {
      'ig-drive-sync': async () => {
        if (L.dBusy) return;
        L.dBusy = true; L.dMsg = ''; L.dErr = false; renderSheet(sh);
        try { const r = await syncIgFromDrive(); L.dMsg = igDriveSummary(r); }
        catch (e) { L.dMsg = igDriveError(e); L.dErr = true; }
        L.dBusy = false; if (topSheet() === sh) renderSheet(sh);
      },
      'ig-drive-off': () => { Store.update(s => { s.settings.igDrive = { ...(s.settings.igDrive || {}), auto: false }; }); L.dMsg = 'Lectura automática desactivada.'; L.dErr = false; renderSheet(sh); },
      'ig-drive-on': () => { Store.update(s => { s.settings.igDrive = { ...(s.settings.igDrive || {}), auto: true }; }); L.dMsg = 'Lectura automática activada.'; L.dErr = false; renderSheet(sh); },
    },
    render() {
      const igc = st().igContacts;
      const gd = st().settings.igDrive || {};
      const on = !!GAuth.token();
      const driveBox = !GOOGLE_READY ? '' : `<div class="card flat" style="margin:0 0 16px"><div class="row between"><h3>☁️ Google Drive</h3>${on && gd.auto !== false ? '<span class="tag ok">Automático</span>' : ''}</div>
        <p class="small muted" style="margin:6px 0 10px">${!on ? 'Conectá Google y la app lee sola las exportaciones semanales de Instagram que llegan a tu Drive.' : gd.auto !== false ? 'Cada vez que abrís la app (como mucho cada 12 h) reviso tu Drive y sumo las exportaciones nuevas.' : 'La lectura automática está apagada.'}${gd.lastSync ? ` Última carga: ${esc(new Date(gd.lastSync).toLocaleString('es-AR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }))}.` : ''}</p>
        <div class="row wrap">${!on ? '<button class="btn sm primary" data-a="g-in">Conectar con Google</button>' : `<button class="btn sm primary" data-a="ig-drive-sync" ${L.dBusy ? 'disabled' : ''}>${L.dBusy ? 'Leyendo Drive…' : 'Revisar ahora'}</button>${gd.auto !== false ? '<button class="btn sm ghost" data-a="ig-drive-off">Apagar automático</button>' : '<button class="btn sm ghost" data-a="ig-drive-on">Activar automático</button>'}`}</div>
        ${L.dMsg ? `<p class="${L.dErr ? 'error' : 'small'}" role="${L.dErr ? 'alert' : 'status'}" style="margin:10px 0 0">${esc(L.dMsg)}</p>` : ''}</div>`;""")
rep('return `<p style="margin-top:0">Instagram no deja que otras apps lean tus seguidores.',
    'return `${driveBox}<p style="margin-top:0">Instagram no deja que otras apps lean tus seguidores.')

# ---------- acciones globales de Google ----------
rep("const globalActions = {\n",
    """const globalActions = {
  'g-in': () => GAuth.signIn(false),
  'g-out': () => confirmSheet({ title: 'Desconectar Google', text: 'Tus datos quedan guardados en este dispositivo y en tu Drive. Dejan de sincronizarse hasta que vuelvas a conectar.', ok: 'Desconectar', onOk: () => { GAuth.signOut(); Store.disconnect(); toast('Google desconectado'); } }),
""")

# ---------- aviso en Inicio si falta conectar ----------
rep("""  if (hasDemo) html += `<div class="notice demo section\"""",
    """  if (GOOGLE_READY && !GAuth.token()) html += `<div class="notice section" style="margin-top:16px">${GAuth.wasSignedIn ? 'Tu sesión de Google venció.' : 'Tus datos están solo en este dispositivo.'} <button class="link" data-a="g-in">Conectar con Google</button> para guardarlos en la nube.</div>`;
  if (hasDemo) html += `<div class="notice demo section\"""")

# ---------- arranque ----------
rep("function boot() {\n  Store.init();\n  if (!st().meta.initialized) { Store.update(s => { s.meta.initialized = true; }); loadDemo(); }",
    "function boot() {\n  GAuth.capture();\n  if (GAuth.renewIfNeeded()) return; // vuelve solo, ya con sesión\n  Store.init();\n  if (!st().meta.initialized) { Store.update(s => { s.meta.initialized = true; }); loadDemo(); Store.unstamp(); }")
rep("  Store.connectRemote(() => { session.result = null; });",
    """  Store.connectRemote(() => { session.result = null; }).finally(() => autoIgDrive());
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { Store.pull(); autoIgDrive(); } });
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});""")

# la primera vez sin datos no se cargan ejemplos si después llega la copia de Drive: se mantiene igual que antes

assert 'window.claude' not in t, [m.start() for m in re.finditer('window.claude', t)]
open(OUT if os.path.isabs(OUT) else os.path.join(os.getcwd(), OUT), 'w', encoding='utf-8').write(t)
# nueva versión de la copia offline para que el iPhone baje la actualización
import hashlib
outp = OUT if os.path.isabs(OUT) else os.path.join(os.getcwd(), OUT)
sw = os.path.join(os.path.dirname(outp), 'sw.js')
if os.path.exists(sw):
    s = open(sw, encoding='utf-8').read()
    s = re.sub(r"chongdashboard-v[\w-]+", 'chongdashboard-v' + hashlib.sha1(t.encode()).hexdigest()[:8], s)
    open(sw, 'w', encoding='utf-8').write(s)
print('ok', len(t))
