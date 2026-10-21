import json
import sqlite3
from contextlib import contextmanager
from routerescue.config import database_path
from routerescue.domain.models import iso_now


@contextmanager
def connection():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=15000')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','user')), active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, last_attempt TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS trips (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id), source_event_id TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(trip_id,source_event_id));
        CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id), input_key TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(trip_id,input_key));
        CREATE TABLE IF NOT EXISTS previews (id TEXT PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id), run_id TEXT NOT NULL REFERENCES runs(id), body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inventory (trip_id TEXT NOT NULL REFERENCES trips(id), offer_id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(trip_id,offer_id));
        ''')
        # A stopped process cannot silently leave a recovery "running" forever.
        for row in db.execute("SELECT id,body FROM runs WHERE state='RUNNING'").fetchall():
            body=json.loads(row['body'])
            body.update(state='FAILED',error='Recovery interrupted by server restart. Start a new recovery.')
            db.execute('UPDATE runs SET state=?,input_key=?,body=? WHERE id=?',('FAILED','interrupted:'+row['id'],dump(body),row['id']))


def dump(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def audit(db, trip_id, actor, action, details):
    db.execute('INSERT INTO audit(trip_id,actor,action,created_at,body) VALUES(?,?,?,?,?)',(trip_id,actor,action,iso_now(),dump(details)))


def get_trip(db, trip_id, owner):
    row=db.execute('SELECT body FROM trips WHERE id=? AND owner=?',(trip_id,owner)).fetchone()
    return json.loads(row['body']) if row else None


def events_for(db, trip_id):
    return [json.loads(r['body']) for r in db.execute('SELECT body FROM events WHERE trip_id=? ORDER BY rowid',(trip_id,)).fetchall()]


def save_trip(db, trip):
    db.execute('UPDATE trips SET body=? WHERE id=?',(dump(trip),trip['id']))


def supersede(db, trip_id):
    for row in db.execute("SELECT id,body FROM runs WHERE trip_id=? AND state NOT IN ('SUPERSEDED','FAILED')",(trip_id,)).fetchall():
        run=json.loads(row['body'])
        run['state']='SUPERSEDED'
        db.execute('UPDATE runs SET state=?,body=? WHERE id=?',('SUPERSEDED',dump(run),row['id']))
