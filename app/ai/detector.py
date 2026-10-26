import threading

class Detector:
    def __init__(self, settings):
        self.settings=settings; self.model=None; self.error=None; self.names={}; self.lock=threading.Lock()
        if settings.model_path:
            path=settings.path(settings.model_path)
            if not path.is_file(): self.error='Configured model file is missing'
            elif path.suffix.lower()!='.pt': self.error='This MVP supports local Ultralytics .pt weights only'
            else:
                try:
                    from ultralytics import YOLO
                    self.model=YOLO(str(path), task='detect')
                    self.names={int(k):settings.class_map.get(v.lower(),v.lower()) for k,v in self.model.names.items()}
                except Exception:
                    self.error='Model could not load; check trusted weights and optional AI dependencies'
    def status(self):
        return {'state':'running' if self.model else 'unavailable','error':self.error,'classes':self.names,'ppe_capabilities':sorted(set(self.names.values()) & {'helmet','vest','gloves','boots'}),'activities':{'enabled':False,'reason':'Requires a specialized temporal model'},'simulated':False}
    def detect(self,frame):
        if self.model is None: return []
        with self.lock:
            result=self.model.predict(frame,conf=self.settings.confidence,imgsz=self.settings.image_size,device=self.settings.device,verbose=False)[0]
        h,w=frame.shape[:2]
        return [{'class_id':int(b.cls.item()),'label':self.names[int(b.cls.item())],'confidence':float(b.conf.item()),'bbox':[float(v)/scale for v,scale in zip(b.xyxy[0].tolist(),[w,h,w,h])],'simulated':False} for b in result.boxes]

class ActivityExtension:
    """Future temporal-model plugin; no activity predictions in the MVP."""
    def evaluate(self, frames):
        raise NotImplementedError('Specialized validated temporal model required')
