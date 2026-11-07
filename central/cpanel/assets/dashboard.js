(function(){'use strict';
const $=sel=>document.querySelector(sel), $$=sel=>[...document.querySelectorAll(sel)];
const state={token:null,user:null,groups:[],library:[],submissions:[],report:null,assignments:[]};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const msg=(s,problem=false)=>{const el=$('#message');el.textContent=s;el.style.background=problem?'#fff1ed':'#e8f3ff';};
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
  state.groups=(await api('groups')).items;
  state.library=(await api('library')).items;
  $$('.groups').forEach(el=>{const old=el.value;el.innerHTML=opt(state.groups);if(old)el.value=old;});
  $$('.exercises').forEach(el=>{const old=el.value;el.innerHTML=opt(state.library);if(old)el.value=old;});
  await refreshReport();
 }else{
  state.assignments=(await api('pull')).items;
  $('#studentAssignments').innerHTML=state.assignments.length?'<table><thead><tr><th>Ejercicio</th><th>Módulo</th><th>Plazo (UTC)</th></tr></thead><tbody>'+state.assignments.map(x=>'<tr><td>'+esc(x.title)+'</td><td>'+esc(x.module_code)+'</td><td>'+esc(x.due_at||'Sin plazo')+'</td></tr>').join('')+'</tbody></table>':'No hay actividades asignadas.';
 }
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
}
function updateCriteria(){const s=state.submissions.find(x=>x.id===+$('#submissionId').value);$('#criterionSelect').innerHTML=opt((s?.criteria||[]).map(x=>({id:x.code,name:x.code+' ('+x.ra+')'})));}
async function bytes64(file){const bytes=new Uint8Array(await file.arrayBuffer());let out='';for(let i=0;i<bytes.length;i+=8192)out+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(out);}
$('#loginForm').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{
 const {email,password}=formData(e.currentTarget);const data=await api('login',{email,password});state.token=data.token;state.user=data.user;
 $('#who').textContent='· '+data.user.name+' ('+data.user.role+')';
 $('#login').hidden=true;$('#app').hidden=false;$('#logout').hidden=false;
 $('#teacher').hidden=data.user.role==='student';$('#student').hidden=data.user.role!=='student';$('#admin').hidden=data.user.role!=='admin';
 $('#nav').innerHTML='<span class="pill">'+esc(data.user.role)+'</span><span class="pill">Centro '+esc(data.user.school_id)+'</span>';
 await refresh();msg('Sesión iniciada.');
});});
$('#logout').addEventListener('click',()=>{invoke(async()=>{await api('logout',{});location.reload();});});
$('#createGroup').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{await api('groups',formData(e.currentTarget));await refresh();msg('Grupo creado.');});});
$('#enroll').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{const f=formData(e.currentTarget);await api('enroll',{group_id:+f.group_id,student_email:f.student_email});msg('Alumno matriculado.');});});
$('#newUser').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{await api('users',formData(e.currentTarget));e.currentTarget.reset();msg('Usuario creado.');});});
$('#publish').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{
 const f=formData(e.currentTarget),zip=f.zip;if(zip.size>25*1024*1024)throw new Error('El paquete supera 25 MB');
 const criteria=String(f.criteria).split(/[\n,;]+/).map(s=>s.trim()).filter(Boolean).map(code=>({code,ra:code.split('.')[0]}));
 const out=await api('library',{title:f.title,external_id:f.external_id,module_code:f.module_code,curriculum:f.curriculum,criteria,zip_base64:await bytes64(zip)});
 await refresh();msg('Paquete publicado en biblioteca con identificador '+out.exercise_id+'.');
});});
$('#assign').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{const f=formData(e.currentTarget);await api('assign',{group_id:+f.group_id,exercise_id:+f.exercise_id,max_attempts:+f.max_attempts});await refresh();msg('Ejercicio asignado.');});});
$('#refreshReports').addEventListener('click',()=>invoke(async()=>{await refreshReport();msg('Calificaciones actualizadas.');}));
$('#reportGroup').addEventListener('change',()=>invoke(refreshReport));
$('#submissionId').addEventListener('change',updateCriteria);
$('#gradeForm').addEventListener('submit',e=>{e.preventDefault();invoke(async()=>{const f=formData(e.currentTarget);await api('grade',{submission_id:+f.submission_id,grades:[{criterion_code:f.criterion_code,instrument:f.instrument,score:+f.score}]});await refreshReport();msg('Calificación guardada por el profesorado.');});});
$('#exportReport').addEventListener('click',()=>{if(!state.report)return;const blob=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='CONTA_FP360_informe_grupo.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
})();
