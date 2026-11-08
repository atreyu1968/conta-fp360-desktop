(function(){'use strict';
const $=sel=>document.querySelector(sel), $$=sel=>[...document.querySelectorAll(sel)];
const state={token:null,user:null,groups:[],library:[],submissions:[],report:null,assignments:[],license:null};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const msg=(s,problem=false)=>{const el=$('#app').hidden?$('#passwordMessage'):$('#message');el.textContent=s;el.setAttribute('role',problem?'alert':'status');};
async function api(route,payload=null,query={}){
 const url='api.php?r='+encodeURIComponent(route)+Object.entries(query).map(([k,v])=>'&'+encodeURIComponent(k)+'='+encodeURIComponent(v)).join('');
 const options={method:payload===null?'GET':'POST',headers:{}};
 if(state.token)options.headers.Authorization='Bearer '+state.token;
 if(payload!==null){options.headers['Content-Type']='application/json';options.body=JSON.stringify(payload);}
 const res=await fetch(url,options), data=await res.json();
 if(!res.ok||data.ok===false)throw new Error(data.error||'Error del servidor');return data;
}
async function invoke(fn){try{await fn();}catch(e){msg(e.message||String(e),true);}}
function opt(items,defaultLabel){return (defaultLabel?'<option value="">'+esc(defaultLabel)+'</option>':'')+items.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.name||x.title)+'</option>').join('');}
function formData(form){return Object.fromEntries(new FormData(form).entries());}
async function refresh(){
 if(state.user.role!=='student'){
  state.license=state.user.role==='teacher'?(await api('license')).license:null;
  renderLicense();
  state.groups=(await api('groups')).items;
  state.library=(await api('library')).items;
  state.assignments=(await api('pull')).items;
  if(state.user.role==='admin'){
    const schools=await api('schools');
    $('#schoolManagement').hidden=!schools.can_create;
    $('#schoolsListing').textContent='Centros registrados: '+schools.items.map(x=>x.name).join(' · ');
    await window.CONTA_PAYPAL?.refresh(schools.can_create,api);
    const users=(await api('users')).items.filter(x=>x.role==='teacher'||x.role==='student');
    const sel=$('#resetUserId');
    sel.innerHTML=users.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.display_name)+' · '+esc(x.email)+'</option>').join('');
  }
  if(state.user.role==='teacher'){
    await window.CONTA_LICENSE?.refresh(api);
  }
  $$('.groups').forEach(el=>{const old=el.value;el.innerHTML=opt(state.groups);if(old)el.value=old;});
  $$('.exercises').forEach(el=>{const old=el.value;el.innerHTML=opt(state.library);if(old)el.value=old;});
  await refreshReport();
 }else{
  state.assignments=(await api('pull')).items;
  $('#studentAssignments').innerHTML=state.assignments.length?'<table><thead><tr><th>Ejercicio</th><th>Módulo</th><th>Plazo (UTC)</th></tr></thead><tbody>'+state.assignments.map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.module_code)+'</td><td>'+esc(x.due_at||'Sin plazo')+'</td></tr>').join('')+'</tbody></table>':'No hay actividades asignadas.';
 }
 window.CONTA_VISUAL?.refresh(state);
}
function renderLicense(){
 const place=$('#licenseStatus');if(!place||!state.user||state.user.role!=='teacher')return;
 const license=state.license||{licenses:[],active_classrooms:0,classroom_limit:0,available_classrooms:0,legacy_classrooms:0};
 const active=license.licenses.filter(x=>x.state==='active');
 const fmt=seconds=>new Intl.DateTimeFormat('es-ES',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(seconds*1000));
 const summary=active.length
  ?'<p><strong>Aulas contratadas y activas:</strong> '+esc(license.active_classrooms)+' / '+esc(license.classroom_limit)+
    ' · Disponibles: '+esc(license.available_classrooms)+'</p>'
  :'<p><strong>Sin licencia anual activa.</strong> Para crear aulas nuevas se necesita un cupo anual.</p>';
 const rows=license.licenses.length
  ?'<table><thead><tr><th>Licencia</th><th>Cupo</th><th>Uso</th><th>Estado</th><th>Vencimiento</th></tr></thead><tbody>'+
   license.licenses.map(x=>'<tr><td>#'+esc(x.id)+'</td><td>'+esc(x.classroom_limit)+'</td><td>'+esc(x.used_classrooms)+' aulas</td><td>'+
    esc(x.state==='active'?'Activa':x.state==='expired'?'Caducada':x.state==='pending'?'Pendiente':'Revocada')+
    '</td><td>'+esc(fmt(x.expires_at))+'</td></tr>').join('')+'</tbody></table>':'';
 place.innerHTML=summary+'<p><strong>Aulas históricas en legado:</strong> '+esc(license.legacy_classrooms)+
  ' · No consumen cupo ni se bloquean por esta transición.</p>'+rows;
}
async function refreshReport(){
 const gid=+($('#reportGroup').value||0);if(!gid)return;
 state.report=(await api('report',null,{group_id:gid}));
 const names=state.report.students;
 $('#reports').innerHTML='<table><thead><tr><th>Alumno</th><th>Ejercicio</th><th>RA y CE</th></tr></thead><tbody>'+names.flatMap(s=>s.assignments.map(a=>{
  const detail=Object.entries(a.criteria).map(([c,v])=>c+': '+(v.final===null?'Pendiente':v.final.toFixed(2))).join(' · ');
  return '<tr><td>'+esc(s.name)+'</td><td>'+esc(a.title)+'</td><td>'+esc(detail||'Sin criterios declarados')+'</td></tr>'; })).join('')+'</tbody></table>';
 state.submissions=(await api('submissions',null,{group_id:gid})).items;
 $('#submissionId').innerHTML=opt(state.submissions.map(s=>({id:s.id,name:s.display_name+' · '+s.title+' · intento '+s.attempt})));
 updateCriteria();
 renderSubmissionEvidence().catch(e=>msg(e.message,true));
 window.CONTA_VISUAL?.report(state);
}
function updateCriteria(){const s=state.submissions.find(x=>x.id===+$('#submissionId').value);$('#criterionSelect').innerHTML=opt((s?.criteria||[]).map(x=>({id:x.code,name:x.code+' ('+x.ra+')'})));}
async function bytes64(file){const bytes=new Uint8Array(await file.arrayBuffer());let out='';for(let i=0;i<bytes.length;i+=8192)out+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(out);}
$('#loginForm').addEventListener('submit',e=>{e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;invoke(async()=>{
 const {email,password}=formData(e.currentTarget);const data=await api('login',{email,password});state.token=data.token;state.user=data.user;
 $('#who').textContent='· '+data.user.name+' ('+data.user.role+')';
 if(data.user.must_change_password){
  $('#loginForm').hidden=true;$('#changePasswordForm').hidden=false;
  $('#passwordMessage').textContent='Debe cambiar la contraseña temporal antes de usar la plataforma.';
  return;
 }
 $('#teacher').hidden=data.user.role==='student';$('#student').hidden=data.user.role!=='student';$('#admin').hidden=data.user.role!=='admin';
 $('#nav').innerHTML='<span class="pill">'+esc(data.user.role)+'</span><span class="pill">Centro '+esc(data.user.school_id)+'</span>';
 await refresh();window.CONTA_VISUAL?.onLogin(state);
 $('#login').hidden=true;$('#app').hidden=false;$('#logout').hidden=false;$('#changePasswordButton').hidden=false;
 msg('Sesión iniciada.');
}).finally(()=>{button.disabled=false;});});
function showChangePassword(){
 $('#app').hidden=true;$('#login').hidden=false;$('#loginForm').hidden=true;
 $('#changePasswordForm').hidden=false;
 $('#passwordMessage').textContent='Cambie su contraseña desde una conexión HTTPS segura.';
}
$('#changePasswordButton').addEventListener('click',showChangePassword);
$('#changePasswordForm').addEventListener('submit',e=>{e.preventDefault();
  invoke(async()=>{
    const f=formData(e.currentTarget);
    await api('change_password',{current_password:f.current_password,new_password:f.new_password});
    $('#passwordMessage').textContent='Contraseña actualizada. Inicie sesión de nuevo.';
    location.reload();
  }).catch(err=>{$('#passwordMessage').textContent=String(err);});
});
$('#logout').addEventListener('click',async()=>{try{await api('logout',{});}catch(err){console.warn('No se pudo confirmar el cierre en el servidor:',err);}finally{state.token=null;state.user=null;location.reload();}});
$('#createGroup').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{await api('groups',formData(e.currentTarget));await refresh();msg('Grupo creado.');});});
$('#enroll').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{const f=formData(e.currentTarget);await api('enroll',{group_id:+f.group_id,student_email:f.student_email});msg('Alumno matriculado.');});});
$('#newUser').addEventListener('submit',e=>{e.preventDefault();const form=e.currentTarget;invoke(async()=>{await api('users',formData(form));form.reset();await refresh();msg('Usuario creado con contraseña temporal.');});});
$('#schoolForm').addEventListener('submit',e=>{e.preventDefault();const form=e.currentTarget;invoke(async()=>{
 const f=formData(form);
 await api('schools',{name:f.name,admin_name:f.admin_name,admin_email:f.admin_email,admin_password:f.admin_password});
 form.reset();await refresh();msg('Nuevo centro y administrador creados de forma independiente.');
});});
$('#resetPasswordForm').addEventListener('submit',e=>{e.preventDefault();const form=e.currentTarget;invoke(async()=>{
  const f=formData(form);await api('reset_password',{user_id:+f.user_id,new_password:f.new_password});
  form.reset();msg('Contraseña restablecida. El usuario deberá cambiarla al acceder.');
});});
$('#curriculumForm').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{
  const f=formData(e.currentTarget);
  const criteria=String(f.criteria).split(/[\n,;\s]+/).map(s=>s.trim()).filter(Boolean);
  const out=await api('curricula',{module_code:f.module_code,territory:f.territory,
    source_url:f.source_url,version:f.version,criteria});
  msg('Catálogo registrado: '+out.registered+' criterios. Compruebe la fuente oficial.');
});});
$('#publish').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{
 const f=formData(e.currentTarget),zip=f.zip;if(zip.size>25*1024*1024)throw new Error('El paquete supera 25 MB');
 const criteria=String(f.criteria).split(/[\n,;]+/).map(s=>s.trim()).filter(Boolean).map(code=>({code,ra:code.split('.')[0]}));
 const out=await api('library',{title:f.title,external_id:f.external_id,module_code:f.module_code,curriculum:f.curriculum,criteria,zip_base64:await bytes64(zip)});
 await refresh();msg('Paquete publicado en biblioteca con identificador '+out.exercise_id+'.');
});});
$('#assign').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{const f=formData(e.currentTarget);await api('assign',{group_id:+f.group_id,exercise_id:+f.exercise_id,max_attempts:+f.max_attempts});await refresh();msg('Ejercicio asignado.');});});
$('#refreshReports').addEventListener('click',()=>invoke(async()=>{await refreshReport();msg('Calificaciones actualizadas.');}));
$('#reportGroup').addEventListener('change',()=>invoke(refreshReport));
$('#submissionId').addEventListener('change',()=>{
 updateCriteria();
 renderSubmissionEvidence().catch(e=>msg(e.message,true));
 updateGradeHistory().catch(e=>msg(e.message,true));
});
async function renderSubmissionEvidence(){
 const sid=+($('#submissionId')?.value||0),place=$('#submissionPreview');
 if(!place)return;
 if(!sid){place.textContent='Seleccione una entrega para revisar los asientos y las actividades.';return;}
 place.textContent='Recuperando evidencias del servidor…';
 const response=await api('submission',null,{id:sid});
 if(+($('#submissionId')?.value||0)!==sid)return;
 const item=response.item||{},work=item.work||{},
       entries=Array.isArray(work.asientos)?work.asientos:[],
       answers=work.respuestasActividades && typeof work.respuestasActividades==='object' && !Array.isArray(work.respuestasActividades)?work.respuestasActividades:{};
 const allowed=new Set((state.submissions.find(x=>x.id===sid)?.criteria||[]).map(x=>x.code));
 const ce=Array.isArray(work.resultadoEvidencias?.ce)?
    work.resultadoEvidencias.ce.filter(x=>allowed.has(x.codigo)):[];
 const preview=(value)=>esc(JSON.stringify(value,null,2).slice(0,55000));
 place.innerHTML='<h3>Revisión de evidencias y trabajo contable</h3>'+
  '<p class="note">Entrega '+esc(sid)+' · Intento '+esc(item.attempt??'—')+' · '+esc(item.received_at||'Sin fecha')+
  '. Los resultados comunicados por Aula son orientativos y no sustituyen la validación docente.</p>'+
  '<div class="buttons"><button type="button" id="downloadSubmissionJson">Descargar entrega íntegra en JSON</button></div>'+
  (ce.length?'<table><thead><tr><th>CE</th><th>Evidencias</th><th>Evaluación orientativa</th></tr></thead><tbody>'+
    ce.map(x=>'<tr><td>'+esc(x.codigo)+'</td><td>'+esc(x.respondidas??0)+' / '+esc(x.actividades??0)+'</td><td>'+
    esc(x.nota===null?'Pendiente':x.nota)+(x.revision?' · Revisión docente':' · No validada')+'</td></tr>').join('')+'</tbody></table>':'')+
  '<details><summary>Libro diario ('+entries.length+' asientos)</summary><pre class="submission-json">'+preview(entries)+'</pre></details>'+
  '<details><summary>Respuestas de las actividades ('+Object.keys(answers).length+')</summary><pre class="submission-json">'+preview(answers)+'</pre></details>'+
  '<details><summary>Evaluación provisional y datos de entrega</summary><pre class="submission-json">'+
    preview({evaluacionProvisional:work.evaluacionProvisional||null,fechaPreparacion:work.fechaPreparacion||null})+'</pre></details>';
 $('#downloadSubmissionJson').addEventListener('click',()=>{
    const data=new Blob([JSON.stringify(item,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(data),a=document.createElement('a');
    a.href=url;a.download='CONTA_FP360_entrega_'+sid+'.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
 });
}
async function updateGradeHistory(){
  const id=+$('#submissionId').value;if(!id){$('#gradeHistory').textContent='Sin entrega seleccionada';return;}
  const history=(await api('grade_history',null,{submission_id:id})).items;
  $('#gradeHistory').innerHTML=history.length?'<table><thead><tr><th>Fecha</th><th>CE</th><th>Instrumento</th><th>Anterior</th><th>Nueva</th><th>Profesor</th></tr></thead><tbody>'+
    history.map(h=>'<tr><td>'+esc(h.created_at)+'</td><td>'+esc(h.criterion_code)+'</td><td>'+esc(h.instrument)+'</td><td>'+esc(h.previous_score??'—')+'</td><td>'+esc(h.new_score)+'</td><td>'+esc(h.teacher_name)+'</td></tr>').join('')+'</tbody></table>':'Sin cambios de notas.';
}
$('#refreshGradeHistory').addEventListener('click',()=>invoke(updateGradeHistory));
$('#gradingPolicyForm').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{
  const f=formData(e.currentTarget);
  const total=Number(f.portafolio)+Number(f.prueba);
  if(Math.abs(total-100)>0.0001)throw Error('La suma de porcentajes debe ser 100 %.');
  await api('grading_policy',{module_code:f.module_code,weights:{portafolio:Number(f.portafolio)/100,prueba:Number(f.prueba)/100}});
  await refreshReport();msg('Ponderación de módulo actualizada.');
});});
$('#gradeForm').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{const f=formData(e.currentTarget);await api('grade',{submission_id:+f.submission_id,grades:[{criterion_code:f.criterion_code,instrument:f.instrument,score:+f.score}]});await refreshReport();await updateGradeHistory();msg('Calificación guardada con historial de auditoría.');});});
window.CONTA_DASHBOARD_REFRESH=refresh;
$('#exportReport').addEventListener('click',()=>{if(!state.report)return;const blob=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='CONTA_FP360_informe_grupo.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
})();
