import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from routerescue import store
from routerescue.auth import require_admin, public_user
from routerescue.config import runtime_status
from routerescue.domain.models import iso_now

router = APIRouter(prefix='/api/admin', tags=['Administration'])


@router.get('/overview')
def overview(admin=Depends(require_admin)):
    with store.connection() as db:
        users = [public_user(row) for row in db.execute('SELECT * FROM users ORDER BY role,email')]
        trips = [json.loads(row['body']) for row in db.execute('SELECT body FROM trips WHERE owner IN (SELECT id FROM users) ORDER BY rowid DESC')]
        runs = [json.loads(row['body']) for row in db.execute('SELECT body FROM runs WHERE trip_id IN (SELECT id FROM trips WHERE owner IN (SELECT id FROM users)) ORDER BY rowid DESC LIMIT 100')]
        audit = [dict(row) for row in db.execute('SELECT id,trip_id,actor,action,created_at FROM audit WHERE trip_id IN (SELECT id FROM trips WHERE owner IN (SELECT id FROM users)) ORDER BY id DESC LIMIT 100')]
    return {'users':users, 'trips':trips, 'runs':runs, 'audit':audit, 'runtime':runtime_status()}


class AccountUpdate(BaseModel):
    active: bool


@router.patch('/users/{user_id}')
def update_account(user_id:str, body:AccountUpdate, admin=Depends(require_admin)):
    with store.connection() as db:
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row: raise HTTPException(404, 'User not found')
        if row['role']=='admin': raise HTTPException(409, 'The administrator account cannot be disabled here.')
        db.execute('UPDATE users SET active=? WHERE id=?', (int(body.active), user_id))
        if not body.active: db.execute('DELETE FROM sessions WHERE owner=?', (user_id,))
        store.audit(db, 'admin', admin['id'], 'ACCOUNT_STATUS_CHANGED', {'user_id':user_id, 'active':body.active})
    return {'id':user_id, 'active':body.active}


@router.get('/trips/{trip_id}/inventory')
def inventory(trip_id:str, admin=Depends(require_admin)):
    with store.connection() as db:
        if not db.execute('SELECT id FROM trips WHERE id=?', (trip_id,)).fetchone(): raise HTTPException(404, 'Trip not found')
        return [json.loads(row['body']) for row in db.execute('SELECT body FROM inventory WHERE trip_id=? ORDER BY offer_id', (trip_id,))]


class OfferUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    cash_required_minor: int | None = Field(default=None, ge=0, le=100000000)
    availability_state: Literal['AVAILABLE','UNAVAILABLE']
    capacity: int = Field(ge=0, le=100)


@router.patch('/trips/{trip_id}/inventory/{offer_id}')
def update_offer(trip_id:str, offer_id:str, body:OfferUpdate, admin=Depends(require_admin)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT body FROM inventory WHERE trip_id=? AND offer_id=?',(trip_id,offer_id)).fetchone()
        if not row: raise HTTPException(404,'Inventory item not found')
        offer = json.loads(row['body'])
        if offer['version'] != body.expected_version: raise HTTPException(409,'Inventory changed. Reload before saving.')
        offer.update(version=offer['version']+1, availability_state=body.availability_state, capacity=body.capacity)
        offer['ledger']=[{'label':'Updated fare, transfers and contingency (per traveller)', 'amount_minor':body.cash_required_minor}]
        offer['evidence_ids']=[f"INV-{offer_id}-v{offer['version']}",'EV-TRANSFER-1','EV-POLICY-1']
        db.execute('UPDATE inventory SET body=? WHERE trip_id=? AND offer_id=?',(store.dump(offer),trip_id,offer_id))
        trip = json.loads(db.execute('SELECT body FROM trips WHERE id=?',(trip_id,)).fetchone()['body'])
        trip['version'] += 1
        store.save_trip(db,trip)
        store.supersede(db,trip_id)
        store.audit(db,trip_id,admin['id'],'INVENTORY_UPDATED',{'offer_id':offer_id,'version':offer['version']})
    return offer
