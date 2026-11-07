/* CONTA FP360 Central · puente offline-first, sin dependencia de red para contabilidad. */
(function(){
'use strict';
const d=window.CONTA_DESKTOP;
if(!d?.dbGet||!d?.dbSet)return;
let studio=false;
const $=s=>document.querySelector(s);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let token=null,user=null,localUser=null,server=localStorage.getItem('cfp360_central_url')||'';
let groups=[],library=[],assignments=[],report=null,cachedPackages=[],busy=false;
const identityReady=d.ready.then(async()=>{
  server=localStorage.getItem('cfp360_central_url')||server;
  localUser=await d.dbGet('central_identity')||null;
}).catch(err=>{console.error('Perfil offline:',err);throw err;});
const privateKeys=new Set(['queue','groups','library','report','assignments','active_assignment','attempts','packages']);
async function storageKey(k){
 await identityReady;
 if(!privateKeys.has(k)) return 'central_'+k;
 if(!localUser?.id)throw Error('Debe autenticar por primera vez este perfil de ordenador antes de trabajar offline.');
 return 'central_profile_'+localUser.school_id+'_'+localUser.id+'_'+k;
}
const load=async k=>d.dbGet(await storageKey(k));
const save=async(k,v)=>d.dbSet(await storageKey(k),v);
function baseUrl(){
 const u=new URL(server.trim());
 if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname)))throw Error('Se exige servidor HTTPS');
 if(u.username||u.password||u.hash||u.search)throw Error('URL cPanel incorrecta');
 return u.href.replace(/\/+$/,'');
}
async function api(route,data=null,query={}){
 if(route!=='login'&&route!=='health'&&!token)throw Error('Conéctese con su cuenta para sincronizar');
 const url=baseUrl()+'/api.php?'+new URLSearchParams({r:route,...query});
 const headers={};if(token)headers.Authorization='Bearer '+token;
 if(data!==null)headers['Content-Type']='application/json';
 const response=await fetch(url,{method:data===null?'GET':'POST',headers,body:data===null?undefined:JSON.stringify(data),cache:'no-store'});
 if(route==='package'){if(!response.ok)throw Error('Paquete no disponible: '+response.status);return response.blob();}
 const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'Error HTTP '+response.status);
 return result;
}
function status(txt,error=false){const n=$('#central-status');if(n){n.textContent=txt;n.style.color=error?'#ac2828':'#244c6b';}}
function button(name,label){return '<button type="button" data-central="'+name+'">'+label+'</button>';}
function choices(data,id,name){return data.map(x=>'<option value="'+escape(x[id])+'">'+escape(x[name])+'</option>').join('');}
function render(){
 const box=$('#central-modal');if(!box)return;
 const auth=user?.must_change_password?'<p>Debe cambiar la contraseña temporal para continuar.</p><label>Contraseña actual<input type="password" id="central-old-password"></label><label>Nueva contraseña (12 caracteres o más)<input type="password" id="central-new-password" minlength="12"></label>'+button('changePassword','Cambiar contraseña'):
  user?'<p>'+escape(user.name)+' · '+escape(user.role)+'</p>'+button('logout','Cerrar sesión'):('<label>Correo<input id="central-email" type="email"></label><label>Contraseña<input id="central-password" type="password"></label>'+button('login','Iniciar sesión'));
 const profile=localUser?'<p class="central-local-profile">Perfil offline de este ordenador: '+escape(localUser.name)+' ('+escape(localUser.role)+')</p>':'';
 const tools=studio?'<h3>Studio: biblioteca y grupos</h3><p>Genere primero el ZIP de alumnado desde Publicar paquete.</p><label>ZIP de alumnado<input id="central-zip" type="file" accept=".zip"></label><label>Revisión<input id="central-revision" type="number" min="1" value="1"></label>'+button('publish','Guardar publicación offline')+'<label>Grupo<select id="central-group">'+choices(groups,'id','name')+'</select></label><label>Ejercicio<select id="central-exercise">'+choices(library,'id','title')+'</select></label>'+button('assign','Asignar ahora')+button('report','Recibir calificaciones RA y CE')+'<div id="central-report"></div>'
 :'<h3>Aula: ejercicios y entregas</h3><label>Ejercicios asignados<select id="central-assignment">'+choices(assignments,'assignment_id','title')+'</select></label>'+button('download','Descargar y abrir')+'<label>Ejercicios guardados en este equipo<select id="central-cached">'+cachedPackages.map(a=>'<option value="'+escape(a.assignment_id)+'">'+escape(a.title)+' · revisión '+escape(a.revision)+'</option>').join('')+'</select></label>'+button('openCached','Abrir sin conexión')+button('prepare','Preparar entrega offline')+'<p>Los ZIP y las respuestas de cada supuesto se conservan por separado en SQLite. La entrega puede prepararse sin Internet.</p>';
 box.innerHTML='<div class="central-dialog"><div class="central-head"><h2>CONTA FP360 · Central</h2>'+button('close','✕')+'</div><label>Dirección HTTPS de cPanel<input id="central-server" type="url" value="'+escape(server)+'" placeholder="https://dominio.es/conta-fp360"></label>'+auth+profile+'<hr>'+tools+'<hr>'+button('receive','Recibir')+button('send','Enviar pendientes')+button('update','Comprobar GitHub')+'<p id="central-status" role="status">Trabajo local disponible sin conexión.</p></div>';
}
function showReport(report){
 const slot=$('#central-report');if(!slot||!report)return;
 const lines=report.students.flatMap(s=>s.assignments.map(a=>'<tr><td>'+escape(s.name)+'</td><td>'+escape(a.title)+'</td><td>'+escape(Object.entries(a.criteria).map(([k,v])=>k+': '+(v.final??'pendiente')).join('; '))+'</td></tr>'));
 slot.innerHTML='<div style="max-height:230px;overflow:auto"><table style="font-size:11px"><thead><tr><th>Alumno</th><th>Ejercicio</th><th>CE</th></tr></thead>'+lines.join('')+'</table></div>'+button('export','Exportar informe JSON');
}
async function queue(action,payload){
 await identityReady;
 if(!localUser)throw Error('Autentique este perfil de ordenador al menos una vez para habilitar entregas offline.');
 if(action==='submit' && localUser.role!=='student')throw Error('El perfil offline no pertenece al alumnado.');
 if(action==='publish' && !['admin','teacher'].includes(localUser.role))throw Error('El perfil offline no pertenece al profesorado.');
 const items=await load('queue')||[];items.push({id:crypto.randomUUID(),owner_id:localUser.id,action,payload});
 await save('queue',items);status('Operación guardada sin conexión. Pendientes: '+items.length);
}
async function send(){
 if(!user||!localUser||Number(user.id)!==Number(localUser.id))throw Error('Debe iniciar sesión con el propietario del perfil offline para sincronizar.');
 const items=await load('queue')||[];const pending=[];let sent=0;
 for(const it of items){try{
  if(it.owner_id!==localUser.id)throw Error('Bloqueado: entrega de otro usuario');
  if(['publish','assign'].includes(it.action)&&!['teacher','admin'].includes(user.role))throw Error('Cuenta docente necesaria');
  if(it.action==='submit'&&user.role!=='student')throw Error('Cuenta de alumno necesaria');
  const route=({publish:'library',assign:'assign',submit:'submit'})[it.action];
  if(!route)throw Error('Operación de cola no reconocida');
  await api(route,it.payload);sent++;
 }catch(err){pending.push(it);console.warn('Pendiente:',err.message);}}
 await save('queue',pending);status('Enviadas: '+sent+'. Pendientes: '+pending.length);
}
async function receive(){
 if(!user)throw Error('Acceda con su cuenta');
 if(studio){groups=(await api('groups')).items;library=(await api('library')).items;await save('groups',groups);await save('library',library);}
 else{assignments=(await api('pull')).items;await save('assignments',assignments);}
 render();status('Asignaciones y biblioteca actualizadas');
}
async function publish(){
 const project=window.CONTA_FP360_STUDIO_STATE?.();
 if(!project?.id)throw Error('No existe supuesto activo');
 const file=$('#central-zip')?.files?.[0];if(!file)throw Error('Seleccione el ZIP para alumnado');
 if(file.size>25*1024*1024)throw Error('ZIP mayor de 25 MB');
 const bytes=new Uint8Array(await file.arrayBuffer());let str='';
 for(let i=0;i<bytes.length;i+=8192)str+=String.fromCharCode(...bytes.subarray(i,i+8192));
 const criteria=[...new Set((project.operaciones||[]).flatMap(x=>x.criteriosTrabajados||[]))].filter(x=>/^RA\d+\.[a-z]$/.test(x)).map(code=>({code,ra:code.split('.')[0]}));
 await queue('publish',{external_id:project.id,title:project.titulo||project.id,module_code:String(project.curriculo?.modulo?.codigo||'SIN-MODULO'),curriculum:project.curriculo?.fuenteEstatal?.url||'',revision:+$('#central-revision').value,criteria,zip_base64:btoa(str)});
}
function bytesToBase64(bytes){
  let str='';
  for(let i=0;i<bytes.length;i+=8192)str+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(str);
}
function base64ToBytes(value){
  const s=atob(value);const array=new Uint8Array(s.length);
  for(let i=0;i<s.length;i++)array[i]=s.charCodeAt(i);
  return array;
}
async function validateHash(bytes,expected){
  if(!expected)throw Error('La asignación no contiene huella de integridad.');
  if(!globalThis.crypto?.subtle)throw Error('No es posible comprobar la huella SHA-256 de la descarga.');
  const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
  const hex=[...digest].map(n=>n.toString(16).padStart(2,'0')).join('');
  if(hex.toLowerCase()!==String(expected).toLowerCase())throw Error('Integridad SHA-256 del paquete incorrecta.');
}
async function installPackage(a,bytes){
  await validateHash(bytes,a.sha256);
  const loader=window.CONTA_FP360_AULA_IMPORT_ZIP;
  if(typeof loader!=='function')throw Error('Importador offline de Aula no disponible.');
  const imported=await loader(new File([bytes],a.external_id+'.zip',{type:'application/zip'}));
  if(!imported)throw Error('El ZIP no ha superado la validación del importador.');
  const pack=await d.dbGet('package');
  if(pack?.manifest?.id!==a.external_id)throw Error('El supuesto importado no coincide con la asignación.');
  await d.flush?.();
  await save('active_assignment',a);
}
async function openCached(){
  await identityReady;
  const id=Number($('#central-cached')?.value);
  const a=cachedPackages.find(x=>Number(x.assignment_id)===id);
  if(!a)throw Error('Seleccione un ejercicio descargado.');
  const record=await d.dbGet('central_zip_'+localUser.school_id+'_'+localUser.id+'_'+id);
  if(!record||record.sha256!==a.sha256)throw Error('ZIP local ausente o desactualizado.');
  await installPackage(a,base64ToBytes(record.zip_base64));
  status('Ejercicio abierto desde SQLite, sin necesidad de Internet.');
}
async function download(){
 if(!user||user.role!=='student')throw Error('Acceda como alumno');
 const a=assignments.find(x=>+x.assignment_id===+$('#central-assignment').value);if(!a)throw Error('Sin asignación');
 const blob=await api('package',null,{id:a.exercise_id});
 const binary=new Uint8Array(await blob.arrayBuffer());
 await validateHash(binary,a.sha256);
 const record={assignment_id:a.assignment_id,exercise_id:a.exercise_id,sha256:a.sha256,
     revision:a.revision,external_id:a.external_id,title:a.title,zip_base64:bytesToBase64(binary)};
 await d.dbSet('central_zip_'+localUser.school_id+'_'+localUser.id+'_'+a.assignment_id,record);
 cachedPackages=[...cachedPackages.filter(x=>Number(x.assignment_id)!==Number(a.assignment_id)),{
     assignment_id:a.assignment_id,external_id:a.external_id,title:a.title,revision:a.revision,sha256:a.sha256
 }];
 await save('packages',cachedPackages);
 await installPackage(a,binary);
 render();
 status('ZIP guardado por ejercicio en SQLite. Se puede abrir sin conexión.');

}
async function prepare(){
 const a=await load('active_assignment');if(!a)throw Error('Descargue una asignación antes de entregarla');
 const pkg=await d.dbGet('package');const id=pkg?.manifest?.id;
 if(id!==a.external_id)throw Error('El supuesto activo no corresponde a la asignación');
 const parse=k=>{try{return JSON.parse(localStorage.getItem(k)||'null');}catch(e){return null;}};
 const journal=parse('cfp360_journal_'+id)||{},activities=parse('cfp360_actividades_'+id)||{};
 if(!Array.isArray(journal.asientos)&&!Object.keys(activities).length)throw Error('No hay trabajo para entregar');
 if(!localUser || localUser.role!=='student')throw Error('El dispositivo debe estar vinculado a un perfil de alumno.');
 const attempts=await load('attempts')||{};
 const queued=(await load('queue')||[]).filter(x=>x.action==='submit' && Number(x.payload.assignment_id)===Number(a.assignment_id));
 const used=queued.reduce((m,x)=>Math.max(m,Number(x.payload.attempt||0)),Number(attempts[a.assignment_id]||0));
 const attempt=used+1;
 if(attempt>Number(a.max_attempts||3))throw Error('Límite de intentos agotado');
 await queue('submit',{assignment_id:+a.assignment_id,attempt,event_id:crypto.randomUUID(),work:{manifest_id:id,asientos:journal.asientos||[],cuentas:journal.cuentas||{},cuentasTerceros:journal.cuentasTerceros||{},respuestasActividades:activities,resultadoEvidencias:window.CONTA_FP360_AULA_EVIDENCE?.()||null,evaluacionProvisional:parse('cfp360_evaluacion_'+id),fechaPreparacion:new Date().toISOString()}});
 attempts[a.assignment_id]=attempt;await save('attempts',attempts);
}
async function update(){
 await d.flush?.();
 const v=await window.__TAURI__.core.invoke('cfp_check_update');
 if(!v.enabled){status('Actualizador pendiente de firma y publicación en GitHub');return;}
 if(!v.available){status('No hay versión nueva');return;}
 if(!confirm('Versión '+v.version+' firmada disponible. ¿Instalar?'))return;
 await d.flush?.();status('Instalando actualización firmada');
 await window.__TAURI__.core.invoke('cfp_install_update');
}
async function act(type){
 if(type==='close'){$('#central-modal')?.remove();return;}
 if(type==='logout'){token=null;user=null;render();return;}
 if(busy)return;busy=true;
 try{
  if(type==='login'){
   await identityReady;
   const r=await api('login',{email:$('#central-email').value,password:$('#central-password').value});
   if(r.user.must_change_password){token=r.token;user=r.user;render();status('Contraseña temporal: cámbiela para activar el perfil offline.');return;}
   const next={...r.user,server:baseUrl()};
   if(localUser && (Number(localUser.id)!==Number(next.id)||Number(localUser.school_id)!==Number(next.school_id)||localUser.server!==next.server)){
     throw Error('Este perfil offline contiene trabajos de otro usuario o servidor. Use una cuenta independiente del sistema operativo para proteger los datos del alumnado.');
   }
   if(!localUser){localUser=next;await d.dbSet('central_identity',next);}
   token=r.token;user=r.user;render();status('Sesión iniciada; los datos offline pertenecen a este usuario.');
  }
  if(type==='changePassword'){
    if(!user?.must_change_password)throw Error('No hay cambio inicial pendiente.');
    const oldPassword=$('#central-old-password')?.value;
    const newPassword=$('#central-new-password')?.value;
    await api('change_password',{current_password:oldPassword,new_password:newPassword});
    token=null;user=null;render();status('Contraseña actualizada. Inicie sesión de nuevo.');
  }
  if(type==='receive')await receive();
  if(type==='send')await send();
  if(type==='publish')await publish();
  if(type==='download')await download();
  if(type==='openCached')await openCached();
  if(type==='prepare')await prepare();
  if(type==='assign'){const payload={group_id:+$('#central-group').value,exercise_id:+$('#central-exercise').value,max_attempts:3};if(!payload.group_id||!payload.exercise_id)throw Error('Seleccione grupo y ejercicio');await queue('assign',payload);status('Asignación guardada; use Enviar pendientes para sincronizar.');}
  if(type==='report'){report=await api('report',null,{group_id:$('#central-group').value});await save('report',report);showReport(report);}
  if(type==='export'){const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));try{await d.saveBlob(url,'CONTA_FP360_RA_CE.json',false);}finally{URL.revokeObjectURL(url);}}
  if(type==='update')await update();
 }catch(e){status(e.message||String(e),true);console.error(e);}
 finally{busy=false;}
}
function open(){
 if($('#central-modal'))return;
 const area=document.createElement('div');area.id='central-modal';
 area.addEventListener('click',e=>{const button=e.target.closest('button[data-central]');if(button)act(button.dataset.central);else if(e.target===area)area.remove();});
 area.addEventListener('change',e=>{if(e.target.id==='central-server'){try{const u=new URL(e.target.value);if(u.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(u.hostname))throw Error('HTTPS obligatorio');server=u.href.replace(/\/+$/,'');localStorage.setItem('cfp360_central_url',server);status('Servidor guardado');}catch(err){status(err.message,true);}}});
 document.body.appendChild(area);render();
 const tasks=identityReady.then(()=>localUser ? (studio?Promise.all([load('groups'),load('library'),load('report')]):Promise.all([load('assignments'),load('packages')])) : []);
 tasks.then(values=>{if(studio){groups=values[0]||[];library=values[1]||[];report=values[2]||null;}else {assignments=values[0]||[];cachedPackages=values[1]||[];}if($('#central-modal')){render();if(report)showReport(report);}}).catch(console.warn);
}
function setup(){
 studio=/\bstudio\b/i.test(document.title);
 const parent=$('.top-actions');if(!parent)return;
 const b=document.createElement('button');b.className='btn';b.id='cfp-central-button';b.textContent='⇅ CONTA FP360 Central';b.addEventListener('click',open);parent.prepend(b);
 const style=document.createElement('style');style.textContent='#central-modal{position:fixed;inset:0;z-index:9999;background:#0c213ab9;display:grid;place-items:center;padding:16px}.central-dialog{background:white;border-radius:12px;padding:23px;width:min(680px,100%);max-height:90vh;overflow:auto;color:#21344c;font:14px/1.5 system-ui}.central-head{display:flex;align-items:center;justify-content:space-between}.central-dialog input,.central-dialog select{display:block;width:100%;padding:8px;margin:5px 0 12px;border:1px solid #b9cadb;border-radius:6px}.central-dialog label{display:block;margin:7px 0}.central-dialog button{padding:8px 10px;margin:4px;background:#eaf2ff;border:1px solid #b8cce2;border-radius:7px}.central-dialog table td,.central-dialog table th{padding:4px;border:1px solid #cbd6e5}';document.head.appendChild(style);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
window.addEventListener('load',()=>setTimeout(()=>window.__TAURI__?.core?.invoke('cfp_check_update').then(v=>{if(v?.available){const b=$('#cfp-central-button');if(b)b.textContent='⬆ Actualizar a '+v.version;}}).catch(()=>{}),1500));
window.addEventListener('online',()=>{if(user)send().catch(console.warn);});
window.CONTA_CENTRAL=Object.freeze({open,send,receive,prepare,identityReady});
})();