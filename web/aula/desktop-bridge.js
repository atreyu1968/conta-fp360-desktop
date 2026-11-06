/* Se conserva el motor contable 2.1. Adaptador de escritorio compartido. */
(function () {
  'use strict';
  const core = window.__TAURI__?.core;
  if (!core?.invoke) return;
  const native = window.__TAURI__;

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
  async function saveBlob(url, filename, openAfter) {
    const response = await fetch(url);
    if (!response.ok) throw new Error('No se pudo leer el archivo generado.');
    const bytes = new Uint8Array(await response.arrayBuffer());
    return core.invoke('save_export', {
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
        ' es una aplicación independiente. Ábrala desde su acceso directo de Windows.');
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
  window.CONTA_DESKTOP = Object.freeze({createPrintWindow, saveBlob});
})();
