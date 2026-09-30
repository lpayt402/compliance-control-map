from sqlalchemy import select

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.passwords import hash_password
from app.models import User, Workspace


def ensure_bootstrap_admin(manager: DatabaseManager, settings: Settings) -> bool:
    if settings.auth_mode != "local":
        return False
    with manager.session() as session:
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        if workspace is None:
            raise RuntimeError("Framework initialization must run before user bootstrap.")
        existing_admin = session.scalar(
            select(User.id).where(
                User.workspace_id == workspace.id,
                User.role == "ADMIN",
                User.is_disabled.is_(False),
            )
        )
        if existing_admin is not None:
            return False
        email = (settings.bootstrap_admin_email or "").strip().casefold()
        password = (
            settings.bootstrap_admin_password.get_secret_value()
            if settings.bootstrap_admin_password is not None
            else ""
        )
        if not email or not password:
            raise RuntimeError(
                "Fresh team mode needs CCM_BOOTSTRAP_ADMIN_EMAIL and "
                "CCM_BOOTSTRAP_ADMIN_PASSWORD. Existing installations may clear both "
                "after confirming an active Admin can sign in."
            )
        session.add(
            User(
                workspace_id=workspace.id,
                email=email,
                normalized_email=email,
                display_name=settings.bootstrap_admin_display_name,
                password_hash=hash_password(password),
                role="ADMIN",
                can_login=True,
            )
        )
    return True
