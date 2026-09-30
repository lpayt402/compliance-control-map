from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.passwords import hash_password, password_needs_rehash, verify_password
from app.core.permissions import Principal, Role
from app.models import User

DUMMY_PASSWORD_HASH = hash_password("this is only a timing equalizer")
LOGIN_WINDOW = timedelta(minutes=10)
LOGIN_FAILURE_LIMIT = 5


def normalize_email(email: str) -> str:
    return email.strip().casefold()


@dataclass
class LoginThrottle:
    failures: dict[str, deque[datetime]] = field(default_factory=lambda: defaultdict(deque))

    def _key(self, source: str, email: str) -> str:
        return f"{source}|{normalize_email(email)}"

    def is_blocked(self, source: str, email: str, now: datetime | None = None) -> bool:
        current_time = now or datetime.now(UTC)
        attempts = self.failures[self._key(source, email)]
        cutoff = current_time - LOGIN_WINDOW
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return len(attempts) >= LOGIN_FAILURE_LIMIT

    def record_failure(self, source: str, email: str, now: datetime | None = None) -> None:
        self.failures[self._key(source, email)].append(now or datetime.now(UTC))

    def clear(self, source: str, email: str) -> None:
        self.failures.pop(self._key(source, email), None)


def authenticate_password(
    db: OrmSession,
    email: str,
    password: str,
) -> User | None:
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.normalized_email == normalized))
    encoded_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    verified = verify_password(password, encoded_hash)
    if user is None or not verified or user.is_disabled or not user.can_login:
        return None
    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def current_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def require_role(minimum: Role) -> Callable[[CurrentPrincipal], Principal]:
    def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.has_role(minimum):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role.")
        return principal

    return dependency
