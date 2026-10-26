import time

def iou(a,b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0])); h=max(0,min(a[3],b[3])-max(a[1],b[1]))
    return w*h/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-w*h)

class Tracker:
    def __init__(self): self.tracks={}; self.next_id=1
    def update(self, detections, timestamp=None):
        now=time.monotonic() if timestamp is None else timestamp
        self.tracks={k:v for k,v in self.tracks.items() if now-v[1]<2}
        available=set(self.tracks)
        people=[]
        for d in detections:
            if d['label']!='person': continue
            best=max(available,key=lambda k:iou(d['bbox'],self.tracks[k][0]),default=None)
            if best is None or iou(d['bbox'],self.tracks[best][0])<.2:
                best=self.next_id; self.next_id+=1
            else: available.remove(best)
            self.tracks[best]=(d['bbox'],now); people.append({**d,'track_id':best})
        return people

def associate(people, detections, capabilities):
    findings={p['track_id']:{c:('not_detected' if c in capabilities else 'unsupported') for c in ('helmet','vest','gloves','boots')} for p in people}
    for d in detections:
        label=d['label']
        if label not in ('helmet','vest','gloves','boots'): continue
        x1,y1,x2,y2=d['bbox']; x=(x1+x2)/2; y=(y1+y2)/2
        candidates=[]
        for p in people:
            a,b,c,e=p['bbox']; rel=(y-b)/max(e-b,1e-6)
            valid={'helmet':(-.15,.35),'vest':(.2,.75),'gloves':(.25,.9),'boots':(.7,1.1)}[label]
            if a<=x<=c and valid[0]<=rel<=valid[1]: candidates.append(p)
        if candidates:
            p=min(candidates,key=lambda p:(p['bbox'][2]-p['bbox'][0])*(p['bbox'][3]-p['bbox'][1]))
            findings[p['track_id']][label]='detected'
    for p in people:
        a,b,c,d=p['bbox']
        if c-a<.04 or d-b<.12 or a<=.005 or b<=.005 or c>=.995 or d>=.995:
            for label,state in findings[p['track_id']].items():
                if state=='not_detected': findings[p['track_id']][label]='insufficient_evidence'
    return findings
