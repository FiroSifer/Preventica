import {normalize,distance,valid} from './geometry.js';
import {esc} from './api.js';
export class ZoneEditor{
 constructor(svg){this.svg=svg;this.editing=false;this.points=[];this.selected=-1;this.drawing=false;this.drag=null;
 svg.addEventListener('pointerdown',e=>{if(!this.editing)return;e.preventDefault();svg.setPointerCapture(e.pointerId);const p=this.point(e);const near=this.points.findIndex(q=>Math.hypot(q[0]-p[0],q[1]-p[1])<.025);if(e.altKey){this.drag={p,points:structuredClone(this.points)};}else if(near>=0){this.selected=near;this.drag=true;}else if(this.drawing){this.points.push(p);this.selected=this.points.length-1;}else{const edge=this.points.findIndex((q,i)=>distance(p,q,this.points[(i+1)%this.points.length])<.018);if(edge>=0){this.points.splice(edge+1,0,p);this.selected=edge+1;this.drag=true;}}this.render();});
 svg.addEventListener('pointermove',e=>{if(!this.editing||!this.drag)return;const p=this.point(e);if(this.drag===true)this.points[this.selected]=p;else{const dx=p[0]-this.drag.p[0],dy=p[1]-this.drag.p[1];const next=this.drag.points.map(q=>[q[0]+dx,q[1]+dy]);if(next.every(q=>q.every(v=>v>=0&&v<=1)))this.points=next;}this.render();});
 svg.addEventListener('pointerup',()=>this.drag=null);svg.addEventListener('pointercancel',()=>this.drag=null);
 document.addEventListener('keydown',e=>{if(this.editing&&e.key==='Delete'&&!['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)&&this.selected>=0&&this.points.length>3){this.points.splice(this.selected,1);this.selected=-1;this.render();}});
 }
 point(e){return normalize(e.clientX,e.clientY,this.svg.getBoundingClientRect());}
 begin(zone){this.editing=true;this.points=structuredClone(zone?.polygon||[]);this.drawing=!zone;this.selected=-1;this.render();}
 cancel(){this.editing=false;this.render();}
 finish(){if(!valid(this.points))throw Error('Draw a simple, nonzero-area polygon with at least three distinct vertices.');this.drawing=false;this.render();}
 render(zones=this.zones||[],detections=this.detections||[]){this.zones=zones;this.detections=detections;let html=zones.map(z=>`<polygon points="${z.polygon.map(p=>p.join(',')).join(' ')}" opacity="${z.enabled?1:.3}"/><text x="${z.polygon[0][0]}" y="${z.polygon[0][1]}">${esc(z.name)}</text>`).join('');if(this.editing){html+=`<polygon points="${this.points.map(p=>p.join(',')).join(' ')}"/>`+this.points.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="${i===this.selected?.012:.008}"/>`).join('');}else{html+=detections.map(d=>{const [a,b,c,e]=d.bbox;return `<rect x="${a}" y="${b}" width="${c-a}" height="${e-b}"/><text x="${a}" y="${Math.max(.02,b-.01)}">${d.simulated?'SIMULATED ':''}${esc(d.label)} ${Math.round(d.confidence*100)}%</text>`;}).join('');}this.svg.innerHTML=html;}
}
