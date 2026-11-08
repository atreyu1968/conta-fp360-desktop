/* Información de versión de CONTA FP360 Central. Sin dependencias externas. */
(() => {
 'use strict';
 const rootId='cfp-central-about';
 function close(){const root=document.getElementById(rootId);if(root)root.remove();document.removeEventListener('keydown',onKey)}
 function onKey(e){if(e.key==='Escape')close()}
 function show(){
   if(document.getElementById(rootId))return;
   const overlay=document.createElement('div');overlay.id=rootId;overlay.className='cfp-about-overlay';
   overlay.innerHTML='<section class="cfp-about-panel" role="dialog" aria-modal="true" aria-labelledby="cfp-about-title" tabindex="-1"><button class="cfp-about-x" aria-label="Cerrar" type="button">×</button><h2 id="cfp-about-title">CONTA FP360 Central</h2><p>Biblioteca educativa y coordinación académica para Administración y Gestión.</p><dl><dt>Edición</dt><dd>Servidor Central · PHP/SQLite</dd><dt>Versión</dt><dd>2.5 (desarrollo)</dd><dt>Autor y titular</dt><dd>Francisco Javier González Rolo</dd><dt>Sello</dt><dd>Atreyu Servicios Digitales</dd></dl><small>© 2026 Francisco Javier González Rolo. Todos los derechos reservados.</small><div class="cfp-about-buttons"><button type="button" class="cfp-about-accept">Cerrar</button></div></section>';
   overlay.querySelector('.cfp-about-x').addEventListener('click',close);
   overlay.querySelector('.cfp-about-accept').addEventListener('click',close);
   overlay.addEventListener('click',e=>{if(e.target===overlay)close()});
   document.body.appendChild(overlay);document.addEventListener('keydown',onKey);
   overlay.querySelector('.cfp-about-x').focus();
 }
 function install(){
   const target=document.querySelector('.side-bottom')||document.querySelector('header');
   if(!target||document.getElementById('cfp-central-about-button'))return;
   const button=document.createElement('button');button.id='cfp-central-about-button';
   button.type='button';button.className='cfp-about-trigger';
   button.textContent='ⓘ Acerca de · v2.5';button.addEventListener('click',show);
   target.appendChild(button);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
