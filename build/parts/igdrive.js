/* ===== Exportaciones semanales de Instagram desde Google Drive ===== */
const IG_DRIVE_EVERY = 12 * 3600000; // revisa como mucho cada 12 h
/**
 * Lee de Google Drive las exportaciones de Instagram que todavía no se procesaron y suma sus
 * seguidores y seguidos a los contactos guardados (cada exportación semanal trae solo lo nuevo).
 */
async function syncIgFromDrive() {
  const all = await Drive.listIgExports();
  const prev = st().settings.igDrive || {};
  const seen = new Set(prev.seen || []);
  const key = f => f.id + ':' + (f.modifiedTime || '');
  const fresh = all.filter(f => !seen.has(key(f))).sort((a, b) => (a.modifiedTime || '').localeCompare(b.modifiedTime || ''));
  const before = st().igContacts.list.length;
  if (!fresh.length) {
    Store.update(s => { s.settings.igDrive = { ...(s.settings.igDrive || {}), auto: true, lastCheck: Date.now() }; });
    return { files: 0, found: all.length, added: 0, total: before, failed: [] };
  }
  const followers = new Set(), following = new Set(), close = new Set(), names = new Map(), done = [], failed = [];
  st().igContacts.list.forEach(c => { if (c.fr) followers.add(c.u); if (c.fg) following.add(c.u); if (c.cf) close.add(c.u); if (c.n) names.set(c.u, c.n); });
  for (const f of fresh) {
    try {
      const r = await readIgExport([await Drive.downloadAsFile(f)]);
      r.followers.forEach(u => followers.add(u)); r.following.forEach(u => following.add(u)); r.close.forEach(u => close.add(u));
      r.names.forEach((n, u) => { if (n) names.set(u, n); });
      done.push(key(f));
    } catch (e) {
      if (e && (e.code === 'auth' || e.code === 'network')) throw e;
      failed.push(f.name);
    }
  }
  const list = mergeIgContacts([], followers, following, close, names);
  Store.update(s => {
    if (done.length) s.igContacts = { importedAt: Date.now(), list };
    s.settings.igDrive = { ...(s.settings.igDrive || {}), auto: true, lastCheck: Date.now(), lastSync: done.length ? Date.now() : (s.settings.igDrive || {}).lastSync || null, seen: [...seen, ...done].slice(-300) };
  });
  return { files: done.length, found: all.length, added: list.length - before, total: list.length, failed };
}
function igDriveError(e) {
  const c = e && e.code;
  if (c === 'auth') return 'Tu sesión de Google venció. Volvé a conectar Google en Ajustes.';
  if (c === 'network') return 'Sin conexión a internet. Probá de nuevo.';
  if (c === 'forbidden') return 'Google no dio permiso para leer tu Drive. Volvé a conectar Google y aceptá el permiso de Drive.';
  return 'No se pudo leer Google Drive. Probá de nuevo en un rato.';
}
function igDriveSummary(r) {
  if (!r.found) return 'Todavía no hay exportaciones de Instagram en tu Drive. Cuando llegue la primera, se carga sola.';
  if (!r.files) return `Ya estaba todo al día (${r.total} contactos).${r.failed.length ? ` No pude leer: ${r.failed.join(', ')}.` : ''}`;
  return `Leí ${r.files} ${r.files === 1 ? 'exportación' : 'exportaciones'} de Drive: ${r.total} contactos${r.added > 0 ? ` (${r.added} nuevos)` : ''}.${r.failed.length ? ` No pude leer: ${r.failed.join(', ')}.` : ''}`;
}
function autoIgDrive() {
  const g = st().settings.igDrive || {};
  if (!GAuth.token() || g.auto === false) return;
  if (g.lastCheck && Date.now() - g.lastCheck < IG_DRIVE_EVERY) return;
  syncIgFromDrive().then(r => { if (r.files) toast(igDriveSummary(r)); }).catch(e => console.warn('igDrive', e));
}

