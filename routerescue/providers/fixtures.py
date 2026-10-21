"""Synthetic inventory only. No provider inventory or booking claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from routerescue.domain.models import iso_now


def at(time):
    return f'2026-11-15T{time}:00+05:30'


def bookings(scenario):
    transport = {'id': 'F1', 'kind': 'air', 'title': 'Mangaluru → Bengaluru', 'provider': 'Demo Air · RR 204', 'start': at('09:00'), 'end': at('10:00'), 'location': 'Bengaluru airport', 'prepaid_minor': 420000}
    if scenario == 'train':
        transport.update(id='T1', kind='train', provider='Demo Rail · RR 102', start=at('06:00'), end=at('15:00'), location='Bengaluru station')
    return [transport,
        {'id': 'P1', 'kind': 'pickup', 'title': 'Your arrival pickup', 'provider': 'Demo Transfers', 'start': at('10:45') if scenario != 'train' else at('15:45'), 'end': at('11:30') if scenario != 'train' else at('16:15'), 'location': 'Bengaluru', 'prepaid_minor': 60000},
        {'id': 'H1', 'kind': 'hotel', 'title': 'Garden House', 'provider': 'Demo Stay · 1 night', 'start': at('14:00'), 'end': at('18:00'), 'location': 'Bengaluru centre', 'prepaid_minor': 200000},
        {'id': 'E1', 'kind': 'experience', 'title': 'An evening of local craft', 'provider': 'Demo cultural workshop', 'start': at('19:30'), 'end': at('21:00'), 'location': 'Bengaluru craft studio', 'prepaid_minor': 120000}]


def dependencies(scenario):
    return [
        {'from_id': 'T1' if scenario == 'train' else 'F1', 'to_id': 'P1', 'rule': 'ARRIVAL_BEFORE', 'buffer_minutes': 30},
        {'from_id': 'P1', 'to_id': 'H1', 'rule': 'CHECKIN_BEFORE', 'buffer_minutes': 30},
        {'from_id': 'H1', 'to_id': 'E1', 'rule': 'TRANSFER_TO', 'buffer_minutes': 60}]


def leg(origin, destination, departure, arrival, mode, label, buffer=0, dwell=0):
    return dict(origin=origin, destination=destination, departure=at(departure), arrival=at(arrival), mode=mode, label=label, boarding_buffer_minutes=buffer, dwell_minutes=dwell)


def offers(scenario='flight', unavailable=False):
    now = iso_now()
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    common = dict(version=1, data_mode='SIMULATED', source_id='fixture:regional-corridor:v1', fetched_at=now, valid_until=expiry, availability_state='AVAILABLE', capacity=4, bags=1, wheelchair=True, currency='INR', booking_changes=2, hotel_arrival=at('17:15'), evidence_ids=['EV-INVENTORY-1', 'EV-TRANSFER-1', 'EV-POLICY-1'])
    rows = [
        dict(id='A', title='The scenic way back on track', mode='bus', subtitle='Direct bus · hotel stop · local transfers', arrival=at('18:15'), ledger=[{'label':'Transfer to bus terminal','amount_minor':30000},{'label':'Intercity bus','amount_minor':230000},{'label':'Local transfers','amount_minor':40000},{'label':'Demo contingency','amount_minor':20000}], legs=[leg('Mangaluru','Mangaluru bus terminal','08:15','08:45','transfer','Transfer to terminal'),leg('Mangaluru bus terminal','Bengaluru bus terminal','09:15','16:45','bus','Coastal Express · simulated',15),leg('Bengaluru bus terminal','Garden House','16:45','17:15','transfer','Transfer to hotel',dwell=30),leg('Garden House','Bengaluru craft studio','17:45','18:15','transfer','Continue to the workshop')]),
        dict(id='B', title='More time in Bengaluru', mode='air', subtitle='Alternate flight · hotel stop · local transfers', arrival=at('17:00'), hotel_arrival=at('16:00'), ledger=[{'label':'Alternate flight','amount_minor':480000},{'label':'Local transfers','amount_minor':80000},{'label':'Demo contingency','amount_minor':20000}], legs=[leg('Mangaluru','Bengaluru airport','13:30','14:30','air','Demo Air · RR 312'),leg('Bengaluru airport','Garden House','14:30','16:00','transfer','Airport transfer',dwell=30),leg('Garden House','Bengaluru craft studio','16:30','17:00','transfer','Continue to the workshop')]),
        dict(id='C', title='A later, lighter fare', mode='bus', subtitle='Later bus · verified early hotel stop', arrival=at('19:45'), hotel_arrival=at('17:45'), ledger=[{'label':'Later bus','amount_minor':190000},{'label':'Local transfers','amount_minor':50000},{'label':'Demo contingency','amount_minor':20000}], legs=[leg('Mangaluru','Bengaluru bus terminal','10:00','17:15','bus','Coastal Express Late · simulated'),leg('Bengaluru bus terminal','Garden House','17:15','17:45','transfer','Transfer to hotel',dwell=30),leg('Garden House','Bengaluru craft studio','18:15','19:45','transfer','Evening traffic transfer')]),
        dict(id='D', title='Connection with too little time', mode='bus', subtitle='Connecting service · transfer cannot be made', arrival=at('18:00'), ledger=[{'label':'Connecting bus and transfers','amount_minor':270000},{'label':'Demo contingency','amount_minor':20000}], legs=[leg('Mangaluru','Hassan terminal','09:00','12:00','bus','First bus',dwell=45),leg('Hassan terminal','Bengaluru craft studio','12:10','18:00','bus','Connecting bus')])]
    if scenario == 'hotel':
        rows = [dict(id='H', title='A new stay, the same evening', mode='stay', subtitle='Replacement hotel · local transfer', arrival=at('18:15'), hotel_arrival=at('17:15'), booking_changes=1, ledger=[{'label':'Replacement room','amount_minor':240000},{'label':'Local transfer','amount_minor':30000},{'label':'Demo contingency','amount_minor':20000}], legs=[leg('Bengaluru airport','Courtyard Stay','16:00','17:15','transfer','Transfer to replacement hotel',dwell=30),leg('Courtyard Stay','Bengaluru craft studio','17:45','18:15','transfer','Continue to the workshop')])]
    result = []
    for row in rows:
        row = {**deepcopy(common), **row}
        if unavailable and row['id'] == 'A':
            row.update(availability_state='UNAVAILABLE', version=2)
        result.append(row)
    return result


def envelope(data, request_id='fixture'):
    return dict(schema_version='1.0', request_id=request_id, source_id='fixture:regional-corridor:v1', fetched_at=iso_now(), valid_until=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(), data_mode='SIMULATED', availability_state='AVAILABLE', evidence_ids=['EV-INVENTORY-1'], errors=[], data=data)
