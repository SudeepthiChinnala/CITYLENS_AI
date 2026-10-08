"""Authentication router for CityLens AI platform.

Supports salted PBKDF2 passwords, role-based access, and signed stateless tokens
for cross-instance and cross-domain compatibility.
"""
import base64
from dataclasses import dataclass
from pathlib import Path
import hashlib
import hmac
import os
import re
import secrets
import time
import json
from typing import Callable

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db

load_dotenv(Path(__file__).with_name('.env'), override=False)

router = APIRouter(prefix='/auth', tags=['authentication'])
SESSION_COOKIE = 'citylens_portal_session'
PASSWORD_ITERATIONS = 310_000

SECRET_KEY = os.getenv('CITYLENS_SECRET_KEY', os.getenv('JWT_SECRET', 'citylens-hackathon-secret-key-2026'))

try:
    SESSION_TTL_SECONDS = min(max(int(os.getenv('CITYLENS_SESSION_TTL_SECONDS', '28800')), 300), 86_400)
except ValueError:
    SESSION_TTL_SECONDS = 28_800

DEFAULT_ADMIN_ID = 'ADMIN-001'
DEFAULT_ADMIN_HASH = 'pbkdf2_sha256$310000$14060585d97de66ed2a25760f34054c4$17cf89d4772559fd2d8da8a9877ae40233b3188e51c4c333b83c8919fc82c54a'
DEFAULT_CITIZEN_ID = 'CIT-001'
DEFAULT_CITIZEN_HASH = 'pbkdf2_sha256$310000$d0b77daebbec373f3517b542f80ead92$d425641dcf95d29b876c4807b346c7f8ad7ec77a7b9c65c9332d425f1bd6445e'


@dataclass(frozen=True)
class PortalIdentity:
    role: str
    account_id: str


@dataclass(frozen=True)
class _Session:
    identity: PortalIdentity
    expires_at: float


_sessions: dict[str, _Session] = {}


def generate_token(identity: PortalIdentity) -> str:
    """Generate a signed, stateless token for cross-instance and cross-domain authentication."""
    expires_at = time.time() + SESSION_TTL_SECONDS
    payload_data = {
        'role': identity.role,
        'account_id': identity.account_id,
        'exp': expires_at,
    }
    payload_bytes = json.dumps(payload_data, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> PortalIdentity | None:
    """Verify signed token signature and expiration timestamp."""
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        padding = '=' * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload_data = json.loads(payload_bytes.decode('utf-8'))
        if payload_data.get('exp', 0) <= time.time():
            return None
        return PortalIdentity(role=payload_data['role'], account_id=payload_data['account_id'])
    except Exception:
        return None


class PortalLoginRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class CitizenRegistrationRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('full_name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Enter your full name.')
        return value

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        parts = value.split('@')
        if len(parts) != 2:
            raise ValueError('Enter a valid email address.')
        local, domain = parts
        labels = domain.split('.')
        valid_local = (
            bool(local)
            and len(local) <= 64
            and not local.startswith('.')
            and not local.endswith('.')
            and '..' not in local
            and re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local) is not None
        )
        valid_domain = (
            len(labels) >= 2
            and len(labels[-1]) >= 2
            and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)
        )
        if not valid_local or not valid_domain:
            raise ValueError('Enter a valid email address.')
        return value

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        digits = re.sub(r'\D', '', value)
        if not re.fullmatch(r'[+0-9().\- ]+', value) or not 7 <= len(digits) <= 15:
            raise ValueError('Enter a valid phone number or leave it blank.')
        return value


