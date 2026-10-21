import json
import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from routerescue import store


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'accounts.sqlite3'))
    monkeypatch.setenv('AGENT_MODE','fixture')
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    with TestClient(app) as client:
        yield client


def login(client,email='aarav@routerescue.local',password='Aarav@12345'):
    response=client.post('/api/auth/login',json={'email':email,'password':password})
    assert response.status_code==200,response.text
    return response.json()


def test_seeded_accounts_and_private_trips(client):
    assert client.get('/api/trips').status_code==401
    assert client.post('/api/session').status_code==401
    user=login(client)
    trips=client.get('/api/trips').json()
    assert len(trips)==2 and all(trip['owner_id']==user['id'] for trip in trips)
    assert client.get('/api/admin/overview').status_code==403
    assert client.get('/api/auth/me').json()['email']=='aarav@routerescue.local'
    assert 'password_hash' not in client.get('/api/auth/me').text
    token=client.cookies.get('rr_session')
    with store.connection() as db:
        assert db.execute('SELECT token FROM sessions WHERE token=?',(token,)).fetchone() is None
    client.post('/api/auth/logout')
    client.cookies.set('rr_session',token)
    assert client.get('/api/auth/me').status_code==401


def test_admin_controls_and_inventory_versioning(client):
    traveller=login(client)
    trip=next(trip for trip in client.get('/api/trips').json() if trip['scenario']=='flight')
    client.post('/api/auth/logout')
    login(client,'admin@routerescue.local','Admin@12345')
    overview=client.get('/api/admin/overview').json()
    assert len(overview['users'])==5 and len(overview['trips'])==8
    inventory=client.get(f"/api/admin/trips/{trip['id']}/inventory").json()
    offer=inventory[0]
    changes={'expected_version':offer['version'],'cash_required_minor':123400,'availability_state':'UNAVAILABLE','capacity':2}
    changed=client.patch(f"/api/admin/trips/{trip['id']}/inventory/{offer['id']}",json=changes)
    assert changed.status_code==200
    assert changed.json()['version']==offer['version']+1
    assert changed.json()['ledger'][0]['amount_minor']==123400
    assert client.patch(f"/api/admin/trips/{trip['id']}/inventory/{offer['id']}",json=changes).status_code==409
    assert client.patch('/api/admin/users/'+traveller['id'],json={'active':False}).status_code==200
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'email':'aarav@routerescue.local','password':'Aarav@12345'}).status_code==401


def test_password_failure_throttle(client):
    for _ in range(8):
        assert client.post('/api/auth/login',json={'email':'unknown@example.test','password':'wrong'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'unknown@example.test','password':'wrong'}).status_code==429


def test_report_time_changes_search_results(client):
    from routerescue.providers.inventory import search_inventory
    from routerescue.domain.engine import evaluate
    login(client)
    trip=next(trip for trip in client.get('/api/trips').json() if trip['scenario']=='flight')
    event={'event_type':'FLIGHT_CANCELLED','source_event_id':'report-test','description':'The flight was cancelled and I can leave only at noon.','available_from':'2026-11-15T12:00:00+05:30'}
    response=client.post(f"/api/trips/{trip['id']}/events",json=event)
    assert response.status_code==200
    result=search_inventory(trip,[event])
    assert next(o for o in result if o['id']=='A')['availability_state']=='DEPARTED'
    assert next(o for o in result if o['id']=='B')['availability_state']=='AVAILABLE'
    assert evaluate(next(o for o in result if o['id']=='A'),trip['constraints'])['status']=='INFEASIBLE'


def test_live_mode_missing_key_is_not_silent_fixture_fallback(client,monkeypatch):
    login(client)
    trip=client.get('/api/trips').json()[0]
    monkeypatch.setenv('AGENT_MODE','openrouter')
    monkeypatch.delenv('OPENROUTER_API_KEY',raising=False)
    response=client.post(f"/api/trips/{trip['id']}/recoveries")
    assert response.status_code==503
    assert 'OpenRouter' in response.json()['detail']
