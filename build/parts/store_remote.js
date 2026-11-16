  // --- copia en Google Drive (carpeta privada de la app): un solo archivo JSON con todo ---
  function stamp() { S.state.meta = { ...(S.state.meta || {}), savedAt: Date.now() }; }
  function emit() { listeners.forEach(fn => { try { fn(); } catch (e) { console.error(e); } }); }

  function scheduleSync() {
    if (!S.fileReady) return;
    clearTimeout(S.timer);
    S.syncStatus = 'pendiente';
    S.timer = setTimeout(flush, 1200);
  }
  async function flush() {
    if (!S.fileReady) return;
    if (S.flushing) { S.again = true; return; }
    S.flushing = true;
    try {
      const body = JSON.stringify(S.state);
      if (body !== S.lastPushed) {
        const meta = await Drive.saveAppData(S.fileId, body);
        S.fileId = meta.id; S.remoteModified = meta.modifiedTime || null; S.lastPushed = body;
      }
      S.syncStatus = 'ok';
    } catch (e) {
      console.warn('sync', e);
      S.syncStatus = e && e.code === 'auth' ? 'auth' : 'error';
      if (e && e.code === 'auth') { S.fileReady = false; S.backend = 'navegador'; }
    } finally {
      S.flushing = false;
      emit();
      if (S.again) { S.again = false; scheduleSync(); }
    }
  }

  /** Conecta con Drive: si hay copia en la nube más nueva la trae; si no, sube la local. */
  async function connectRemote(onLoaded) {
    if (!GAuth.token()) return;
    try {
      const found = await Drive.findAppData();
      S.backend = 'cuenta';
      if (found) {
        S.fileId = found.id; S.remoteModified = found.modifiedTime || null;
        const remote = normalize(await Drive.readAppData(found.id));
        const localSaved = (S.state.meta && S.state.meta.savedAt) || 0;
        const remoteSaved = (remote.meta && remote.meta.savedAt) || 0;
        if (S.fresh || remoteSaved >= localSaved) { // un dispositivo nuevo nunca pisa la nube
          S.state = remote; saveLocal(); S.lastPushed = JSON.stringify(S.state); S.syncStatus = 'ok';
          S.fileReady = true; onLoaded && onLoaded(true);
        } else {
          S.fileReady = true; scheduleSync(); onLoaded && onLoaded(false);
        }
      } else {
        S.fileReady = true; S.lastPushed = null; scheduleSync(); onLoaded && onLoaded(false);
      }
      S.fresh = false;
      emit();
    } catch (e) {
      console.warn('remote', e);
      S.fileReady = false; S.backend = 'navegador';
      S.syncStatus = e && e.code === 'auth' ? 'auth' : 'error';
      emit();
    }
  }
  /** Al volver a la app: si otro dispositivo guardó cambios, los trae. */
  async function pull() {
    if (!S.fileReady || S.flushing || S.syncStatus === 'pendiente' || !GAuth.token()) return;
    try {
      const found = await Drive.findAppData();
      if (!found || found.modifiedTime === S.remoteModified) return;
      const remote = normalize(await Drive.readAppData(found.id));
      if (((remote.meta && remote.meta.savedAt) || 0) > ((S.state.meta && S.state.meta.savedAt) || 0)) {
        S.state = remote; saveLocal(); S.lastPushed = JSON.stringify(S.state);
      }
      S.fileId = found.id; S.remoteModified = found.modifiedTime; emit();
    } catch (e) { console.warn('pull', e); }
  }
  function disconnect() { S.fileReady = false; S.backend = 'navegador'; S.syncStatus = 'local'; S.fileId = null; S.lastPushed = null; emit(); }

  return {
    LS_KEY,
    get state() { return S.state; },
    get backend() { return S.backend; },
    get syncStatus() { return S.syncStatus; },
    init() { const l = loadLocal(); S.fresh = !l; S.state = normalize(l); return S.state; },
    connectRemote, pull, disconnect,
    /** marca el estado como «sin cambios del usuario» (datos de ejemplo): la nube siempre le gana */
    unstamp() { S.state.meta = { ...(S.state.meta || {}), savedAt: 0 }; saveLocal(); },
    subscribe(fn) { listeners.push(fn); },
    /** aplica un cambio y lo persiste en todos los destinos */
    update(fn) {
      fn(S.state); trim(S.state); stamp();
      const ok = saveLocal();
      scheduleSync();
      emit();
      return ok;
    },
    replace(newState) { S.state = normalize(newState); stamp(); saveLocal(); scheduleSync(); emit(); },
    reset() { S.state = defaults(); S.state.meta.initialized = true; stamp(); saveLocal(); scheduleSync(); emit(); },
    normalize, defaults,
  };
})();
