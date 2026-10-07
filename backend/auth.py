"""Small single-process authentication for the CityLens hackathon MVP.

Portal IDs and PBKDF2 hashes are read from backend/.env (or the process
environment). Sessions are opaque, revocable server-side tokens in HttpOnly
SameSite cookies; run one backend worker for this in-memory session store.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import hmac
import os
import re
import secrets
import time
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
try:
    SESSION_TTL_SECONDS = min(max(int(os.getenv('CITYLENS_SESSION_TTL_SECONDS', '28800')), 300), 86_400)
except ValueError:
    SESSION_TTL_SECONDS = 28_800


@dataclass(frozen=True)
class PortalIdentity:
    role: str
    account_id: str


@dataclass(frozen=True)
class _Session:
    identity: PortalIdentity
    expires_at: float


_sessions: dict[str, _Session] = {}


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
    prefix = 'CITYLENS_ADMIN' if role == 'admin' else 'CITYLENS_CITIZEN'
    return os.getenv(f'{prefix}_ID', '').strip(), os.getenv(f'{prefix}_PASSWORD_HASH', '').strip()


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
    for token, session in list(_sessions.items()):
        if session.expires_at <= now:
            _sessions.pop(token, None)
    token = secrets.token_urlsafe(32)
    _sessions[token] = _Session(identity=identity, expires_at=now + SESSION_TTL_SECONDS)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        path='/api',
        httponly=True,
        secure=request.url.scheme == 'https',
        samesite='strict',
    )
    return {'role': identity.role, 'account_id': identity.account_id}


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
    # Keep the existing backend-configured CIT-001 demo account working.
    return _login('citizen', payload, request, response)


@router.post('/citizen/register', status_code=status.HTTP_201_CREATED)
async def register_citizen(payload: CitizenRegistrationRequest, db: Session = Depends(get_db)):
    from .models import CitizenAccount

    if db.query(CitizenAccount).filter(CitizenAccount.email == payload.email).first():
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

    worker_id = payload.account_id.strip().upper()
    _raise_if_known_wrong_portal('worker', worker_id)
    worker = db.query(WorkerAccount).filter_by(worker_id=worker_id).first()
    if not worker or not verify_password(payload.password, worker.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid worker ID or password.')
    if worker.account_status != 'active':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='This worker account is inactive.')
    return _new_session(response, request, PortalIdentity(role='worker', account_id=worker.worker_id))


async def get_current_user(request: Request) -> PortalIdentity:
    token = request.cookies.get(SESSION_COOKIE)
    session = _sessions.get(token or '')
    if not session or session.expires_at <= time.time():
        if token:
            _sessions.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Please sign in to continue.')
    return session.identity


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
        samesite='strict',
    )
    return {'detail': 'Signed out.'}
