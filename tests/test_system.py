import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.config import Settings
from app.main import create_app
from app.database.models import Incident
from app.safety.geometry import inside, validate_polygon
from app.safety.rules import highest, Rules
from app.ai.tracking import Tracker, associate
from app.ai.detector import Detector
from app.events import Events

@pytest.fixture
def system(tmp_path):
    config=Settings(model_path='',ppe_model_path='',fire_model_path='',database=str(tmp_path/'test.db'),min_observations=2,inference_fps=10,capture_fps=15)
    app=create_app(config)
    with TestClient(app) as client:
        assert client.post('/api/auth/login',json={'name':'admin','password':'admin'}).status_code==200
        yield client,app,config

def camera(c,source='synthetic',**kwargs):
    r=c.post('/api/cameras',json={'name':'Demo','location':'Lab','source_type':'demo','source':source,**kwargs}); assert r.status_code==201,r.text; return r.json()

def zone(c,id,**kwargs):
    r=c.post(f'/api/cameras/{id}/zones',json={'name':'Restricted floor','polygon':[[.05,.05],[.95,.05],[.95,.95],[.05,.95]],'required_ppe':['helmet'],**kwargs});assert r.status_code==201,r.text;return r.json()

def wait_for(fn,timeout=6):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(.05)
    raise AssertionError('Condition did not become true')

def test_health_static_model(system):
    c,a,s=system
    assert c.get('/api/health').json()['status']=='ok'
    assert 'SafeSense' in c.get('/').text
    assert c.get('/api/model/status').json()['state']=='unavailable'
    assert c.get('/api/system/status').json()['recording'] is False
    assert Detector(Settings(model_path='missing.pt')).status()['error']

def test_camera_crud_and_validation(system):
    c,a,s=system
    for body in [{'source_type':'usb','source':'-1'},{'source_type':'network','source':'file:///etc/passwd'},{'source_type':'network','source':'rtsp://user:secret@host/feed'},{'source_type':'demo','source':'fake'}]:
        assert c.post('/api/cameras',json={'name':'Bad',**body}).status_code==422
    cam=camera(c,enabled=False); id=cam['id']
    assert c.get(f'/api/cameras/{id}').json()['name']=='Demo'
    assert c.patch(f'/api/cameras/{id}',json={'name':''}).status_code==422
    assert c.patch(f'/api/cameras/{id}',json={'name':'Renamed','location':'Floor'}).json()['name']=='Renamed'
    network=c.post('/api/cameras',json={'name':'IP','source_type':'network','source':'https://example.com/feed?token=private','enabled':False}).json()
    assert network['source']=='[configured URL]'
    assert c.delete(f'/api/cameras/{id}').status_code==204
    assert c.get(f'/api/cameras/{id}').status_code==404

def test_offline_and_transitions(system):
    c,a,s=system; id=camera(c,'offline')['id']
    wait_for(lambda:c.get(f'/api/cameras/{id}/status').json()['status']=='offline')
    assert a.state.manager.workers[id].jpeg is None
    wait_for(lambda:len(c.get('/api/incidents').json())>0)
    assert c.get('/api/incidents').json()[0]['category']=='camera_offline'
    c.patch(f'/api/cameras/{id}',json={'source':'synthetic'})
    state=wait_for(lambda:(x if (x:=c.get(f'/api/cameras/{id}/status').json())['status']=='online' else None))
    assert state['last_frame_at']
    c.patch(f'/api/cameras/{id}',json={'enabled':False})
    assert c.get(f'/api/cameras/{id}/status').json()['status']=='offline'

def test_zones_and_invalid_geometry(system):
    c,a,s=system;id=camera(c,enabled=False)['id'];z=zone(c,id)
    assert c.get(f'/api/cameras/{id}/zones').json()[0]['polygon']==z['polygon']
    for points in [[[0,0],[1,1]],[[0,0],[1,0],[2,1]],[[0,0],[1,1],[1,0],[0,1]],[[0,0],[.5,.5],[1,1]],[[0,0],[0,0],[1,0],[1,1]]]:
        assert c.post(f'/api/cameras/{id}/zones',json={'name':'Bad','polygon':points}).status_code==422
    z['name']='Changed';assert c.put(f"/api/zones/{z['id']}",json=z).json()['name']=='Changed'
    assert c.delete(f"/api/zones/{z['id']}").status_code==204
    assert c.get(f'/api/cameras/{id}/zones').json()==[]

