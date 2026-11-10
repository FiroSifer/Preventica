// Kenney Interface Sounds, CC0. Audio starts after an operator gesture.
const names=['click','whoosh','pop','delete','confirm','warning','danger'];
const assets=new Map(names.map(n=>[n,fetch(`/static/assets/sounds/${n}.wav`).then(r=>{if(!r.ok)throw Error('Audio unavailable');return r.arrayBuffer();}).catch(()=>null)]));
let context,ready=false,lastEffect=0,lastAlarm=0,alarmKey='';
const buffers=new Map();
const preference=(key)=>{try{return localStorage.getItem(key)!=='off';}catch{return true;}};
let effects=preference('safesense-effects'),alerts=preference('safesense-alerts');
export function settings(){return {effects,alerts,ready};}
export function toggle(kind){if(kind==='effects')effects=!effects;else alerts=!alerts;try{localStorage.setItem('safesense-'+kind,(kind==='effects'?effects:alerts)?'on':'off');}catch{}return settings();}
export async function unlock(){
 try{
  context ||= new (window.AudioContext||window.webkitAudioContext)();
  await context.resume();ready=context.state==='running';
 }catch{ready=false;}
}
export async function sound(name,alarm=false){
 if(!ready||!(alarm?alerts:effects))return;
 const now=performance.now();
 if(!alarm&&now-lastEffect<70)return;
 if(!alarm)lastEffect=now;
 try{
  if(!buffers.has(name))buffers.set(name,assets.get(name).then(data=>data?context.decodeAudioData(data.slice(0)):null));
  const buffer=await buffers.get(name);if(!buffer)return;
  // A critical alarm uses three pulses of the original CC0 sound.
  const count=alarm&&name==='danger'?3:1;
  for(let i=0;i<count;i++){
   const source=context.createBufferSource(),gain=context.createGain();source.buffer=buffer;
   gain.gain.value=alarm?.65:name==='click'?.12:.25;
   source.connect(gain);gain.connect(context.destination);source.start(context.currentTime+i*(buffer.duration+.12));
  }
 }catch{}
}
export function alarm(incidents,now=Date.now()){
 const open=incidents.filter(i=>i.status==='open'&&['warning','critical'].includes(i.severity));
 const tier=open.some(i=>i.severity==='critical')?'critical':open.length?'warning':null;
 const key=tier?`${tier}:${open.filter(i=>i.severity===tier).map(i=>i.id).sort((a,b)=>a-b).join(',')}`:'';
 if(!key){alarmKey='';return;}
 if(!ready||!alerts)return;
 if((key!==alarmKey&&now-lastAlarm>=2000)||now-lastAlarm>=10000){
  alarmKey=key;lastAlarm=now;sound(tier==='critical'?'danger':'warning',true);
 }
}
export function resetAlarms(){alarmKey='';lastAlarm=0;}
