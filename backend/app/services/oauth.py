import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import allowed_redirect, user_passphrases
from app.models import OAuthClient, OAuthCode, OAuthToken, User

ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)
CODE_TTL = timedelta(minutes=5)


class OAuthError(Exception):
    """Carries an RFC 6749 error code, e.g. invalid_grant."""

    def __init__(self, error: str, description: str = ""):
        super().__init__(description)
        self.error = error
        self.description = description


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ---- dynamic client registration
def register_client(session, redirect_uris, client_name=None) -> OAuthClient:
    if (not isinstance(redirect_uris, list) or not redirect_uris
            or not all(isinstance(u, str) for u in redirect_uris)):
        raise OAuthError("invalid_redirect_uri", "redirect_uris must be a non-empty list")
    for uri in redirect_uris:
        if not allowed_redirect(uri):
            raise OAuthError("invalid_redirect_uri", f"redirect URI not allowed: {uri}")
    client = OAuthClient(client_id=secrets.token_urlsafe(16),
                         client_name=(client_name or "")[:200] or None,
                         redirect_uris=redirect_uris)
    session.add(client)
    session.commit()
    return client


# ---- login (who is the person behind this Claude account?)
def verify_login(session, email: str, passphrase: str) -> User | None:
    expected = user_passphrases().get(email.strip().lower())
    # compare even when the email is unknown, so timing doesn't reveal valid emails
    ok = hmac.compare_digest((expected or "x").encode(), passphrase.encode())
    if expected is None or not ok:
        return None
    return session.scalar(select(User).where(User.email == email.strip().lower()))


# ---- codes and tokens
def create_code(session, client_id, user_id, redirect_uri, code_challenge) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(OAuthCode(code_hash=_hash(raw), client_id=client_id, user_id=user_id,
                          redirect_uri=redirect_uri, code_challenge=code_challenge,
                          expires_at=_now() + CODE_TTL))
    session.commit()
    return raw


def _issue_tokens(session, client_id: str, user_id: int) -> dict:
    now = _now()
    session.execute(delete(OAuthToken).where(OAuthToken.expires_at < now))  # tidy up
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add_all([
        OAuthToken(token_hash=_hash(access), kind="access", client_id=client_id,
                   user_id=user_id, expires_at=now + ACCESS_TTL),
        OAuthToken(token_hash=_hash(refresh), kind="refresh", client_id=client_id,
                   user_id=user_id, expires_at=now + REFRESH_TTL),
    ])
    return {"access_token": access, "token_type": "Bearer",
            "expires_in": int(ACCESS_TTL.total_seconds()), "refresh_token": refresh}


def exchange_code(session, client_id, code, redirect_uri, code_verifier) -> dict:
    # Atomic delete-and-return: a code works exactly once, even under a race.
    row = session.execute(
        delete(OAuthCode).where(OAuthCode.code_hash == _hash(code))
        .returning(OAuthCode)).scalar_one_or_none()
    session.commit()
    if row is None:
        raise OAuthError("invalid_grant", "unknown or already used code")
    if (row.expires_at < _now() or row.client_id != client_id
            or row.redirect_uri != redirect_uri):
        raise OAuthError("invalid_grant", "code expired or does not match this request")
    if not hmac.compare_digest(_s256(code_verifier), row.code_challenge):
        raise OAuthError("invalid_grant", "PKCE verification failed")
    result = _issue_tokens(session, client_id, row.user_id)
    session.commit()
    return result


def refresh_tokens(session, client_id, refresh_token) -> dict:
    row = session.execute(
        delete(OAuthToken).where(OAuthToken.token_hash == _hash(refresh_token),
                                 OAuthToken.kind == "refresh")
        .returning(OAuthToken)).scalar_one_or_none()
    session.commit()
    if row is None or row.client_id != client_id or row.expires_at < _now():
        raise OAuthError("invalid_grant", "invalid or expired refresh token")
    result = _issue_tokens(session, client_id, row.user_id)   # rotation: old one is gone
    session.commit()
    return result


def user_for_access_token(session, token: str) -> int | None:
    row = session.get(OAuthToken, _hash(token))
    if row is not None and row.kind == "access" and row.expires_at > _now():
        return row.user_id
    return None

"""
PKCE (_s256): the client sends a hash first and proves it knows the original secret later. A stolen login code is then useless on its own.
Atomic delete on use: a code can’t be replayed, even by two simultaneous requests.
Refresh rotation: every refresh invalidates the old refresh token, so a leaked one has a short life.
verify_login: this is where “which person is this Claude account” gets decided.
"""