import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from langsmith import traceable, tracing_context
from routerescue.config import runtime_status
from routerescue.store import connection, get_trip, events_for, dump, audit
from routerescue.domain.models import iso_now
from routerescue.domain.engine import impacts, evaluate, rank, frontier
from routerescue.providers.fixtures import offers
from routerescue.agent.planner import plan
from routerescue.providers.inventory import search_inventory


def update_run(run_id, **changes):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body,state FROM runs WHERE id=?',(run_id,)).fetchone()
        run=json.loads(row['body'])
        if row['state']=='SUPERSEDED': return run
        run.update(changes)
        db.execute('UPDATE runs SET state=?,body=? WHERE id=?',(run['state'],dump(run),run_id))
        return run


def stage(run_id, name, detail):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body,state FROM runs WHERE id=?',(run_id,)).fetchone()
        if row['state']=='SUPERSEDED': return
        run=json.loads(row['body'])
        run['progress'].append(dict(stage=name,detail=detail,at=iso_now()))
        db.execute('UPDATE runs SET body=? WHERE id=?',(dump(run),run_id))


@traceable(name='verify-and-assess-trip')
def assess(trip, events):
    return impacts(trip, events)


@traceable(name='search-fixture-inventory',run_type='tool')
def search(trip,events):
    return search_inventory(trip,events)


@traceable(name='validate-and-rank')
def validate(inventory,constraints):
    evaluations=[evaluate(o,constraints) for o in inventory]
    return evaluations,rank(evaluations,constraints['preference']),frontier(evaluations)


async def recover(run_id,owner):
    status=runtime_status()
    with tracing_context(enabled=status['langsmith_enabled'],project_name=status['langsmith_project']):
        await _recover(run_id,owner,langsmith_extra={'run_id':uuid.UUID(run_id),'metadata':{'data_mode':'SIMULATED','recovery_run_id':run_id}})


@traceable(name='RouteRescue recovery')
async def _recover(run_id,owner):
    started=time.perf_counter()
    try:
        with connection() as db:
            row=db.execute('SELECT body FROM runs WHERE id=?',(run_id,)).fetchone()
            run=json.loads(row['body'])
            trip=get_trip(db,run['trip_id'],owner)
            events=events_for(db,trip['id'])
        stage(run_id,'CONTEXT_READY','Loaded owned trip, constraints and event evidence.')
        impact=assess(trip,events)
        stage(run_id,'IMPACT_ANALYZED','Checked connected bookings and their cutoff times.')
        stage(run_id,'SEARCHING','Researching the bounded synthetic corridor inventory.')
        agent=await plan(owner,trip['id'],run_id)
        if runtime_status()['agent_mode']=='openrouter' and agent['status']!='COMPLETE':
            stage(run_id,'FAILED',agent['message'])
            update_run(run_id,state='FAILED',agent=agent,error=agent['message'],trace_id=run_id if runtime_status()['langsmith_enabled'] else None)
            return
        inventory=search(trip,events)
        if agent['status']=='COMPLETE':
            valid_ids={o['id'] for o in inventory}
            if not set(agent['candidate_ids']) <= valid_ids:
                raise ValueError('Agent returned unknown inventory IDs')
            inventory=[offer for offer in inventory if offer['id'] in agent['candidate_ids']]
        evaluations,ranked,front=validate(inventory,trip['constraints'])
        stage(run_id,'VALIDATED','Checked gross cash, venue arrival, transfers, needs and availability.')
        state='OPTIONS_READY' if ranked else 'NO_FEASIBLE_PLAN'
        stage(run_id,state,'Prepared validated options.' if ranked else 'No feasible option in the searched set; prepared explicit trade-offs.')
        update_run(run_id,state=state,impacts=impact,offers=inventory,evaluations=evaluations,ranked_ids=ranked,frontier_ids=front,recommended_option_id=ranked[0] if ranked else None,agent=agent,completed_at=iso_now(),elapsed_ms=round((time.perf_counter()-started)*1000),trace_id=run_id if runtime_status()['langsmith_enabled'] else None)
    except Exception as exc:
        stage(run_id,'FAILED',f'Recovery could not complete ({type(exc).__name__}). Retry the recovery.')
        update_run(run_id,state='FAILED',error='Recovery could not complete. Retry or inspect server diagnostics.')


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def booking_actions(trip, offer):
    if trip['scenario']=='hotel':
        return [{'booking_id':b['id'],'action':'CHANGE' if b['id']=='H1' else 'KEEP','detail':'Arrange replacement lodging; refund remains unverified.' if b['id']=='H1' else 'Retain existing booking; reconfirm provider details.','evidence_ids':['EV-POLICY-1']} for b in trip['bookings']]
    return [dict(booking_id=b['id'],action='CHANGE' if b['id'] in ('F1','T1') else 'REVIEW' if b['id']=='P1' else 'KEEP',detail='Arrange replacement transport. No old ticket is cancelled.' if b['id'] in ('F1','T1') else 'Review unused pickup with operator; refund not assumed.' if b['id']=='P1' else 'Fixture hotel cutoff met; reconfirm operational changes.' if b['id']=='H1' else 'Workshop missed; contact the operator.' if offer['id']=='C' else 'Workshop arrival preserved under fixture assumptions.',evidence_ids=['EV-POLICY-1']) for b in trip['bookings']]


def receipt(run, trip, offer):
    evaluation=next(e for e in run['evaluations'] if e['option_id']==offer['id'])
    return dict(run_id=run['id'],trip_id=trip['id'],trip_title=trip['title'],trip_version=trip['version'],constraint_version=trip['constraint_version'],option_version=offer['version'],option_id=offer['id'],generated_at=iso_now(),expires_at=offer['valid_until'],data_mode='SIMULATED',currency='INR',title=offer['title'],legs=offer['legs'],ledger=[{**r,'amount_minor':r['amount_minor']*trip['constraints']['passengers']} for r in offer['ledger']],cash_required_minor=evaluation['cash_required_minor'],venue_arrival=offer['arrival'],constraints=trip['constraints'],evaluation=evaluation,booking_actions=booking_actions(trip,offer),before_itinerary=trip['bookings'],refunds={'status':'UNVERIFIED','available_to_spend_minor':0},evidence=[{'id':e,'source':'Synthetic corridor fixtures v1','fetched_at':offer['fetched_at'],'valid_until':offer['valid_until'],'data_mode':'SIMULATED'} for e in offer['evidence_ids']],next_actions=['Verify fare, availability and accessibility directly with the provider.','Arrange the selected transport or stay with the provider.','Review the original booking and unused pickup; request refunds separately.'],booking_status='Booking pending with provider',approval_status='PREVIEW_READY',limitations='Synthetic inventory; no live provider search, purchase, cancellation or automatic monitoring.')
