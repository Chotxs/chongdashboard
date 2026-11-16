/* ===== Configuración ===== */
// Client ID de Google (Google Cloud → Credenciales → ID de cliente de OAuth, tipo «Aplicación web»).
const GOOGLE_CLIENT_ID = '__GOOGLE_CLIENT_ID__';
const GOOGLE_READY = /\.apps\.googleusercontent\.com$/.test(GOOGLE_CLIENT_ID);

/* ===== Inicio de sesión con Google (sin servidor: el permiso vuelve en la dirección) ===== */
const GAuth = (() => {
  const KEY = 'cd:gtoken', FLAG = 'cd:google', TRIED = 'cd:gsilent', STATE = 'cd:gstate';
  const SCOPES = 'https://www.googleapis.com/auth/drive.appdata https://www.googleapis.com/auth/drive.readonly';
  let lastError = '';
  const ls = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sin espacio */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* nada */ } },
  };
  function saved() { try { const t = JSON.parse(ls.get(KEY)); return t && t.token ? t : null; } catch (e) { return null; } }
  function token() { const t = saved(); return t && t.exp > Date.now() + 60000 ? t.token : null; }
  function redirectUri() { return location.origin + location.pathname; }
  /** Lee el resultado que Google deja en la dirección (#access_token=… o #error=…). */
  function capture() {
    const h = location.hash || '';
    if (!/access_token=|error=/.test(h)) return;
    const p = new URLSearchParams(h.slice(1));
    let expected = null; try { expected = sessionStorage.getItem(STATE); } catch (e) { /* nada */ }
    history.replaceState(null, '', location.pathname + location.search);
    if (expected && p.get('state') !== expected) { lastError = 'La respuesta de Google no coincide. Probá de nuevo.'; return; }
    if (p.get('access_token')) {
      ls.set(KEY, JSON.stringify({ token: p.get('access_token'), exp: Date.now() + (Number(p.get('expires_in')) || 3600) * 1000 }));
      ls.set(FLAG, '1'); ls.del(TRIED); lastError = '';
    } else {
      const err = p.get('error');
      if (!['interaction_required', 'login_required', 'consent_required'].includes(err)) lastError = err === 'access_denied' ? 'No diste permiso a Google Drive.' : 'Google no pudo iniciar la sesión.';
    }
  }
  function signIn(silent = false) {
    if (!GOOGLE_READY) return;
    const state = Math.random().toString(36).slice(2) + Date.now().toString(36);
    try { sessionStorage.setItem(STATE, state); } catch (e) { /* nada */ }
    if (silent) ls.set(TRIED, String(Date.now()));
    const q = new URLSearchParams({ client_id: GOOGLE_CLIENT_ID, redirect_uri: redirectUri(), response_type: 'token', scope: SCOPES, include_granted_scopes: 'true', state });
    if (silent) q.set('prompt', 'none');
    location.assign('https://accounts.google.com/o/oauth2/v2/auth?' + q.toString());
  }
  /** Si ya había iniciado sesión y el permiso venció, lo renueva sin preguntar (una vez cada 10 min como mucho). */
  function renewIfNeeded() {
    if (!GOOGLE_READY || token() || ls.get(FLAG) !== '1') return false;
    const tried = Number(ls.get(TRIED)) || 0;
    if (Date.now() - tried < 10 * 60000) return false;
    signIn(true); return true;
  }
  function signOut() {
    const t = saved();
    if (t) fetch('https://oauth2.googleapis.com/revoke?token=' + encodeURIComponent(t.token), { method: 'POST' }).catch(() => {});
    ls.del(KEY); ls.del(FLAG); ls.del(TRIED);
  }
  function expire() { ls.del(KEY); }
  return { capture, signIn, signOut, renewIfNeeded, token, expire, get wasSignedIn() { return ls.get(FLAG) === '1'; }, get error() { return lastError; } };
})();

/* ===== Google Drive: copia de la app y lectura de exportaciones de Instagram ===== */
const Drive = (() => {
  const API = 'https://www.googleapis.com/drive/v3', UP = 'https://www.googleapis.com/upload/drive/v3';
  const APP_FILE = 'chongdashboard.json';
  async function gfetch(url, opts = {}) {
    const t = GAuth.token(); if (!t) throw { code: 'auth' };
    let r;
    try { r = await fetch(url, { ...opts, headers: { Authorization: 'Bearer ' + t, ...(opts.headers || {}) } }); }
    catch (e) { throw { code: 'network' }; }
    if (r.status === 401) { GAuth.expire(); throw { code: 'auth' }; }
    if (r.status === 403) throw { code: 'forbidden', status: 403 };
    if (!r.ok) throw { code: 'http', status: r.status };
    return r;
  }
  async function findAppData() {
    const q = encodeURIComponent(`name = '${APP_FILE}' and trashed = false`);
    const r = await gfetch(`${API}/files?spaces=appDataFolder&q=${q}&fields=files(id,modifiedTime)&orderBy=modifiedTime desc&pageSize=1`);
    const j = await r.json();
    return (j.files || [])[0] || null;
  }
  async function readAppData(id) { return (await gfetch(`${API}/files/${id}?alt=media`)).json(); }
  async function saveAppData(id, body) {
    if (id) {
      const r = await gfetch(`${UP}/files/${id}?uploadType=media&fields=id,modifiedTime`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body });
      return r.json();
    }
    const boundary = 'cd' + Math.random().toString(36).slice(2);
    const meta = JSON.stringify({ name: APP_FILE, parents: ['appDataFolder'], mimeType: 'application/json' });
    const multipart = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${meta}\r\n--${boundary}\r\nContent-Type: application/json\r\n\r\n${body}\r\n--${boundary}--`;
    const r = await gfetch(`${UP}/files?uploadType=multipart&fields=id,modifiedTime`, { method: 'POST', headers: { 'Content-Type': `multipart/related; boundary=${boundary}` }, body: multipart });
    return r.json();
  }
  /** Archivos de exportación de Instagram en el Drive del usuario (.zip, followers_*.json, following.json…). */
  async function listIgExports() {
    const q = encodeURIComponent("(name contains 'instagram' or name contains 'followers' or name contains 'following') and trashed = false and mimeType != 'application/vnd.google-apps.folder'");
    const out = []; let token = '';
    for (let i = 0; i < 10; i++) {
      const r = await gfetch(`${API}/files?q=${q}&fields=nextPageToken,files(id,name,modifiedTime,size)&orderBy=modifiedTime desc&pageSize=100${token ? '&pageToken=' + encodeURIComponent(token) : ''}`);
      const j = await r.json();
      out.push(...(j.files || []));
      token = j.nextPageToken; if (!token) break;
    }
    return out.filter(f => /\.zip$/i.test(f.name || '') || igFileKind(f.name || ''));
  }
  async function downloadAsFile(f) {
    const blob = await (await gfetch(`${API}/files/${f.id}?alt=media`)).blob();
    return new File([blob], f.name);
  }
  return { findAppData, readAppData, saveAppData, listIgExports, downloadAsFile };
})();

