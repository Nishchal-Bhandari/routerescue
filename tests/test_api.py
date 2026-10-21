import json
import time
from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from routerescue import store


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('AGENT_MODE','fixture')
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    with TestClient(app) as c:
        assert c.post('/api/auth/login',json={'email':'aarav@routerescue.local','password':'Aarav@12345'}).status_code==200
        yield c


def create(c,scenario='flight'):
    response=c.post('/api/trips',json={'scenario':scenario})
    assert response.status_code==201,response.text
    return response.json()


def event(c,t,kind='FLIGHT_CANCELLED',key='event-1'):
    return c.post(f"/api/trips/{t['id']}/events",json={'event_type':kind,'source_event_id':key})


def recover(c,t):
    response=c.post(f"/api/trips/{t['id']}/recoveries")
    assert response.status_code==202,response.text
    run=response.json()
    for _ in range(100):
        run=c.get('/api/recoveries/'+run['id']).json()
        if run['state']!='RUNNING': return run
        time.sleep(.02)
    pytest.fail('Recovery did not finish')


def preview(c,run,option='A'):
    return c.post(f"/api/options/{option}/preview?run_id={run['id']}")


def confirm(c,p,key=None):
    return c.post('/api/previews/'+p['id']+'/confirm',json={'snapshot_hash':p['snapshot_hash'],'idempotency_key':key or 'confirmation-'+p['id']})


def test_end_to_end_second_disruption_and_receipt(client):
    c=client;t=create(c)
    assert event(c,t).status_code==200
    run=recover(c,t)
    assert run['ranked_ids']==['A']
    first=preview(c,run).json()
    assert first['snapshot']['cash_required_minor']==320000
    assert event(c,t,'BUS_UNAVAILABLE','event-2').status_code==200
    assert confirm(c,first).status_code==409
    run=recover(c,t)
    assert run['state']=='NO_FEASIBLE_PLAN' and run['frontier_ids']==['B','C']
    assert preview(c,run,'B').status_code==409
    t=c.get('/api/trips/'+t['id']).json()
    constraints={**t['constraints'],'cash_limit_minor':580000}
    assert c.patch('/api/trips/'+t['id']+'/constraints',json={'expected_version':t['constraint_version'],'constraints':constraints}).status_code==200
    run=recover(c,t);assert run['ranked_ids']==['B']
    p=preview(c,run,'B').json();assert confirm(c,p).status_code==200
    assert confirm(c,p).json()==confirm(c,p).json()
    assert confirm(c,p,'different-key').status_code==409
    receipt=c.get(f"/api/recoveries/{run['id']}/receipt").json()
    assert receipt['approval_status']=='SIMULATED_COMPLETE'
    assert receipt['booking_status']=='Booking pending with provider'
    assert receipt['cash_required_minor']==580000


def test_duplicate_event_run_and_conflicting_key(client):
    t=create(client);a=event(client,t);b=event(client,t)
    assert a.json()==b.json()
    assert len(client.get('/api/trips/'+t['id']).json()['events'])==1
    assert event(client,t,'BUS_UNAVAILABLE').status_code==409
    first=recover(client,t);second=recover(client,t)
    assert first['id']==second['id']


def test_owner_isolation_and_missing_session(client):
    t=create(client);event(client,t);run=recover(client,t);p=preview(client,run).json()
    cookie=client.cookies.get('rr_session');client.cookies.clear()
    assert client.get('/api/trips/'+t['id']).status_code==401
    client.post('/api/auth/login',json={'email':'diya@routerescue.local','password':'Diya@12345'})
    for path in ['/api/trips/'+t['id'],'/api/recoveries/'+run['id'],f"/api/recoveries/{run['id']}/receipt",f"/api/trips/{t['id']}/audit"]:
        assert client.get(path).status_code==404
    assert confirm(client,p).status_code==404
    assert all(trip['id']!=t['id'] for trip in client.get('/api/trips').json())


def test_expired_preview_and_tampering(client):
    t=create(client);event(client,t);run=recover(client,t);p=preview(client,run).json()
    altered={**p,'snapshot_hash':'wrong'}
    assert confirm(client,altered).status_code==409
    with store.connection() as db:
        p['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        db.execute('UPDATE previews SET body=? WHERE id=?',(store.dump(p),p['id']))
    assert confirm(client,p).status_code==409


def test_constraint_conflict_and_stale_preview(client):
    t=create(client);event(client,t);run=recover(client,t);p=preview(client,run).json()
    body={'expected_version':1,'constraints':{**t['constraints'],'cash_limit_minor':100000}}
    assert client.patch('/api/trips/'+t['id']+'/constraints',json=body).status_code==200
    assert client.patch('/api/trips/'+t['id']+'/constraints',json=body).status_code==409
    assert confirm(client,p).status_code==409
    assert client.get('/api/recoveries/'+run['id']).json()['state']=='SUPERSEDED'


@pytest.mark.parametrize('scenario,kind',[('train','TRAIN_DELAYED'),('hotel','HOTEL_CANCELLED')])
def test_other_scenarios(client,scenario,kind):
    t=create(client,scenario);assert event(client,t,kind).status_code==200
    run=recover(client,t);assert run['state']=='OPTIONS_READY'
    p=preview(client,run,run['ranked_ids'][0]);assert p.status_code==200
    assert confirm(client,p.json()).status_code==200


def test_sse_and_audit(client):
    t=create(client);event(client,t);run=recover(client,t)
    response=client.get('/api/recoveries/'+run['id']+'/events')
    assert 'event: done' in response.text and 'VALIDATED' in response.text
    assert len(client.get('/api/trips/'+t['id']+'/audit').json())==3


def test_csrf_and_invalid_intake(client):
    assert client.post('/api/trips',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/trips',json={'constraints':{'cash_limit_minor':-1,'latest_arrival':'2026-11-15T19:00:00'}}).status_code==422
    t=create(client)
    assert client.post('/api/trips/'+t['id']+'/recoveries').status_code==422
    assert event(client,t,'HOTEL_CANCELLED').status_code==422
