import threading
from datetime import timedelta
from sqlalchemy import select
from app.database.models import Incident, now

class Incidents:
    def __init__(self,sessions,events,cooldown): self.sessions=sessions; self.events=events; self.cooldown=cooldown; self.lock=threading.Lock()
    def report(self, camera_id, zone_id, track_id, category, severity, explanation, evidence, simulated=False):
        key=f'{camera_id}:{zone_id}:{track_id}:{category}'
        with self.lock, self.sessions() as s:
            previous=s.scalar(select(Incident).where(Incident.key==key).order_by(Incident.id.desc()))
            if previous and (previous.status!='resolved' or previous.updated_at.replace(tzinfo=now().tzinfo)>now()-timedelta(seconds=self.cooldown)): return previous.id
            row=Incident(camera_id=camera_id,zone_id=zone_id,track_id=track_id,key=key,category=category,severity=severity,explanation=explanation,evidence=evidence,simulated=simulated,history=[{'status':'open','at':now().isoformat()}])
            s.add(row); s.commit(); self.events.publish('incident.created',{'id':row.id,'camera_id':camera_id,'category':category,'severity':severity,'simulated':simulated})
            return row.id