def test_demo_pipeline_incident_lifecycle_and_persistence(system):
    c,a,s=system;id=camera(c)['id'];zone(c,id)
    records=wait_for(lambda:[i for i in c.get('/api/incidents').json() if i['category']=='potential_missing_ppe'])
    i=records[0];assert i['simulated'];assert i['evidence']['not_detected']==['helmet']
    worker=a.state.manager.workers[id]
    first=worker.jpeg;time.sleep(.3);assert worker.jpeg!=first and worker.jpeg[:2]==b'\xff\xd8'
    time.sleep(.4)
    assert len(c.get('/api/incidents').json())==2
    assert c.post(f"/api/incidents/{i['id']}/acknowledge").json()['status']=='acknowledged'
    assert c.post(f"/api/incidents/{i['id']}/resolve").json()['status']=='resolved'
    assert c.post(f"/api/incidents/{i['id']}/acknowledge").status_code==409
    c.patch(f'/api/cameras/{id}',json={'enabled':False})
    with TestClient(create_app(s)) as second:
        second.post('/api/auth/login',json={'name':'admin','password':'admin'})
        assert second.get(f"/api/incidents/{i['id']}").json()['status']=='resolved'
        assert len(second.get(f'/api/cameras/{id}/zones').json())==1
    assert c.get('/api/incidents?status=resolved').json()[0]['id']==i['id']
    c.delete(f'/api/cameras/{id}')
    assert c.get(f"/api/incidents/{i['id']}").json()['camera_id'] is None

def test_geometry_and_severity():
    p=validate_polygon([[0,0],[1,0],[1,1],[0,1]])
    assert inside((.5,.5),p) and inside((0,.5),p) and not inside((2,2),p)
    assert highest(['info','critical','warning'])=='critical'
    assert highest([])=='normal'

def person(box=(.1,.1,.4,.9)):
    return {'class_id':0,'label':'person','bbox':list(box),'confidence':.9}

def test_tracking_and_exclusive_ppe_association():
    t=Tracker();people=t.update([person(),person((.2,.1,.5,.9))],0)
    helmet={'label':'helmet','bbox':[.23,.12,.29,.2]}
    ppe=associate(people,[helmet],{'helmet'})
    assert sum(p['helmet']=='detected' for p in ppe.values())==1
    assert all(p['vest']=='unsupported' for p in ppe.values())
    assert t.update([person()],1)[0]['track_id']==people[0]['track_id']
    assert t.update([person()],4)[0]['track_id']!=people[0]['track_id']
    cropped=t.update([person((0,0,.5,.8))],5)
    assert associate(cropped,[],{'helmet'})[cropped[0]['track_id']]['helmet']=='insufficient_evidence'

def test_rule_persistence_reset_and_unsupported():
    from types import SimpleNamespace
    class Recorder:
        def __init__(self):self.calls=[]
        def report(self,*args):self.calls.append(args)
    r=Recorder();rule=Rules(r,2);z=SimpleNamespace(id=1,name='PPE checkpoint',enabled=True,type='warning',polygon=[[0,0],[1,0],[1,1],[0,1]],required_ppe=['helmet'],severity='warning')
    p={**person(),'track_id':1}
    for _ in range(3):rule.evaluate(1,[z],[p],{1:{'helmet':'unsupported'}},False)
    assert not r.calls
    rule.evaluate(1,[z],[p],{1:{'helmet':'not_detected'}},False);assert not r.calls
    rule.evaluate(1,[z],[],{},False)
    rule.evaluate(1,[z],[p],{1:{'helmet':'not_detected'}},False);assert not r.calls
    rule.evaluate(1,[z],[p],{1:{'helmet':'not_detected'}},False);assert len(r.calls)==1

def test_websocket_event_schema(system):
    c,a,s=system
    with c.websocket_connect('/ws/events') as ws:
        hello=ws.receive_json();assert hello['type']=='connected'
        a.state.events.publish('test.event',{'id':123})
        event=ws.receive_json();assert event['type']=='test.event' and event['data']['id']==123 and event['timestamp']

def test_event_queue_bounded():
    e=Events();q=e.subscribe()
    for n in range(200):e._send({'n':n})
    assert q.qsize()==100 and q.get_nowait()['n']==100

def test_cross_origin_and_no_credential_echo(system):
    c,a,s=system
    assert c.post('/api/cameras',json={},headers={'origin':'https://other.example'}).status_code==403
    response=c.post('/api/cameras',json={'name':'bad','source_type':'network','source':'rtsp://user:private_password@host/feed'})
    assert response.status_code==422 and 'private_password' not in response.text
    assert c.get('/api/health',headers={'host':'evil.example'}).status_code==400

def test_camera_environment_references_from_dotenv(tmp_path,monkeypatch):
    import app.config as config
    monkeypatch.setattr(config,'ROOT',tmp_path)
    (tmp_path/'.env').write_text('TEST_CAMERA_SOURCE=https://camera.example/feed\n')
    settings=Settings()
    assert settings.source_variable('TEST_CAMERA_SOURCE')=='https://camera.example/feed'
    monkeypatch.setenv('TEST_CAMERA_SOURCE','https://other.example/feed')
    assert settings.source_variable('TEST_CAMERA_SOURCE')=='https://other.example/feed'
    assert settings.source_variable('NONEXISTENT_CAMERA_VARIABLE')==''


