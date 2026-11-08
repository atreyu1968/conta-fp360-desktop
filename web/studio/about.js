/* CONTA FP360 — diálogo de información de la edición instalada. */
(() => {
  "use strict";
  const edition = document.documentElement.dataset.cfpEdition === "aula" ? "Aula" : "Studio";
  const version = "2.1.0";
  const rootId = "cfp-about-overlay";
  let previousFocus = null;
  function show() {
    if (document.getElementById(rootId)) return;
    previousFocus = document.activeElement;
    const overlay = document.createElement("div");
    overlay.id = rootId;
    overlay.className = "cfp-about-backdrop";
    overlay.innerHTML = `
      <section class="cfp-about-dialog" role="dialog" aria-modal="true"
        aria-labelledby="cfp-about-title" aria-describedby="cfp-about-desc" tabindex="-1">
        <button type="button" class="cfp-about-close" aria-label="Cerrar información" title="Cerrar">×</button>
        <div class="cfp-about-heading">
          <img src="./favicon.png" alt="Logotipo de CONTA FP360" width="64" height="64">
          <div><div class="cfp-about-kicker">Información de la aplicación</div>
          <h2 id="cfp-about-title">CONTA FP360 ${edition}</h2>
          <span class="cfp-about-version">Versión de escritorio ${version}</span></div>
        </div>
        <p id="cfp-about-desc" class="cfp-about-description">
          ${edition === "Studio"
            ? "Herramienta de creación, revisión y exportación de supuestos prácticos de contabilidad para el profesorado de Formación Profesional."
            : "Entorno de aprendizaje de contabilidad para el alumnado de Formación Profesional."}
        </p>
        <dl class="cfp-about-facts">
          <div><dt>Edición</dt><dd>${edition === "Studio" ? "Profesorado" : "Alumnado"}</dd></div>
          <div><dt>Versión de escritorio</dt><dd>${version}</dd></div>
          <div><dt>Tecnología</dt><dd>Tauri 2 · WebView2 (Windows)</dd></div>
          <div><dt>Funcionamiento</dt><dd>Local, sin conexión obligatoria</dd></div>
          <div><dt>Autor y titular</dt><dd>Francisco Javier González Rolo</dd></div>
          <div><dt>Sello</dt><dd>Atreyu Servicios Digitales</dd></div>
        </dl>
        <p class="cfp-about-copyright">© 2026 Francisco Javier González Rolo. Todos los derechos reservados.</p>
        <div class="cfp-about-footer"><button class="cfp-about-done" type="button">Cerrar</button></div>
      </section>`;
    const close = () => {
      document.removeEventListener("keydown", keyHandler);
      overlay.remove();
      if (previousFocus && previousFocus.isConnected) previousFocus.focus();
    };
    const keyHandler = (event) => {
      if (event.key === "Escape") { event.preventDefault(); close(); }
      if (event.key === "Tab") {
        const nodes = [...overlay.querySelectorAll("button:not([disabled])")];
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    overlay.querySelector(".cfp-about-close").addEventListener("click", close);
    overlay.querySelector(".cfp-about-done").addEventListener("click", close);
    overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });
    document.body.appendChild(overlay);
    document.addEventListener("keydown", keyHandler);
    overlay.querySelector(".cfp-about-close").focus();
  }
  function install() {
    if (document.getElementById("cfp-about-button")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.id = "cfp-about-button";
    button.className = "cfp-about-trigger";
    button.textContent = "ⓘ Acerca de";
    button.title = "Información y versión de CONTA FP360 " + edition;
    button.addEventListener("click", show);
    const topbar = document.querySelector(".top-actions") || document.querySelector(".topbar");
    const footer = document.querySelector(".sidebar-footer");
    if (topbar) topbar.appendChild(button);
    else if (footer) footer.appendChild(button);
    else document.body.appendChild(button);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();
