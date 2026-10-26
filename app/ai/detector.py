import threading

ALIASES={'hardhat':'helmet','hard_hat':'helmet','hard-hat':'helmet','safety_helmet':'helmet','safety-helmet':'helmet','safety helmet':'helmet','safety vest':'vest','safety_vest':'vest','safety-vest':'vest','reflective vest':'vest','glove':'gloves','boot':'boots','flame':'fire','flames':'fire'}

class Detector:
    """Run person, PPE and fire detection models; report only installed capabilities."""
    def __init__(self, settings):
        self.settings=settings; self.model=None; self.models=[]; self.errors=[]; self.names={}; self.lock=threading.Lock()
        for kind,configured in [('people',settings.model_path),('ppe',settings.ppe_model_path),('fire',settings.fire_model_path)]:
            if not configured: continue
            path=settings.path(configured)
            if not path.is_file(): self.errors.append(f'{kind}: configured model file is missing'); continue
            if path.suffix.lower()!='.pt': self.errors.append(f'{kind}: use Ultralytics detection .pt weights'); continue
            try:
                from ultralytics import YOLO
                model=YOLO(str(path),task='detect')
                names={int(k):settings.class_map.get(v.lower(),ALIASES.get(v.lower(),v.lower())) for k,v in model.names.items()}
                self.models.append((kind,model,names))
                for label in names.values():
                    if label not in self.names.values(): self.names[len(self.names)]=label
            except Exception:
                self.errors.append(f'{kind}: model could not load; check trusted weights and AI dependencies')
        self.model=self.models[0][1] if self.models else None
        self.error='; '.join(self.errors) or None
    def status(self):
        classes=set(self.names.values())
        return {'state':'running' if self.model else 'unavailable','error':self.error,'classes':self.names,'models':[{'kind':k,'classes':list(n.values())} for k,m,n in self.models],'ppe_capabilities':sorted(classes & {'helmet','vest','gloves','boots'}),'hazard_capabilities':sorted(classes & {'fire','smoke'}),'activities':{'enabled':False,'reason':'Injury and falls require a specialized temporal model'},'gas':{'enabled':False,'reason':'Gas requires calibrated sensor input'},'simulated':False}
    def detect(self,frame):
        if not self.models: return []
        h,w=frame.shape[:2]; detections=[]
        with self.lock:
            for kind,model,names in self.models:
                result=model.predict(frame,conf=self.settings.confidence,imgsz=self.settings.image_size,device=self.settings.device,verbose=False)[0]
                for b in result.boxes:
                    label=names[int(b.cls.item())]
                    # Use one authoritative person model to avoid duplicate tracks.
                    if kind!='people' and label=='person' and any(k=='people' for k,m,n in self.models): continue
                    detections.append({'class_id':int(b.cls.item()),'label':label,'confidence':float(b.conf.item()),'bbox':[float(v)/scale for v,scale in zip(b.xyxy[0].tolist(),[w,h,w,h])],'simulated':False})
        return detections