def test_authentication_enforced(tmp_path):
    app=create_app(Settings(database=str(tmp_path/'auth.db'),model_path='',ppe_model_path='',fire_model_path=''))
    with TestClient(app) as c:
        assert c.get('/api/cameras').status_code==401
        assert c.get('/api/cameras/1/stream').status_code==401
        assert c.post('/api/auth/login',json={'name':'admin','password':'wrong'}).status_code==401
        assert c.post('/api/auth/login',json={'name':'admin','password':'admin'}).status_code==200
        assert c.get('/api/auth/session').json()['name']=='admin'
        assert c.get('/api/cameras').status_code==200
        token=c.cookies.get('safesense_session')
        assert c.post('/api/auth/logout').status_code==200
        assert c.get('/api/cameras').status_code==401
        c.cookies.set('safesense_session',token)
        assert c.get('/api/cameras').status_code==401
        with pytest.raises(Exception):
            with c.websocket_connect('/ws/events') as ws: ws.receive_json()


def test_camera_connection_probe_failure_and_duplicates(system,monkeypatch):
    c,a,s=system
    monkeypatch.setattr('app.video.sources.probe',lambda *a:'USB camera not found or in use.')
    body={'name':'USB','location':'Lab','source_type':'usb','source':'0'}
    assert c.post('/api/cameras',json=body).status_code==422
    assert c.get('/api/cameras').json()==[]
    body['enabled']=False
    assert c.post('/api/cameras',json=body).status_code==201
    assert c.post('/api/cameras',json=body).status_code==409
    assert c.post('/api/cameras',json={**body,'source':'1','name':'  '}).status_code==422


def test_snapshot_has_real_jpeg_bytes(system):
    c,a,s=system;id=camera(c)['id']
    wait_for(lambda:a.state.manager.workers[id].jpeg)
    response=c.get(f'/api/cameras/{id}/snapshot')
    assert response.status_code==200
    assert response.headers['content-type']=='image/jpeg'
    assert response.content.startswith(b'\xff\xd8')
    assert response.headers['cache-control']=='no-store'


def test_danger_and_restricted_categories_and_hazard_persistence():
    from types import SimpleNamespace
    class Recorder:
        def __init__(self):self.calls=[]
        def report(self,*args):self.calls.append(args)
    recorder=Recorder();rules=Rules(recorder,2)
    zones=[SimpleNamespace(id=i,enabled=True,type=kind,name=kind,polygon=[[0,0],[1,0],[1,1],[0,1]],required_ppe=[],severity='critical') for i,kind in [(1,'danger'),(2,'restricted')]]
    person_record={**person(),'track_id':1}
    for _ in range(2):rules.evaluate(1,zones,[person_record],{1:{}},False)
    assert {call[3] for call in recorder.calls}=={'danger_entry','restricted_entry'}
    fire={'label':'fire','confidence':.92,'bbox':[.1,.1,.4,.4]}
    rules.hazards(1,[fire]);assert len(recorder.calls)==2
    rules.hazards(1,[])
    rules.hazards(1,[fire]);assert len(recorder.calls)==2
    rules.hazards(1,[fire]);assert recorder.calls[-1][3]=='fire_hazard'
    assert recorder.calls[-1][6]['consecutive_observations']==2


def test_cropped_webcam_checks_visible_ppe_per_item():
    people=[{**person((.2,.08,.8,1)), 'track_id':1}]
    result=associate(people,[{'label':'vest','bbox':[.3,.35,.7,.7]}],{'helmet','vest','boots'})[1]
    assert result=={'helmet':'not_detected','vest':'detected','gloves':'unsupported','boots':'insufficient_evidence'}
    wide=[{**person((0,.08,1,1)), 'track_id':2}]
    result=associate(wide,[],{'helmet','vest','boots'})[2]
    assert result['helmet']==result['vest']=='not_detected'
    assert result['boots']=='insufficient_evidence'


