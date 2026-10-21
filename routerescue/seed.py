"""Idempotent local demonstration accounts; never overwrite existing accounts."""
import uuid
from routerescue.auth import password_hash
from routerescue import store
from routerescue.domain.models import TripInput, iso_now
from routerescue.providers.fixtures import bookings, dependencies, offers

DEMO_USERS = [
    ('admin@routerescue.local', 'RouteRescue Admin', 'admin', 'Admin@12345'),
    ('aarav@routerescue.local', 'Aarav Sharma', 'user', 'Aarav@12345'),
    ('diya@routerescue.local', 'Diya Patel', 'user', 'Diya@12345'),
    ('kabir@routerescue.local', 'Kabir Rao', 'user', 'Kabir@12345'),
    ('meera@routerescue.local', 'Meera Nair', 'user', 'Meera@12345'),
]


def seed_accounts():
    with store.connection() as db:
        for index, (email, name, role, password) in enumerate(DEMO_USERS):
            if db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                continue
            owner = str(uuid.uuid4())
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)', (owner, email, name, password_hash(password), role, 1, iso_now()))
            if role == 'admin':
                continue
            for number in range(2):
                scenario = 'flight' if number == 0 else ('hotel' if index % 2 else 'train')
                trip = TripInput(title=f"{name.split()[0]}'s {'Bengaluru getaway' if number == 0 else 'return to the city'}", scenario=scenario).model_dump(mode='json')
                trip['constraints']['cash_limit_minor'] = [500000, 650000, 400000, 800000][index-1]
                trip['constraints']['preference'] = 'earliest_arrival' if index in (2,4) else 'lowest_cost'
                trip.update(id=str(uuid.uuid4()), owner_id=owner, version=1, constraint_version=1, created_at=iso_now(), bookings=bookings(scenario), dependencies=dependencies(scenario))
                db.execute('INSERT INTO trips VALUES(?,?,?)', (trip['id'], owner, store.dump(trip)))
                seed_inventory(db, trip)
                store.audit(db, trip['id'], 'system', 'TRIP_ASSIGNED', {'owner_id': owner})


def seed_inventory(db, trip):
    for offer in offers(trip['scenario']):
        db.execute('INSERT OR IGNORE INTO inventory VALUES(?,?,?)', (trip['id'], offer['id'], store.dump(offer)))
