"""Queryable SQLite demo inventory. Admin changes drive subsequent tool results."""
import json
from datetime import datetime, timedelta, timezone
from routerescue import store
from routerescue.domain.models import iso_now, parse_time
from routerescue.providers.fixtures import offers


def search_inventory(trip, events):
    with store.connection() as db:
        rows = db.execute('SELECT body FROM inventory WHERE trip_id=? ORDER BY offer_id', (trip['id'],)).fetchall()
    # Unit fixtures and older projects are migrated lazily; all normal trips are seeded.
    inventory = [json.loads(row['body']) for row in rows] if rows else offers(trip['scenario'])
    withdrawn = any(e['event_type']=='BUS_UNAVAILABLE' for e in events)
    reported_times = [parse_time(e['available_from']) for e in events if e.get('available_from')]
    for offer in inventory:
        offer['fetched_at'] = iso_now()
        offer['valid_until'] = (datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()
        offer['source_id'] = 'sqlite:demo-inventory'
        if withdrawn and offer['id']=='A':
            offer.update(availability_state='UNAVAILABLE', version=offer['version']+1)
        if reported_times and parse_time(offer['legs'][0]['departure']) < max(reported_times):
            offer['availability_state'] = 'DEPARTED'
    return inventory