def test_ppe_one_or_all_missing_outside_zone_and_alternating_evidence():
    from types import SimpleNamespace
    class Recorder:
        def __init__(self):self.calls=[]
        def report(self,*args):self.calls.append(args)
    recorder=Recorder();rule=Rules(recorder,2)
    z=SimpleNamespace(id=1,name='Webcam PPE',enabled=True,type='warning',polygon=[[.1,.05],[.9,.05],[.9,.95],[.1,.95]],required_ppe=['helmet','vest'],severity='warning')
    p={**person((.2,.08,.8,1)), 'track_id':1}
    # Legs are outside the frame; the visible torso is inside the PPE checkpoint.
    for _ in range(2):result=rule.evaluate(1,[z],[p],{1:{'helmet':'not_detected','vest':'detected'}},False)
    assert result[0]['status']=='missing' and result[0]['missing']==['helmet']
    assert recorder.calls[-1][6]['not_detected']==['helmet'] and recorder.calls[-1][-1] is False
    rule.reset();recorder.calls.clear()
    for _ in range(2):rule.evaluate(1,[z],[p],{1:{'helmet':'not_detected','vest':'not_detected'}},False)
    assert recorder.calls[-1][6]['not_detected']==['helmet','vest']
    # Different missing items in successive frames cannot build one false streak.
    rule.reset();recorder.calls.clear()
    for i in range(6):rule.evaluate(1,[z],[p],{1:{'helmet':'not_detected' if i%2 else 'detected','vest':'detected' if i%2 else 'not_detected'}},False)
    assert not recorder.calls
    outside={**p,'bbox':[.91,.1,.99,.8]}
    for _ in range(3):assert rule.evaluate(1,[z],[outside],{1:{'helmet':'not_detected','vest':'not_detected'}},False)==[]
    assert not recorder.calls
    for _ in range(3):result=rule.evaluate(1,[z],[p],{1:{'helmet':'detected','vest':'detected'}},False)
    assert result[0]['status']=='compliant' and not recorder.calls


def test_recorded_footage_uses_real_inference_and_protects_local_paths(system,monkeypatch):
    c,app,settings=system
    detector=app.state.manager.args[1]
    monkeypatch.setattr(detector,'detect',lambda frame:[person()])
    detector.names={0:'person',1:'helmet',2:'vest'};detector.model=object()
    for source in ('../../etc/passwd','/etc/passwd','file:///etc/passwd'):
        assert c.post('/api/cameras',json={'name':'Invalid','source_type':'video','source':source}).status_code==422
    assert len(c.get('/api/video-samples').json())==3
    response=c.post('/api/cameras',json={'name':'Real recording','source_type':'video','source':'worker-zone'})
    assert response.status_code==201,response.text
    id=response.json()['id']
    zone(c,id,type='warning',required_ppe=['helmet','vest'])
    records=wait_for(lambda:[i for i in c.get('/api/incidents').json() if i['category']=='potential_missing_ppe'])
    assert records[0]['simulated'] is False and records[0]['evidence']['not_detected']==['helmet','vest']
    state=c.get(f'/api/cameras/{id}/status').json()
    assert state['simulated'] is False and state['ppe_assessments'][0]['status']=='missing'
    assert c.get(f'/api/cameras/{id}/snapshot').content[:2]==b'\xff\xd8'
    assert c.post('/api/cameras',json={'name':'Duplicate','source_type':'video','source':'worker-zone'}).status_code==409


def test_recording_loops_and_inference_survives(system,monkeypatch,tmp_path):
    c,app,settings=system
    import cv2
    import numpy as np
    clip=tmp_path/'short.avi';writer=cv2.VideoWriter(str(clip),cv2.VideoWriter_fourcc(*'MJPG'),10,(160,120))
    for value in [30,90,150,210]:writer.write(np.full((120,160,3),value,dtype=np.uint8))
    writer.release()
    monkeypatch.setattr('app.video.catalog.video_path',lambda key:clip)
    response=c.post('/api/cameras',json={'name':'Loop','source_type':'video','source':'walkthrough'})
    assert response.status_code==201
    worker=app.state.manager.workers[response.json()['id']]
    wait_for(lambda:worker.jpeg)
    wait_for(lambda:worker.capture_epoch>=2)
    assert worker.state()['status']=='online' and worker.jpeg[:2]==b'\xff\xd8'


def test_person_model_fallback_keeps_unmatched_specialist_people(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    def box(xy):
        return SimpleNamespace(cls=SimpleNamespace(item=lambda:0),conf=SimpleNamespace(item=lambda:.9),xyxy=[SimpleNamespace(tolist=lambda:xy)])
    class FakeYOLO:
        def __init__(self,path,**kwargs): self.ppe='ppe' in path;self.names={0:'Person' if self.ppe else 'person'}
        def predict(self,*args,**kwargs):return [SimpleNamespace(boxes=[box([10,10,40,90]),box([60,10,90,90])] if self.ppe else [box([10,10,40,90])])]
    monkeypatch.setitem(sys.modules,'ultralytics',SimpleNamespace(YOLO=FakeYOLO))
    for name in ['people.pt','ppe.pt']:(tmp_path/name).touch()
    detector=Detector(Settings(model_path=str(tmp_path/'people.pt'),ppe_model_path=str(tmp_path/'ppe.pt'),fire_model_path=''))
    detections=detector.detect(SimpleNamespace(shape=(100,100,3)))
    assert len(detections)==2 and all(d['label']=='person' for d in detections)
