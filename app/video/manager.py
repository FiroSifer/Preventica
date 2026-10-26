import logging
import os
import threading
import time
from datetime import datetime, timezone
import cv2
from sqlalchemy import select
from app.database.models import Camera, Zone
from app.ai.tracking import Tracker, associate
from app.safety.rules import Rules
from .sources import synthetic

log=logging.getLogger(__name__)
class Worker:
    def __init__(self,camera,settings,detector,sessions,incidents,events):
        self.camera=camera; self.settings=settings; self.detector=detector; self.sessions=sessions; self.incidents=incidents; self.events=events
        self.stop=threading.Event(); self.lock=threading.Lock(); self.frame=None; self.jpeg=None; self.seq=0; self.status='connecting'; self.error=None; self.last_frame=None
        self.demo_detections=[]
        self.result={'detections':[],'people':[],'ppe':{},'simulated':camera.source_type=='demo','dimensions':[800,450]}; self.tracker=Tracker(); self.rules=Rules(incidents,settings.min_observations)
        self.threads=[threading.Thread(target=self.capture,daemon=True),threading.Thread(target=self.infer,daemon=True)]
    def start(self):
        for t in self.threads: t.start()
    def state(self):
        with self.lock: return {'status':self.status,'error':self.error,'last_frame_at':self.last_frame,**self.result}
    def set_status(self,status,error=None):
        with self.lock:
            changed=self.status!=status; self.status=status; self.error=error
            if status!='online': self.frame=None; self.jpeg=None
        if changed:
            self.events.publish('camera.state',{'id':self.camera.id,'status':status,'error':error})
            if status=='offline': self.incidents.report(self.camera.id,None,None,'camera_offline','warning','Camera unavailable; monitoring coverage unknown',{},self.camera.source_type=='demo')
    def capture(self):
        cap=None; backoff=1; start=time.monotonic()
        try:
            while not self.stop.is_set():
                if self.camera.source_type=='demo':
                    if self.camera.source=='offline': self.set_status('offline','Demo disconnection'); self.stop.wait(1); continue
                    frame,demo_detections=synthetic(time.monotonic()-start,self.camera.id)
                else:
                    if cap is None:
                        self.set_status('connecting')
                        source=self.camera.source
                        if source.startswith('env:'): source=self.settings.source_variable(source[4:])
                        if not source: self.set_status('offline','Camera source environment variable is missing'); self.stop.wait(5); continue
                        # Do not pass URLs through logging. FFmpeg diagnostics can expose URLs, so suppress them.
                        os.environ.setdefault('OPENCV_FFMPEG_LOGLEVEL','-8')
                        if self.camera.source_type=='usb': cap=cv2.VideoCapture(int(source))
                        else: cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,3000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,3000])
                    ok,frame=cap.read()
                    if not ok:
                        cap.release(); cap=None; self.set_status('offline','Cannot read camera; check source and connection')
                        self.stop.wait(backoff); backoff=min(15,backoff*2); continue
                backoff=1
                # Bound memory and bandwidth for large camera sources.
                h,w=frame.shape[:2]
                if w>1280: frame=cv2.resize(frame,(1280,int(h*1280/w)))
                ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,80])
                if ok:
                    with self.lock:
                        self.frame=frame; self.jpeg=encoded.tobytes();
                        if self.camera.source_type=='demo': self.demo_detections=demo_detections
                        self.seq+=1; self.last_frame=datetime.now(timezone.utc).isoformat(); self.result['dimensions']=[frame.shape[1],frame.shape[0]]
                    self.set_status('online')
                self.stop.wait(1/self.settings.capture_fps)
        except Exception:
            log.error('Camera capture failed (camera_id=%s)',self.camera.id); self.set_status('error','Camera capture failed')
        finally:
            if cap: cap.release()
    def infer(self):
        last=-1; start=time.monotonic()
        while not self.stop.is_set():
            with self.lock: frame=self.frame; seq=self.seq; demo_detections=self.demo_detections
            if frame is not None and seq!=last:
                last=seq
                try:
                    simulated=self.camera.source_type=='demo'
                    if simulated:
                        det=demo_detections
                    else: det=self.detector.detect(frame)
                    people=self.tracker.update(det); caps={'helmet','vest'} if simulated else set(self.detector.names.values())
                    ppe=associate(people,det,caps)
                    with self.sessions() as s: zones=s.scalars(select(Zone).where(Zone.camera_id==self.camera.id)).all()
                    self.rules.evaluate(self.camera.id,zones,people,ppe,simulated)
                    self.rules.hazards(self.camera.id,det,simulated)
                    with self.lock: self.result.update(detections=det,people=people,ppe=ppe,inference_error=None)
                except Exception:
                    with self.lock: self.result.update(detections=[],people=[],ppe={},inference_error='Inference unavailable; inspect model configuration')
                    log.error('Inference failed (camera_id=%s)',self.camera.id)
                    self.stop.wait(5)
            self.stop.wait(1/self.settings.inference_fps)
    def close(self):
        self.stop.set()
        for t in self.threads: t.join(timeout=8)

class Manager:
    def __init__(self,settings,detector,sessions,incidents,events): self.args=(settings,detector,sessions,incidents,events); self.workers={}; self.lock=threading.RLock()
    def refresh(self,camera):
        with self.lock:
            self.remove(camera.id)
            if camera.enabled:
                w=Worker(camera,*self.args); self.workers[camera.id]=w; w.start()
    def remove(self,id):
        with self.lock:
            w=self.workers.pop(id,None)
            if w: w.close()
    def state(self,id):
        w=self.workers.get(id)
        return w.state() if w else {'status':'offline','error':'Camera disabled','last_frame_at':None,'detections':[],'people':[],'ppe':{},'dimensions':[800,450],'simulated':False}
    def close(self):
        for id in list(self.workers): self.remove(id)
