import asyncio
import threading
from datetime import datetime, timezone

class Events:
    def __init__(self):
        self.clients=set(); self.loop=None; self.lock=threading.Lock()
    def publish(self, kind, data):
        event={'type':kind,'timestamp':datetime.now(timezone.utc).isoformat(),'data':data}
        if self.loop and not self.loop.is_closed(): self.loop.call_soon_threadsafe(self._send,event)
    def _send(self,event):
        for q in tuple(self.clients):
            if q.full(): q.get_nowait()
            q.put_nowait(event)
    def subscribe(self):
        q=asyncio.Queue(maxsize=100); self.clients.add(q); return q