def hash_password(password: str, salt_hex: str | None = None) -> str:
    """Return a salted PBKDF2-SHA256 verifier for backend-only storage."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PASSWORD_ITERATIONS)
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, expected_hex = encoded.split('$', 3)
        iterations = int(iterations_text)
        if algorithm != 'pbkdf2_sha256' or not 100_000 <= iterations <= 1_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError):
        return False


def _account_config(role: str) -> tuple[str, str]:
    if role == 'admin':
        env_id = os.getenv('CITYLENS_ADMIN_ID', '').strip()
        env_hash = os.getenv('CITYLENS_ADMIN_PASSWORD_HASH', '').strip()
        return env_id or DEFAULT_ADMIN_ID, env_hash or DEFAULT_ADMIN_HASH
    else:
        env_id = os.getenv('CITYLENS_CITIZEN_ID', '').strip()
        env_hash = os.getenv('CITYLENS_CITIZEN_PASSWORD_HASH', '').strip()
        return env_id or DEFAULT_CITIZEN_ID, env_hash or DEFAULT_CITIZEN_HASH


def _raise_if_known_wrong_portal(role: str, account_id: str):
    normalized = account_id.strip().lower()
    known_roles = {
        'admin': _account_config('admin')[0].lower(),
        'citizen': _account_config('citizen')[0].lower(),
    }
    for known_role, known_id in known_roles.items():
        if known_id and known_role != role and hmac.compare_digest(normalized, known_id):
            label = 'Admin' if known_role == 'admin' else 'Citizen'
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'These credentials belong to a different portal. Please sign in through the {label} Portal.',
            )


def _new_session(response: Response, request: Request, identity: PortalIdentity) -> dict:
    now = time.time()
    for token_key, session in list(_sessions.items()):
        if session.expires_at <= now:
            _sessions.pop(token_key, None)

    token = generate_token(identity)
    _sessions[token] = _Session(identity=identity, expires_at=now + SESSION_TTL_SECONDS)

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        path='/api',
        httponly=True,
        secure=request.url.scheme == 'https',
        samesite='lax',
    )
    return {'role': identity.role, 'account_id': identity.account_id, 'token': token}


def _login(role: str, payload: PortalLoginRequest, request: Request, response: Response) -> dict:
    _raise_if_known_wrong_portal(role, payload.account_id)
    expected_id, encoded_hash = _account_config(role)
    if not expected_id or not encoded_hash:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Portal credentials are not configured on the backend.')
    id_matches = hmac.compare_digest(payload.account_id.strip(), expected_id)
    password_matches = verify_password(payload.password, encoded_hash)
    if not (id_matches and password_matches):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid portal ID or password.')
    return _new_session(response, request, PortalIdentity(role=role, account_id=expected_id))


@router.post('/citizen/login')
async def citizen_login(
    payload: PortalLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from .models import CitizenAccount

    account_key = payload.account_id.strip()
    _raise_if_known_wrong_portal('citizen', account_key)
    account = db.query(CitizenAccount).filter(
        or_(
            CitizenAccount.citizen_id == account_key,
            func.lower(CitizenAccount.email) == account_key.lower(),
        )
    ).first()
    if account:
        if not verify_password(payload.password, account.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid portal ID or password.')
        return _new_session(response, request, PortalIdentity(role='citizen', account_id=account.citizen_id))
    return _login('citizen', payload, request, response)


@router.post('/citizen/register', status_code=status.HTTP_201_CREATED)
async def register_citizen(payload: CitizenRegistrationRequest, db: Session = Depends(get_db)):
    from .models import CitizenAccount

    if db.query(CitizenAccount).filter(func.lower(CitizenAccount.email) == payload.email.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='An account with this email already exists.')

    configured_id, _ = _account_config('citizen')
    citizen_id = ''
    while not citizen_id or citizen_id == configured_id or db.query(CitizenAccount).filter_by(citizen_id=citizen_id).first():
        citizen_id = f'CIT-{secrets.token_hex(4).upper()}'

    account = CitizenAccount(
        citizen_id=citizen_id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    db.add(account)
    try:
        db.commit()
        db.refresh(account)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='An account with this email already exists.')
    return {'detail': 'Registration successful.', 'citizen_id': account.citizen_id}


@router.post('/admin/login')
async def admin_login(payload: PortalLoginRequest, request: Request, response: Response):
    return _login('admin', payload, request, response)


@router.post('/worker/login')
async def worker_login(
    payload: PortalLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from .models import WorkerAccount

    worker_id = payload.account_id.strip()
    _raise_if_known_wrong_portal('worker', worker_id)
    worker = db.query(WorkerAccount).filter(func.lower(WorkerAccount.worker_id) == worker_id.lower()).first()
    if not worker or not verify_password(payload.password, worker.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid worker ID or password.')
    if worker.account_status != 'active':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='This worker account is inactive.')
    return _new_session(response, request, PortalIdentity(role='worker', account_id=worker.worker_id))


async def get_current_user(request: Request) -> PortalIdentity:
    token = None
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get(SESSION_COOKIE)

    if token:
        identity = verify_token(token)
        if identity:
            return identity
        session = _sessions.get(token)
        if session and session.expires_at > time.time():
            return session.identity

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Please sign in to continue.')


def require_roles(*roles: str) -> Callable:
    allowed = frozenset(roles)

    async def _require_role(identity: PortalIdentity = Depends(get_current_user)) -> PortalIdentity:
        if identity.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='This portal account does not have access to this resource.')
        return identity

    return _require_role


@router.get('/me')
async def get_session(identity: PortalIdentity = Depends(get_current_user)):
    return {'role': identity.role, 'account_id': identity.account_id}


@router.post('/logout')
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _sessions.pop(token, None)
    response.delete_cookie(
        key=SESSION_COOKIE,
        path='/api',
        httponly=True,
        secure=request.url.scheme == 'https',
        samesite='lax',
    )
    return {'detail': 'Signed out.'}
