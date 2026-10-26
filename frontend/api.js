export async function api(path,method='GET',body){
 const r=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 if(!r.ok){const e=await r.json().catch(()=>({detail:r.status===500?'The service encountered a problem. Please try again.':r.statusText}));const detail=Array.isArray(e.detail)?e.detail.map(v=>v.msg.replace(/^Value error, /,'')).join('. '):e.detail;const error=Error(typeof detail==='string'?detail:'The request could not be completed.');error.status=r.status;throw error;}
 return r.status===204?null:r.json();
}
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
