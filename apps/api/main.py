import asyncio
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from routerescue.config import ROOT, runtime_status
from routerescue.domain.models import TripInput,EventInput,ConstraintPatch,ConfirmInput,iso_now,parse_time
from routerescue.providers.fixtures import bookings,dependencies,offers
from routerescue.domain.engine import impacts,evaluate
from routerescue import store
from routerescue.service import recover,receipt,snapshot_hash
from routerescue.auth import current_user, router as auth_router
from routerescue.seed import seed_accounts, seed_inventory
from routerescue.providers.inventory import search_inventory
from apps.api.admin import router as admin_router

tasks=set()


@asynccontextmanager
async def lifespan(app):
    store.initialize()
    seed_accounts()
    yield
    for task in tasks: task.cancel()
    if tasks: await asyncio.gather(*tasks,return_exceptions=True)


app=FastAPI(title='RouteRescue API',version='1.0.0',lifespan=lifespan)
app.include_router(auth_router)
app.include_router(admin_router)


@app.middleware('http')
async def security(request,call_next):
    if request.method in ('POST','PATCH','DELETE','PUT'):
        origin=request.headers.get('origin')
        if origin and origin not in (str(request.base_url).rstrip('/'),'http://127.0.0.1:5173','http://localhost:5173'):
            return Response('Cross-origin mutation rejected',status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site': return Response(status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
    return response


def owner(request:Request):
    return current_user(request)['id']


def owned_trip(db,trip_id,user):
    trip=store.get_trip(db,trip_id,user)
    if not trip: raise HTTPException(404,'Trip not found')
    return trip


def owned_run(db,run_id,user):
    row=db.execute('SELECT body FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row: raise HTTPException(404,'Recovery not found')
    run=json.loads(row['body'])
    trip=owned_trip(db,run['trip_id'],user)
    return run,trip


@app.get('/api/health')
def health():
    with store.connection() as db: db.execute('SELECT 1')
    return {'status':'ok','database':'SQLite'}


@app.post('/api/session')
def session(request:Request,response:Response):
    user=current_user(request)
    return {'owner_id':user['id'],'auth_mode':'Authenticated account'}


@app.get('/api/status')
def status(user=Depends(owner)): return runtime_status()


@app.get('/api/trips')
def list_trips(user=Depends(owner)):
    with store.connection() as db: return [json.loads(r['body']) for r in db.execute('SELECT body FROM trips WHERE owner=? ORDER BY rowid DESC',(user,))]


@app.post('/api/trips',status_code=201)
def create_trip(body:TripInput,user=Depends(owner)):
    trip=body.model_dump(mode='json')
    trip.update(id=str(uuid.uuid4()),owner_id=user,version=1,constraint_version=1,created_at=iso_now(),bookings=bookings(body.scenario),dependencies=dependencies(body.scenario))
    with store.connection() as db:
        if db.execute('SELECT count(*) FROM trips WHERE owner=?',(user,)).fetchone()[0]>=50: raise HTTPException(429,'Local demo limit reached: 50 trips per session.')
        db.execute('INSERT INTO trips VALUES(?,?,?)',(trip['id'],user,store.dump(trip)))
        seed_inventory(db,trip)
        store.audit(db,trip['id'],user,'TRIP_CREATED',{'scenario':trip['scenario']})
    return trip


@app.get('/api/trips/{trip_id}')
def get_trip(trip_id:str,user=Depends(owner)):
    with store.connection() as db:
        trip=owned_trip(db,trip_id,user); events=store.events_for(db,trip_id)
        rows=db.execute('SELECT body FROM runs WHERE trip_id=? ORDER BY rowid DESC LIMIT 1',(trip_id,)).fetchall()
    return {**trip,'events':events,'impacts':impacts(trip,events),'latest_run':json.loads(rows[0]['body']) if rows else None}


@app.post('/api/trips/{trip_id}/events')
def add_event(trip_id:str,body:EventInput,user=Depends(owner)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        trip=owned_trip(db,trip_id,user)
        existing=db.execute('SELECT body FROM events WHERE trip_id=? AND source_event_id=?',(trip_id,body.source_event_id)).fetchone()
        if existing:
            value=json.loads(existing['body'])
            if value['event_type']!=body.event_type: raise HTTPException(409,'Event key already used for a different event')
            return value
        expected={'flight':'FLIGHT_CANCELLED','train':'TRAIN_DELAYED','hotel':'HOTEL_CANCELLED'}[trip['scenario']]
        if body.event_type not in (expected,'BUS_UNAVAILABLE') or (body.event_type=='BUS_UNAVAILABLE' and trip['scenario']=='hotel'): raise HTTPException(422,'Event does not match this scenario')
        event={**body.model_dump(mode='json'),'id':str(uuid.uuid4()),'trip_id':trip_id,'data_mode':'USER_REPORTED','occurred_at':iso_now(),'evidence_id':'EV-EVENT-'+str(trip['version'])}
        db.execute('INSERT INTO events VALUES(?,?,?,?)',(event['id'],trip_id,body.source_event_id,store.dump(event)))
        trip['version']+=1; store.save_trip(db,trip); store.supersede(db,trip_id)
        store.audit(db,trip_id,user,'DISRUPTION_REPORTED',event)
    return event


@app.patch('/api/trips/{trip_id}/constraints')
def constraints(trip_id:str,body:ConstraintPatch,user=Depends(owner)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE'); trip=owned_trip(db,trip_id,user)
        if trip['constraint_version']!=body.expected_version: raise HTTPException(409,'Constraints changed. Refresh before editing.')
        trip.update(constraints=body.constraints.model_dump(mode='json'),constraint_version=trip['constraint_version']+1)
        store.save_trip(db,trip); store.supersede(db,trip_id); store.audit(db,trip_id,user,'CONSTRAINTS_CHANGED',trip['constraints'])
    return trip


@app.post('/api/trips/{trip_id}/recoveries',status_code=202)
async def start_recovery(trip_id:str,user=Depends(owner)):
    configuration=runtime_status()
    if configuration['agent_mode']=='openrouter' and not configuration['agent_available']:
        raise HTTPException(503,'OpenRouter is not configured. Ask the administrator to set OPENROUTER_API_KEY.')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE'); trip=owned_trip(db,trip_id,user)
        if not store.events_for(db,trip_id): raise HTTPException(422,'Report a disruption before recovering this trip.')
        key=f"{trip['version']}:{trip['constraint_version']}"
        row=db.execute('SELECT body FROM runs WHERE trip_id=? AND input_key=?',(trip_id,key)).fetchone()
        if row:
            previous=json.loads(row['body'])
            if previous['state'] not in ('FAILED','SUPERSEDED') and (not previous.get('offers') or all(parse_time(o['valid_until'])>datetime.now(timezone.utc) for o in previous['offers'])): return previous
            db.execute('UPDATE runs SET input_key=? WHERE id=?',('retired:'+previous['id'],previous['id']))
        active=db.execute("SELECT count(*) FROM runs WHERE state='RUNNING'").fetchone()[0]
        if active>=4: raise HTTPException(429,'Recovery queue is busy. Please retry shortly.')
        run=dict(id=str(uuid.uuid4()),trip_id=trip_id,trip_version=trip['version'],constraint_version=trip['constraint_version'],state='RUNNING',created_at=iso_now(),data_mode='SIMULATED',progress=[],offers=[],evaluations=[],ranked_ids=[],frontier_ids=[])
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(run['id'],trip_id,key,'RUNNING',store.dump(run)))
        store.audit(db,trip_id,user,'RECOVERY_STARTED',{'run_id':run['id']})
    task=asyncio.create_task(recover(run['id'],user)); tasks.add(task); task.add_done_callback(tasks.discard)
    return run


@app.get('/api/recoveries/{run_id}')
def get_recovery(run_id:str,user=Depends(owner)):
    with store.connection() as db: return owned_run(db,run_id,user)[0]


@app.get('/api/recoveries/{run_id}/events')
async def progress(run_id:str,user=Depends(owner)):
    with store.connection() as db: owned_run(db,run_id,user)
    async def stream():
        seen=0
        for _ in range(180):
            with store.connection() as db: run,_=owned_run(db,run_id,user)
            for item in run['progress'][seen:]: yield 'data: '+json.dumps(item)+'\n\n'
            seen=len(run['progress'])
            if run['state']!='RUNNING':
                yield 'event: done\ndata: '+json.dumps({'state':run['state']})+'\n\n'; return
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type='text/event-stream')


@app.get('/api/recoveries/{run_id}/trace')
async def trace_delivery(run_id:str, account=Depends(current_user)):
    with store.connection() as db:
        row=db.execute('SELECT body FROM runs WHERE id=?',(run_id,)).fetchone()
        if not row: raise HTTPException(404,'Recovery not found')
        run=json.loads(row['body'])
        if account['role']!='admin': owned_trip(db,run['trip_id'],account['id'])
    if not run.get('trace_id'): raise HTTPException(409,'No LangSmith trace was recorded for this run.')
    def read_trace():
        from langsmith import Client
        return Client(timeout_ms=10000).read_run(run['trace_id'])
    try:
        remote=await asyncio.wait_for(asyncio.to_thread(read_trace),timeout=12)
    except Exception:
        raise HTTPException(503,'Trace delivery could not be verified yet. Check the LangSmith connection and retry.')
    return {'verified':True,'trace_id':run['trace_id'],'url':remote.url,'name':remote.name}


def validated_offer(db,run,trip,option_id):
    if run['state'] in ('SUPERSEDED','RUNNING','FAILED') or run['trip_version']!=trip['version'] or run['constraint_version']!=trip['constraint_version']: raise HTTPException(409,'This recovery is stale. Run recovery again.')
    offer=next((o for o in run['offers'] if o['id']==option_id),None)
    if not offer: raise HTTPException(404,'Option not found')
    latest=next((o for o in search_inventory(trip,store.events_for(db,trip['id'])) if o['id']==option_id),None)
    if not latest or latest['version']!=offer['version'] or latest['availability_state']!='AVAILABLE': raise HTTPException(409,'Offer changed or is unavailable. Recover again.')
    if evaluate(offer,trip['constraints'])['status']!='FEASIBLE': raise HTTPException(409,'Option no longer passes all constraints. Recover again.')
    return offer


@app.post('/api/options/{option_id}/preview')
def preview(option_id:str,run_id:str,user=Depends(owner)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE'); run,trip=owned_run(db,run_id,user)
        offer=validated_offer(db,run,trip,option_id); snapshot=receipt(run,trip,offer)
        result=dict(id=str(uuid.uuid4()),trip_id=trip['id'],run_id=run_id,option_id=option_id,snapshot=snapshot,snapshot_hash=snapshot_hash(snapshot),expires_at=min(parse_time(offer['valid_until']),datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),state='PREVIEW_READY',outcome=None)
        db.execute('INSERT INTO previews VALUES(?,?,?,?)',(result['id'],trip['id'],run_id,store.dump(result)))
        store.audit(db,trip['id'],user,'PREVIEW_READY',{'preview_id':result['id'],'snapshot_hash':result['snapshot_hash']})
    return result


@app.post('/api/previews/{preview_id}/confirm')
def confirm(preview_id:str,body:ConfirmInput,user=Depends(owner)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body FROM previews WHERE id=?',(preview_id,)).fetchone()
        if not row: raise HTTPException(404,'Preview not found')
        preview=json.loads(row['body']); run,trip=owned_run(db,preview['run_id'],user)
        if body.snapshot_hash!=preview['snapshot_hash']: raise HTTPException(409,'Preview snapshot mismatch')
        if preview['outcome']:
            if preview['idempotency_key']!=body.idempotency_key: raise HTTPException(409,'Preview already confirmed with a different key')
            return preview
        if parse_time(preview['expires_at'])<=datetime.now(timezone.utc): raise HTTPException(409,'Preview expired. Review a fresh preview.')
        validated_offer(db,run,trip,preview['option_id'])
        preview.update(state='SIMULATED_COMPLETE',idempotency_key=body.idempotency_key,outcome={'status':'SIMULATED_COMPLETE','booking_status':'Booking pending with provider','confirmed_at':iso_now(),'reference':'DEMO-'+preview_id[:8]})
        db.execute('UPDATE previews SET body=? WHERE id=?',(store.dump(preview),preview_id))
        store.audit(db,trip['id'],user,'SIMULATED_COMPLETE',preview['outcome'])
    return preview


@app.get('/api/recoveries/{run_id}/receipt')
def download_receipt(run_id:str,option_id:str|None=None,user=Depends(owner)):
    with store.connection() as db:
        run,trip=owned_run(db,run_id,user)
        selected=option_id or run.get('recommended_option_id')
        if not selected: raise HTTPException(409,'No feasible plan. Choose an explicit trade-off first.')
        offer=validated_offer(db,run,trip,selected)
        result=receipt(run,trip,offer)
        for row in db.execute('SELECT body FROM previews WHERE run_id=? ORDER BY rowid DESC',(run_id,)):
            value=json.loads(row['body'])
            if value['option_id']==selected and value['outcome']:
                result=value['snapshot']; result={**result,'approval_status':'SIMULATED_COMPLETE','outcome':value['outcome']}; break
    return Response(json.dumps(result,indent=2,ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="routerescue-{run_id[:8]}.json"'})


@app.get('/api/trips/{trip_id}/audit')
def audit(trip_id:str,user=Depends(owner)):
    with store.connection() as db:
        owned_trip(db,trip_id,user)
        return [dict(r) | {'body':json.loads(r['body'])} for r in db.execute('SELECT * FROM audit WHERE trip_id=? ORDER BY id DESC',(trip_id,))]


web_dist=ROOT/'apps'/'web'/'dist'
if web_dist.exists():
    app.mount('/assets',StaticFiles(directory=web_dist/'assets'),name='assets')


@app.get('/')
@app.get('/login')
@app.get('/admin')
@app.get('/app')
def index():
    if (web_dist/'index.html').exists(): return FileResponse(web_dist/'index.html')
    return {'message':'Run npm.cmd run build in apps/web, then restart the API, or use the Vite dev server.'}
