/* Configuración interna de Central. No utiliza conectores ni secretos del escritorio. */
(function () {
'use strict';
let api=null, settings=null, busy=false, mounted=false, dirty=false;
const $=s=>document.querySelector(s);
function notice(text,error=false) {
 const el=$('#paypalMessage');el.textContent=text;el.setAttribute('role',error?'alert':'status');
}
function locks() {
 $('#paypalFields').disabled=busy||!settings;
 $('#paypalTest').disabled=busy||dirty||!settings?.configured;
 $('#paypalDelete').disabled=busy||!settings?.configured;
 $('#paypalReload').disabled=busy;
}
function render(data) {
 if(!data)throw new Error('El servidor no ha devuelto la configuración de PayPal.');
 settings=data;dirty=false;
 const form=$('#paypalForm');
 form.reset();form.elements.environment.value=data.environment;
 form.elements.client_id.placeholder=data.configured?data.client_id_hint+' · vacío para conservar':'Client ID del entorno seleccionado';
 form.elements.client_secret.placeholder=data.configured?'Guardado · vacío para conservar':'Client Secret';
 const descriptions={unverified:'Sin comprobar',verified:'Credenciales verificadas',rejected:'Credenciales rechazadas',unavailable:'No se pudo verificar'};
 $('#paypalSummary').textContent=data.configured
  ? (data.environment==='live'?'Producción':'Pruebas (Sandbox)')+' · '+(descriptions[data.verification_status]||'Sin comprobar')+
    (data.checked_at?' · Última comprobación: '+new Date(data.checked_at).toLocaleString('es-ES'):'')+
    (data.webhook_configured?' · Webhook listo':' · Falta configurar webhook')+
    (data.merchant_configured?' · Comercio listo':' · Falta ID de comercio')
  : 'PayPal todavía no está configurado.';
 $('#paypalLiveNotice').hidden=data.environment!=='live';
 form.elements.confirm_live.required=data.environment==='live';locks();
 $('#paypalWebhookEndpoint').textContent=data.webhook_endpoint||'';
}
async function run(work) {
 if(busy)return;
 busy=true;locks();
 try {await work();} catch(error) {notice(error.message||'No se pudo completar la operación.',true);}
 finally {busy=false;locks();}
}
function mount() {
 if(mounted)return;mounted=true;
 const box=document.createElement('section');box.id='paypalSettings';
 box.innerHTML=`<hr><h3>Configuración de PayPal</h3>
 <p class="note">Solo el administrador general puede configurar la cuenta de cobro.
 Tarifa del servicio: 10 € por aula y año. Sin soporte personalizado.
 Las compras solo operan en Sandbox. Los cobros de producción permanecen desactivados.</p>
 <p id="paypalSummary" class="note"></p>
 <form id="paypalForm" autocomplete="off"><fieldset id="paypalFields" disabled>
 <label>Entorno de PayPal<select name="environment"><option value="sandbox">Pruebas (Sandbox)</option><option value="live">Producción</option></select></label>
 <label>Client ID<input name="client_id" type="text" maxlength="512" autocomplete="off" spellcheck="false"></label>
 <label>Client Secret<input name="client_secret" type="password" maxlength="512" autocomplete="off" spellcheck="false"></label>
 <label>PayPal Merchant ID<input name="merchant_id" type="text" maxlength="64" autocomplete="off" spellcheck="false" placeholder="ID de comercio Sandbox"></label>
 <label>ID del webhook Sandbox<input name="webhook_id" type="text" maxlength="256" autocomplete="off" spellcheck="false" placeholder="ID creado en PayPal Developer"></label>
 <p class="note">Las credenciales se cifran en Central y nunca se devuelven al navegador.
 Deje un campo vacío para conservarlo. Cambiar de entorno exige credenciales nuevas.
 El webhook debe apuntar a <code id="paypalWebhookEndpoint"></code> y suscribirse a pedidos aprobados,
 capturas completadas, pendientes, denegadas, reembolsadas y revertidas, y disputas creadas.</p>
 <label id="paypalLiveNotice" hidden><input type="checkbox" name="confirm_live">
 Confirmo que estas credenciales son de producción. Guardarlas o comprobarlas no realiza cobros; la venta sigue bloqueada.</label>
 <button type="submit">Guardar configuración PayPal</button></fieldset></form>
 <p><button id="paypalTest" type="button" disabled>Comprobar conexión sin cobrar</button>
 <button id="paypalReload" type="button">Actualizar configuración</button>
 <button id="paypalDelete" type="button" disabled>Eliminar credenciales PayPal</button></p>
 <p id="paypalMessage" class="note" role="status" aria-live="polite"></p>`;
 $('#schoolManagement').append(box);
 $('#paypalForm').addEventListener('input',()=>{dirty=true;locks();});
 $('#paypalForm').elements.environment.addEventListener('change',e=>{
  $('#paypalLiveNotice').hidden=e.target.value!=='live';
  $('#paypalForm').elements.confirm_live.checked=false;
  $('#paypalForm').elements.confirm_live.required=e.target.value==='live';
  dirty=true;locks();
 });
 $('#paypalForm').addEventListener('submit',e=>{
  e.preventDefault();
  if(busy||!settings)return;
  const f=e.currentTarget.elements;
  const payload={environment:f.environment.value,client_id:f.client_id.value,
   client_secret:f.client_secret.value,merchant_id:f.merchant_id.value,webhook_id:f.webhook_id.value,
   confirm_live:f.confirm_live.checked,expected_revision:settings.revision};
  f.client_secret.value='';
  run(async()=>{
   const data=await api('paypal_settings',payload);render(data.settings);
   notice('Configuración guardada. Compruebe la conexión; no se ha realizado ningún cobro.');
  });
 });
 $('#paypalReload').addEventListener('click',()=>{
  if(dirty&&!window.confirm('¿Descartar los cambios sin guardar y cargar la configuración del servidor?'))return;
  run(async()=>{render((await api('paypal_settings')).settings);notice('Configuración actualizada.');});
 });
 $('#paypalTest').addEventListener('click',()=>run(async()=>{
  notice('Comprobando credenciales con PayPal, sin realizar cobros…');
  const data=await api('paypal_test',{expected_revision:settings.revision});
  render(data.settings);notice(data.message,!data.connected);
 }));
 $('#paypalDelete').addEventListener('click',()=>{
  if(busy||!settings?.configured)return;
  if(!window.confirm('¿Eliminar las credenciales de PayPal? No se borrarán cuentas, aulas ni trabajos. Los cobros futuros necesitarán una nueva configuración.'))return;
  run(async()=>{
   render((await api('paypal_delete',{expected_revision:settings.revision,confirm_delete:true})).settings);
   notice('Credenciales eliminadas. Las cuentas y los trabajos se conservan.');
  });
 });
}
async function refresh(canManage,callApi) {
 if(!canManage)return;
 api=callApi;mount();
 if(dirty)return;
 await run(async()=>render((await api('paypal_settings')).settings));
}
window.CONTA_PAYPAL={refresh};
})();
