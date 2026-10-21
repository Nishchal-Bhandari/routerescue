"""Password authentication and revocable, server-side sessions."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from routerescue import store
from routerescue.domain.models import iso_now, parse_time

router = APIRouter(prefix='/api/auth', tags=['Authentication'])


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt$' + salt.hex() + '$' + digest.hex()


def verify_password(password, stored):
    try:
        _, salt, expected = stored.split('$')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def public_user(row):
    return {k: row[k] for k in ('id', 'email', 'name', 'role', 'active')}


def current_user(request: Request):
    token = request.cookies.get('rr_session', '')
    digest = hashlib.sha256(token.encode()).hexdigest()
    with store.connection() as db:
        row = db.execute('SELECT u.*, s.created_at AS session_created FROM sessions s JOIN users u ON u.id=s.owner WHERE s.token=?', (digest,)).fetchone()
    if not row or not row['active'] or parse_time(row['session_created']) < datetime.now(timezone.utc)-timedelta(hours=12):
        raise HTTPException(401, 'Please sign in to continue.')
    return public_user(row)


def require_admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required.')
    return user


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    email = body.email.strip().lower()
    key = hashlib.sha256((email + '|' + (request.client.host if request.client else 'local')).encode()).hexdigest()
    with store.connection() as db:
        attempt = db.execute('SELECT * FROM login_attempts WHERE key=?', (key,)).fetchone()
        if attempt and attempt['attempts'] >= 8 and parse_time(attempt['last_attempt']) > datetime.now(timezone.utc)-timedelta(minutes=10):
            raise HTTPException(429, 'Too many sign-in attempts. Try again in 10 minutes.')
        row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    # Perform a password derivation even for an unknown account.
    valid = verify_password(body.password, row['password_hash']) if row else verify_password(body.password, password_hash('unknown-account'))
    if not row or not valid or not row['active']:
        with store.connection() as db:
            count = attempt['attempts']+1 if attempt and parse_time(attempt['last_attempt']) > datetime.now(timezone.utc)-timedelta(minutes=10) else 1
            db.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)', (key, count, iso_now()))
        raise HTTPException(401, 'Email or password is incorrect.')
    token = secrets.token_urlsafe(32)
    with store.connection() as db:
        db.execute('DELETE FROM login_attempts WHERE key=?', (key,))
        old = request.cookies.get('rr_session', '')
        db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(old.encode()).hexdigest(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], iso_now()))
    response.set_cookie('rr_session', token, httponly=True, secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', samesite='strict', max_age=43200)
    return public_user(row)


@router.get('/me')
def me(user=Depends(current_user)):
    return user


@router.post('/logout')
def logout(request: Request, response: Response):
    token = request.cookies.get('rr_session', '')
    with store.connection() as db:
        db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie('rr_session')
    return {'signed_out': True}
