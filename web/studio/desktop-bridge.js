/* CONTA FP360 Desktop 2.2: SQLite por aplicación, sin alterar el motor didáctico. */
(function () {
  'use strict';
  const core = window.__TAURI__?.core;
  if (!core?.invoke) return;
  const native = window.__TAURI__;
  const originalSet = Storage.prototype.setItem;
  const originalRemove = Storage.prototype.removeItem;
  let writeQueue = Promise.resolve();
  let writeError = null;
  let restoring = false;

  const relevant = key => /^cfp360_/i.test(key) || key === 'contafp360.sidebar.collapsed';
  const storageValue = key => originalSet.call(localStorage, key, String(localStorage.getItem(key) ?? ''));
  const invoke = (command, args) => core.invoke(command, args);
  const warning = err => {
    writeError = err instanceof Error ? err : new Error(String(err));
    console.error('CONTA FP360 SQLite:', writeError);
    const status = document.getElementById('cfp-sqlite-status');
    if (status) {
      status.textContent = 'Error de guardado SQLite: exporte una copia.';
      status.style.color = '#ffc4b7';
    }
  };
  const enqueue = task => {
    if (restoring) return;
    writeQueue = writeQueue.then(task).catch(warning);
  };
  async function flush() {
    await writeQueue;
    if (writeError) throw writeError;
  }
  function legacyRows() {
    const rows = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && relevant(key)) rows.push({key, value: localStorage.getItem(key) ?? ''});
    }
    return rows;
  }
  async function initializeSQLite() {
    // La marca impide reimportar datos obsoletos de WebView tras restaurar una copia.
    const migrated = await invoke('sqlite_get', {namespace:'local', key:'__migration_v1'});
    if (migrated === null) {
      const rows = legacyRows();
      rows.push({key:'__migration_v1',value:'1'});
      await invoke('sqlite_put_many', {namespace:'local', entries:rows});
    }
    const rows = await invoke('sqlite_list', {namespace:'local'});
    const keys = new Set(rows.filter(r=>relevant(r.key)).map(r=>r.key));
    for (const {key} of legacyRows()) {
      if (!keys.has(key)) originalRemove.call(localStorage, key);
    }
    for (const {key,value} of rows) {
      if (relevant(key)) originalSet.call(localStorage, key, value);
    }
  }

  // Mantiene la API síncrona del motor actual, con SQLite como origen al arrancar.
  // Las escrituras se encolan en orden y se hacen transaccionales en el backend.
  Storage.prototype.setItem = function (key, value) {
    const result = originalSet.apply(this, arguments);
    if (this === localStorage && relevant(String(key))) {
      enqueue(() => invoke('sqlite_put', {
        namespace:'local', key:String(key), value:String(value)
      }));
    }
    return result;
  };
  Storage.prototype.removeItem = function (key) {
    const result = originalRemove.apply(this, arguments);
    if (this === localStorage && relevant(String(key))) {
      enqueue(() => invoke('sqlite_delete', {
        namespace:'local', key:String(key)
      }));
    }
    return result;
  };

  const ready = initializeSQLite();

  function basename(input) {
    return String(input || 'CONTA_FP360_exportacion.bin')
      .replace(/[\\/]/g, '_').replace(/[<>:"|?*\x00-\x1f]/g, '_').slice(0, 160);
  }
  function encode(bytes) {
    let bin = '';
    for (let pos = 0; pos < bytes.length; pos += 16384) {
      bin += String.fromCharCode(...bytes.subarray(pos, pos + 16384));
    }
    return btoa(bin);
  }
  function decode(base64) {
    const str = atob(base64);
    const out = new Uint8Array(str.length);
    for (let i = 0; i < str.length; i++) out[i] = str.charCodeAt(i);
    return out;
  }
  async function dbGet(key) {
    await ready;
    const raw = await invoke('sqlite_get', {namespace:'objects', key:String(key)});
    if (raw !== null) {
      const data = JSON.parse(raw);
      if (data?.storageFormat === 'package-pdfs-b64-v1') {
        const pdfs = {};
        for (const [name, bytes] of Object.entries(data.pdfs || {})) pdfs[name] = decode(bytes);
        return {manifest:data.manifest, pdfs};
      }
      return data;
    }
    // Migración única del paquete legado de IndexedDB, si existe.
    const previous = await new Promise((resolve, reject) => {
      const open = indexedDB.open('conta_fp360_aula', 1);
      open.onupgradeneeded = () => {
        if (!open.result.objectStoreNames.contains('objects'))
          open.result.createObjectStore('objects');
      };
      open.onerror = () => reject(open.error);
      open.onsuccess = () => {
        const db = open.result;
        const req = db.transaction('objects', 'readonly').objectStore('objects').get(key);
        req.onsuccess = () => { resolve(req.result); db.close(); };
        req.onerror = () => { reject(req.error); db.close(); };
      };
    });
    if (previous !== undefined) await dbSet(key, previous);
    return previous;
  }
  async function dbSet(key, value) {
    await ready;
    let data = value;
    if (key === 'package' && value?.manifest && value?.pdfs) {
      const pdfs = {};
      for (const [name, bytes] of Object.entries(value.pdfs)) {
        pdfs[name] = encode(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes));
      }
      data = {storageFormat:'package-pdfs-b64-v1', manifest:value.manifest, pdfs};
    }
    await invoke('sqlite_put', {namespace:'objects',key:String(key),value:JSON.stringify(data)});
    return true;
  }
  async function saveBlob(url, filename, openAfter) {
    const response = await fetch(url);
    if (!response.ok) throw new Error('No se pudo leer el archivo generado.');
    const bytes = new Uint8Array(await response.arrayBuffer());
    return invoke('save_export', {
      filename: basename(filename),
      base64Data: encode(bytes),
      openAfter: Boolean(openAfter)
    });
  }
  function issue(err) {
    console.error('CONTA FP360 Desktop:', err);
    alert('No se ha podido completar la operación: ' + (err?.message || String(err)));
  }

  const originalClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function (...args) {
    if (!this.isConnected && this.hasAttribute('download') && /^(blob:|data:)/i.test(this.href)) {
      saveBlob(this.href, this.download || 'CONTA_FP360_exportacion.bin', false).catch(issue);
      return;
    }
    return originalClick.apply(this, args);
  };
  document.addEventListener('click', function (event) {
    const node = event.target instanceof Element ? event.target.closest('a') : null;
    if (!node || !node.href) return;

    if (node.dataset.cfpOther) {
      event.preventDefault(); event.stopImmediatePropagation();
      alert('CONTA FP360 ' + node.dataset.cfpOther +
        ' es una aplicación independiente. Ábrala desde su acceso directo del sistema.');
      return;
    }
    const scheme = node.href;
    if (node.hasAttribute('download') && /^(blob:|data:)/i.test(scheme)) {
      event.preventDefault(); event.stopImmediatePropagation();
      saveBlob(scheme, node.download || 'CONTA_FP360_exportacion.bin', false).catch(issue);
      return;
    }
    if (node.target === '_blank' && /^blob:/i.test(scheme)) {
      event.preventDefault(); event.stopImmediatePropagation();
      saveBlob(scheme, 'CONTA_FP360_documento.pdf', true).catch(issue);
      return;
    }
    if (node.target === '_blank' && /^https?:\/\//i.test(scheme)) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (native.opener?.openUrl) native.opener.openUrl(scheme).catch(issue);
      else issue(new Error('No está disponible el servicio de enlaces externos.'));
    }
  }, true);

  function createPrintWindow() {
    let contents = '';
    return { document: {
      write(html) { contents += String(html); },
      close() {
        contents = contents.replace(/<script>window\.onload=\(\)=>window\.print\(\)<\/script>/gi, '');
        const iframe = document.createElement('iframe');
        iframe.setAttribute('title','Informe de impresión CONTA FP360');
        iframe.style.cssText = 'position:fixed;left:-200vw;top:0;width:1000px;height:800px;border:0;';
        document.body.appendChild(iframe);
        iframe.addEventListener('load', () => {
          setTimeout(() => {
            try { iframe.contentWindow.focus(); iframe.contentWindow.print(); }
            catch (e) { issue(e); }
          }, 200);
        }, {once:true});
        iframe.srcdoc = contents;
        setTimeout(() => iframe.remove(), 120000);
      }
    }};
  }

  async function backup() {
    await ready;
    await flush();
    const done = await invoke('sqlite_backup');
    if (done) alert('Copia de seguridad SQLite guardada correctamente.');
  }
  async function restore() {
    if (!confirm('Se sustituirán todos los datos de esta aplicación por los de la copia. ¿Continuar?'))
      return;
    await ready;
    await flush();
    restoring = true;
    try {
      const done = await invoke('sqlite_restore');
      if (done) window.location.reload();
    } finally { restoring = false; }
  }
  function installBackupTools() {
    const sidebar = document.querySelector('.sidebar-footer');
    if (!sidebar || document.getElementById('cfp-sqlite-backup')) return;
    const panel = document.createElement('div');
    panel.style.cssText = 'display:grid;gap:7px;padding-top:11px;';
    const button = (id,title,action) => {
      const el = document.createElement('button');
      el.id = id;
      el.type = 'button';
      el.textContent = title;
      el.title = title;
      el.style.cssText = 'background:#234767;color:#fff;border:1px solid #6083a2;border-radius:7px;padding:7px 9px;font-size:12px;text-align:left;';
      el.addEventListener('click', () => action().catch(issue));
      panel.appendChild(el);
    };
    button('cfp-sqlite-backup','Guardar copia SQLite',backup);
    button('cfp-sqlite-restore','Restaurar copia SQLite',restore);
    const status = document.createElement('small');
    status.id = 'cfp-sqlite-status';
    status.textContent = 'SQLite · almacenamiento local';
    status.style.cssText = 'font-size:10px;color:#c5defc;';
    panel.appendChild(status);
    sidebar.appendChild(panel);
    ready.catch(warning);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded',installBackupTools,{once:true});
  } else { installBackupTools(); }
  window.CONTA_DESKTOP = Object.freeze({
    ready, flush, dbGet, dbSet, saveBlob, createPrintWindow, backup, restore
  });
})();
