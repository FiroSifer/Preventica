import asyncio
import secrets
import time
import hmac
import hashlib
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select
from .config import Settings, ROOT
from .database.store import database
from .database.models import Camera, Zone, Incident, now
from .schemas import CameraInput, CameraPatch, ZoneInput
from .events import Events
from .ai.detector import Detector
from .safety.incidents import Incidents
from .safety.rules import highest
from .video.manager import Manager

def record(row):
    values={c.name:getattr(row,c.name) for c in row.__table__.columns}
    for key,value in values.items():
        if isinstance(value,datetime) and value.tzinfo is None: values[key]=value.replace(tzinfo=timezone.utc)
    return jsonable_encoder(values)

def create_app(settings=None):
    settings=settings or Settings(); engine,sessions=database(settings); events=Events(); detector=Detector(settings)
    incidents=Incidents(sessions,events,settings.cooldown_seconds); manager=Manager(settings,detector,sessions,incidents,events)
    @asynccontextmanager
    async def lifespan(app):
        events.loop=asyncio.get_running_loop()
        with sessions() as s:
            for c in s.scalars(select(Camera)).all(): manager.refresh(c)
        yield
        await asyncio.to_thread(manager.close); engine.dispose()
    app=FastAPI(title='SafeSense AI',version='1.0.0',lifespan=lifespan)
    signing_key=secrets.token_bytes(32)
    auth_sessions={}
    attempts={}
    def authenticated(token):
        try:
            nonce,expiry,signature=(token or '').split('.')
            payload=f'{nonce}.{expiry}'
            expected=hmac.new(signing_key,payload.encode(),hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature,expected) and int(expiry)>time.time() and auth_sessions.get(nonce,0)>time.time()
        except (ValueError,TypeError): return False
    class Login(BaseModel):
        name: str = Field(max_length=100)
        password: str = Field(max_length=200)
    @app.post('/api/auth/login')
    def login(body:Login,request:Request):
        host=request.client.host if request.client else 'local'
        now_s=time.time()
        recent=[v for v in attempts.get(host,[]) if now_s-v<60]
        attempts[host]=recent
        if len(recent)>=10: raise HTTPException(429,'Too many attempts. Try again in one minute.')
        if not (hmac.compare_digest(body.name.encode(),settings.admin_name.encode()) and hmac.compare_digest(body.password.encode(),settings.admin_password.encode())):
            recent.append(now_s)
            raise HTTPException(401,'Incorrect name or password.')
        attempts.pop(host,None)
        for key,expires in list(auth_sessions.items()):
            if expires<=now_s: auth_sessions.pop(key,None)
        if len(auth_sessions)>=1024: auth_sessions.pop(next(iter(auth_sessions)))
        nonce=secrets.token_hex(16)
        auth_sessions[nonce]=int(now_s+settings.session_hours*3600)
        payload=f'{nonce}.{auth_sessions[nonce]}'
        token=payload+'.'+hmac.new(signing_key,payload.encode(),hashlib.sha256).hexdigest()
        response=JSONResponse({'name':settings.admin_name})
        response.set_cookie('safesense_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=settings.session_hours*3600)
        return response
    @app.get('/api/auth/session')
    def session(): return {'name':settings.admin_name}
    @app.post('/api/auth/logout')
    def logout(request:Request):
        auth_sessions.pop(request.cookies.get('safesense_session','').split('.')[0],None)
        response=JSONResponse({'ok':True}); response.delete_cookie('safesense_session'); return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
    @app.middleware('http')
    async def browser_safety(request, call_next):
        if request.url.path.startswith('/api/') and request.url.path not in ('/api/health','/api/auth/login') and not authenticated(request.cookies.get('safesense_session')):
            return JSONResponse({'detail':'Please sign in to continue.'},status_code=401)
        origin=request.headers.get('origin')
        if request.method not in ('GET','HEAD','OPTIONS') and origin and origin.split('://')[-1]!=request.headers.get('host'):
            return JSONResponse({'detail':'Cross-origin writes are not permitted'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        return response
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({'detail':[{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in exc.errors()]},status_code=422)
    app.state.manager=manager; app.state.sessions=sessions; app.state.events=events
    def require(s,model,id):
        row=s.get(model,id)
        if row is None: raise HTTPException(404,'Resource not found')
        return row
    def camera_out(s,c):
        result=record(c); result['source']=c.source if c.source_type!='network' or c.source.startswith('env:') else '[configured URL]'
        state=manager.state(c.id)
        result['zones']=[record(z) for z in s.scalars(select(Zone).where(Zone.camera_id==c.id)).all()]
        active=s.scalars(select(Incident).where(Incident.camera_id==c.id,Incident.status!='resolved')).all()
        severity=highest([i.severity for i in active])
        restricted=any(i.category=='restricted_entry' for i in active)
        major=any(i.severity=='critical' and i.category!='restricted_entry' for i in active)
        result.update(state=state,alert_severity=severity,alert_color='critical' if major else 'restricted' if restricted else severity)
        return result
    @app.get('/api/health')
    def health(): return {'status':'ok','version':'1.0.0'}
    @app.get('/api/cameras')
    def cameras():
        with sessions() as s: return [camera_out(s,c) for c in s.scalars(select(Camera)).all()]
    @app.post('/api/cameras',status_code=201)
    def add_camera(body:CameraInput):
        with sessions() as s:
            if len(s.scalars(select(Camera)).all())>=64: raise HTTPException(409,'A maximum of 64 cameras is supported in this workspace.')
            if body.source_type!='demo' and s.scalar(select(Camera).where(Camera.source_type==body.source_type,Camera.source==body.source)):
                raise HTTPException(409,'This camera source is already registered.')
            if body.enabled and body.source_type!='demo':
                from .video.sources import probe
                error=probe(body.source_type,body.source,settings)
                if error: raise HTTPException(422,error)
            c=Camera(**body.model_dump()); s.add(c); s.commit(); manager.refresh(c); return camera_out(s,c)
    @app.get('/api/cameras/{id}')
    def camera(id:int):
        with sessions() as s: return camera_out(s,require(s,Camera,id))
    @app.patch('/api/cameras/{id}')
    def edit_camera(id:int,body:CameraPatch):
        with sessions() as s:
            c=require(s,Camera,id)
            try: validated=CameraInput.model_validate({**record(c),**body.model_dump(exclude_unset=True)})
            except ValidationError: raise HTTPException(422,'Invalid camera configuration')
            if validated.enabled and validated.source_type!='demo' and (validated.source!=c.source or validated.source_type!=c.source_type or not c.enabled):
                from .video.sources import probe
                error=probe(validated.source_type,validated.source,settings)
                if error: raise HTTPException(422,error)
            if validated.source_type!='demo' and s.scalar(select(Camera).where(Camera.id!=id,Camera.source_type==validated.source_type,Camera.source==validated.source)):
                raise HTTPException(409,'This camera source is already registered.')
            for k,v in validated.model_dump().items(): setattr(c,k,v)
            s.commit(); manager.refresh(c); return camera_out(s,c)
    @app.delete('/api/cameras/{id}',status_code=204)
    def delete_camera(id:int):
        with sessions() as s:
            c=require(s,Camera,id); manager.remove(id); s.delete(c); s.commit()
    @app.get('/api/cameras/{id}/status')
    def camera_status(id:int):
        with sessions() as s: require(s,Camera,id)
        return manager.state(id)
    @app.get('/api/cameras/{id}/snapshot')
    def snapshot(id:int):
        with sessions() as s: require(s,Camera,id)
        worker=manager.workers.get(id)
        if not worker: raise HTTPException(503,'Camera is not connected')
        with worker.lock: jpeg=worker.jpeg
        if not jpeg: raise HTTPException(503,'Waiting for camera frames')
        return Response(jpeg,media_type='image/jpeg',headers={'Cache-Control':'no-store'})
    @app.get('/api/cameras/{id}/stream')
    async def stream(id:int,request:Request):
        with sessions() as s: require(s,Camera,id)
        async def frames():
            last=None
            while not await request.is_disconnected():
                if not authenticated(request.cookies.get('safesense_session')): return
                w=manager.workers.get(id)
                if not w: return
                with w.lock: jpeg=w.jpeg; seq=w.seq
                if jpeg and seq!=last:
                    last=seq
                    yield b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(jpeg)).encode()+b'\r\n\r\n'+jpeg+b'\r\n'
                await asyncio.sleep(1/settings.capture_fps)
        return StreamingResponse(frames(),media_type='multipart/x-mixed-replace; boundary=frame',headers={'Cache-Control':'no-store'})
    @app.get('/api/cameras/{id}/zones')
    def zones(id:int):
        with sessions() as s:
            require(s,Camera,id); return [record(z) for z in s.scalars(select(Zone).where(Zone.camera_id==id)).all()]
    @app.post('/api/cameras/{id}/zones',status_code=201)
    def add_zone(id:int,body:ZoneInput):
        with sessions() as s:
            require(s,Camera,id); z=Zone(camera_id=id,**body.model_dump()); s.add(z); s.commit(); return record(z)
    @app.put('/api/zones/{id}')
    def edit_zone(id:int,body:ZoneInput):
        with sessions() as s:
            z=require(s,Zone,id)
            for k,v in body.model_dump().items(): setattr(z,k,v)
            s.commit(); return record(z)
    @app.delete('/api/zones/{id}',status_code=204)
    def delete_zone(id:int):
        with sessions() as s: s.delete(require(s,Zone,id)); s.commit()
    @app.get('/api/incidents')
    def list_incidents(status:str|None=None,severity:str|None=None,camera_id:int|None=None,limit:int=100):
        with sessions() as s:
            q=select(Incident).order_by(Incident.id.desc()).limit(max(1,min(limit,500)))
            for field,value in [(Incident.status,status),(Incident.severity,severity),(Incident.camera_id,camera_id)]:
                if value is not None: q=q.where(field==value)
            return [record(i) for i in s.scalars(q).all()]
    @app.get('/api/incidents/{id}')
    def incident(id:int):
        with sessions() as s: return record(require(s,Incident,id))
    def transition(id,status):
        with incidents.lock, sessions() as s:
            i=require(s,Incident,id)
            if i.status=='resolved' or (i.status=='acknowledged' and status=='acknowledged'): raise HTTPException(409,'Incident has already reached this lifecycle stage')
            i.status=status; i.updated_at=now(); i.history=[*i.history,{'status':status,'at':now().isoformat()}]; s.commit()
            events.publish('incident.updated',{'id':id,'status':status}); return record(i)
    @app.post('/api/incidents/{id}/acknowledge')
    def acknowledge(id:int): return transition(id,'acknowledged')
    @app.post('/api/incidents/{id}/resolve')
    def resolve(id:int): return transition(id,'resolved')
    @app.get('/api/model/status')
    def model_status(): return detector.status()
    @app.get('/api/system/status')
    def system_status(): return {'model':detector.status(),'cameras':len(manager.workers),'recording':False,'authentication':True,'decision_support_only':True}
    @app.websocket('/ws/events')
    async def websocket(ws:WebSocket):
        if not authenticated(ws.cookies.get('safesense_session')): await ws.close(code=1008); return
        origin=ws.headers.get('origin')
        if origin and origin.split('://')[-1]!=ws.headers.get('host'): await ws.close(code=1008); return
        await ws.accept(); q=events.subscribe()
        try:
            await ws.send_json({'type':'connected','timestamp':now().isoformat(),'data':{}})
            while True:
                if not authenticated(ws.cookies.get('safesense_session')):
                    await ws.close(code=1008); return
                try: event=await asyncio.wait_for(q.get(),timeout=10)
                except asyncio.TimeoutError: event={'type':'heartbeat','timestamp':now().isoformat(),'data':{}}
                await ws.send_json(event)
        except (WebSocketDisconnect,RuntimeError): pass
        finally: events.clients.discard(q)
    app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
    @app.get('/')
    def index(): return FileResponse(ROOT/'frontend/index.html')
    return app
