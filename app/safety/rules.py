from .geometry import inside

RANK={'info':0,'warning':1,'critical':2}
def highest(severities): return max(severities,key=lambda s:RANK[s],default='normal')

class Rules:
    def __init__(self,incidents,minimum): self.incidents=incidents; self.minimum=minimum; self.counts={}
    def evaluate(self,camera_id,zones,people,ppe,simulated):
        seen=set()
        for z in zones:
            if not z.enabled: continue
            for p in people:
                a,b,c,d=p['bbox']
                if not inside(((a+c)/2,d),z.polygon): continue
                categories=[]
                if z.type in ('danger','restricted'): categories.append(('restricted_entry','Tracked person observed inside a restricted zone',{}))
                missing=[item for item in z.required_ppe if ppe[p['track_id']][item]=='not_detected']
                if missing: categories.append(('potential_missing_ppe','Required PPE not detected persistently; operator review needed',{'not_detected':missing}))
                for category,message,detail in categories:
                    key=(z.id,p['track_id'],category); seen.add(key); self.counts[key]=self.counts.get(key,0)+1
                    if self.counts[key]>=self.minimum:
                        self.incidents.report(camera_id,z.id,p['track_id'],category,z.severity,message,{'confidence':p['confidence'],'uncertainty':'Detection evidence is not proof of absence','consecutive_observations':self.counts[key],**detail},simulated)
        self.counts={k:v for k,v in self.counts.items() if k in seen}
