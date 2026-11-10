from .geometry import inside

RANK={'info':0,'warning':1,'critical':2}
def highest(severities): return max(severities,key=lambda s:RANK[s],default='normal')

class Rules:
    def __init__(self,incidents,minimum): self.incidents=incidents; self.minimum=minimum; self.counts={}
    def hazards(self,camera_id,detections,simulated=False):
        seen=set()
        for label in ('fire','smoke'):
            evidence=[d for d in detections if d['label']==label]
            key=('hazard',label)
            if evidence:
                seen.add(key); self.counts[key]=self.counts.get(key,0)+1
                if self.counts[key]>=self.minimum:
                    self.incidents.report(camera_id,None,None,label+'_hazard','critical',label.capitalize()+' detected; urgent operator verification required',{'confidence':max(d['confidence'] for d in evidence),'consecutive_observations':self.counts[key]},simulated)
            else: self.counts.pop(key,None)
    def reset(self):
        self.counts.clear()

    def evaluate(self,camera_id,zones,people,ppe,simulated):
        seen=set(); assessments=[]
        for z in zones:
            if not z.enabled: continue
            for p in people:
                a,b,c,d=p['bbox']
                feet_inside=inside(((a+c)/2,d),z.polygon)
                # Torso location permits PPE checking in a webcam view with
                # cropped legs. Entry rules retain the ground-contact point.
                ppe_inside=feet_inside or inside(((a+c)/2,b+(d-b)*.45),z.polygon)
                categories=[]
                if feet_inside and z.type in ('danger','restricted'):
                    category='danger_entry' if z.type=='danger' else 'restricted_entry'
                    categories.append((category,f'Tracked person observed inside {z.type} zone: {z.name}',{}))
                if ppe_inside and z.required_ppe:
                    states=ppe.get(p['track_id'],{})
                    missing=[]; pending=[]; unknown=[]
                    for item in z.required_ppe:
                        state=states.get(item,'unsupported')
                        key=(z.id,p['track_id'],'ppe:'+item)
                        if state=='not_detected':
                            seen.add(key); self.counts[key]=self.counts.get(key,0)+1
                            (missing if self.counts[key]>=self.minimum else pending).append(item)
                        elif state!='detected': unknown.append(item)
                    status='missing' if missing else 'checking' if pending else 'unverified' if unknown else 'compliant'
                    assessments.append({'zone_id':z.id,'zone_name':z.name,'track_id':p['track_id'],'status':status,'missing':missing,'pending':pending,'unverified':unknown,'required':z.required_ppe,'severity':z.severity})
                    if missing:
                        self.incidents.report(camera_id,z.id,p['track_id'],'potential_missing_ppe',z.severity,
                            f"PPE checkpoint {z.name}: {', '.join(missing)} not detected on person {p['track_id']}; review required",
                            {'not_detected':missing,'confidence':p['confidence'],'uncertainty':'Detection evidence is not proof of absence','consecutive_observations':min(self.counts[(z.id,p['track_id'],'ppe:'+item)] for item in missing)},simulated)
                for category,message,detail in categories:
                    key=(z.id,p['track_id'],category); seen.add(key); self.counts[key]=self.counts.get(key,0)+1
                    if self.counts[key]>=self.minimum:
                        self.incidents.report(camera_id,z.id,p['track_id'],category,z.severity,message,{'confidence':p['confidence'],'consecutive_observations':self.counts[key],**detail},simulated)
        self.counts={k:v for k,v in self.counts.items() if k in seen or k[0]=='hazard'}
        return assessments
