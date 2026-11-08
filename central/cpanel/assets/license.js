/* Pago anual de aulas por docente. El importe, la aprobación y la licencia se verifican en Central. */
(function () {
'use strict';
let callApi=null, mounted=false, busy=false;
const $=selector=>document.querySelector(selector);
const labels={
 purchase:'Nueva licencia',renewal:'Renovación manual',expansion:'Ampliación',
 creating:'Creando pedido',pending:'Esperando aprobación en PayPal',
 approved:'Aprobado; falta confirmar el pago',pending_payment:'Pago pendiente',
 completed:'Pagado y verificado',failed:'Pago no completado',cancelled:'Cancelado',
 expired:'Pedido vencido',refunded:'Reembolso recibido; revisión requerida',
 review:'Revisión necesaria',suspended:'Licencia suspendida',disputed:'Pago en disputa'
};
const fmtDate=value=>value?new Date(value).toLocaleDateString('es-ES',{dateStyle:'medium'}):'—';
function msg(text,error=false){
 const el=$('#licenseMessage');el.textContent=text;el.setAttribute('role',error?'alert':'status');
}
function mount(){
 if(mounted)return;mounted=true;
 const panel=document.createElement('article');panel.id='teacherLicense';panel.className='card';
 panel.innerHTML='<h2>Licencia anual de aulas</h2>'+
  '<p class="note">10 € por aula y año. Renovación manual; no hay cargos automáticos. '+
  'Solo PayPal Sandbox está habilitado: no se realizarán cobros de producción.</p>'+
  '<div id="licenseSummary" class="note">Consultando licencia…</div>'+
  '<form id="licenseOrderForm"><label>Número total de aulas<input name="classrooms" type="number" min="1" max="100" step="1" value="1" required></label>'+
  '<button type="submit">Continuar a PayPal Sandbox</button></form>'+
  '<p id="licenseCheckoutLink"></p><div id="licenseOrders"></div>'+
  '<p id="licenseMessage" class="note" role="status" aria-live="polite"></p>';
 $('#teacher').append(panel);
 $('#licenseOrderForm').addEventListener('submit',createOrder);
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin || event.data?.type!=='conta-paypal-return')return;
  refresh(callApi).catch(error=>msg(error.message||'No se pudo actualizar la licencia.',true));
 });
}
function render(data){
 const license=data.license,summary=$('#licenseSummary'),input=$('#licenseOrderForm').elements.classrooms;
 if(!license){
  summary.textContent='No hay una licencia de pago activa para esta cuenta docente.';
  input.min='1';input.value='1';
 }else{
  summary.textContent=(labels[license.status]||license.status)+' · '+license.classrooms+
   ' aula(s) · vigente hasta '+fmtDate(license.expires_at)+
   (license.status==='review'||license.status==='suspended'?' · contacte con el administrador general para revisar el pago.':'');
  input.min=String(license.classrooms);
  if(Number(input.value)<license.classrooms)input.value=String(license.classrooms);
 }
 const list=$('#licenseOrders');list.replaceChildren();
 if(data.orders.length){
  const title=document.createElement('h3');title.textContent='Pedidos recientes';list.append(title);
  const table=document.createElement('table');
  const head=document.createElement('thead');head.innerHTML='<tr><th>Fecha</th><th>Concepto</th><th>Importe</th><th>Estado</th><th></th></tr>';table.append(head);
  const body=document.createElement('tbody');
  for(const order of data.orders){
   const row=document.createElement('tr'),details=order.intent==='expansion'
    ?'Ampliación a '+order.classrooms+' aulas':'Licencia para '+order.classrooms+' aulas';
   const amount=(order.amount_cents/100).toLocaleString('es-ES',{style:'currency',currency:order.currency});
   for(const value of [fmtDate(order.created_at),details,amount,labels[order.status]||order.status]){
    const cell=document.createElement('td');cell.textContent=value;row.append(cell);
   }
   const action=document.createElement('td');
   if(['pending','approved','pending_payment'].includes(order.status)){
    const button=document.createElement('button');button.type='button';button.textContent='Comprobar pago';
    button.addEventListener('click',()=>checkOrder(order.id));action.append(button);
   }
   row.append(action);body.append(row);
  }
  table.append(body);list.append(table);
 }
}
async function refresh(api){
 if(!api)return;
 callApi=api;mount();
 const data=await callApi('paypal_license');
 render(data);
}
async function createOrder(event){
 event.preventDefault();if(busy)return;
 const form=event.currentTarget,button=form.querySelector('button');
 const input=form.elements.classrooms;
 const classrooms=Number(input.value);
 if(!Number.isInteger(classrooms)||classrooms<Number(input.min)||classrooms>100){
  msg('El número de aulas no es válido.',true);return;
 }
 // Abrir la pestaña dentro del gesto del usuario para evitar el bloqueo del navegador.
 const popup=window.open('about:blank','_blank');
 busy=true;button.disabled=true;
 $('#licenseCheckoutLink').replaceChildren();
 try{
  msg('Central está creando un pedido Sandbox seguro…');
  const result=await callApi('paypal_order',{
   classrooms,request_id:crypto.randomUUID().replaceAll('-','')
  });
  const link=document.createElement('a');link.href=result.approval_url;
  link.target='_blank';link.rel='noopener noreferrer';link.textContent='Abrir aprobación de PayPal Sandbox';
  $('#licenseCheckoutLink').append(link);
  if(popup){popup.location=result.approval_url;}
  msg('Pedido '+result.order.amount_cents/100+' € '+(result.already_created?'recuperado.':'creado.')+
    ' Complete la aprobación en PayPal Sandbox.');
  await refresh(callApi);
 }catch(error){
  if(popup)popup.close();
  msg(error.message||'No se pudo crear el pedido.',true);
 }finally{
  busy=false;button.disabled=false;
 }
}
async function checkOrder(orderId){
 if(busy)return;busy=true;
 try{
  msg('Consultando el estado de la orden directamente con PayPal…');
  const result=await callApi('paypal_capture',{order_id:orderId});
  await refresh(callApi);
  msg(result.status==='completed'?'Pago confirmado y licencia actualizada.':
   'PayPal aún no confirma el pago. No se ha activado ninguna licencia.');
 }catch(error){msg(error.message||'No se pudo comprobar el pedido.',true);}
 finally{busy=false;}
}
window.CONTA_LICENSE={refresh};
})();
