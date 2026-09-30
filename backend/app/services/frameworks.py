from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Framework, FrameworkRequirement, FrameworkVersion
from app.schemas.frameworks import FrameworkSummary, FrameworkVersionSummary


def list_frameworks(session: Session) -> list[FrameworkSummary]:
    frameworks = list(session.scalars(select(Framework).order_by(Framework.name)))
    result: list[FrameworkSummary] = []
    for framework in frameworks:
        version = session.scalar(
            select(FrameworkVersion)
            .where(
                FrameworkVersion.framework_id == framework.id,
                FrameworkVersion.is_active.is_(True),
            )
            .order_by(FrameworkVersion.imported_at.desc())
        )
        active_version = None
        if version is not None:
            requirement_count = session.scalar(
                select(func.count())
                .select_from(FrameworkRequirement)
                .where(FrameworkRequirement.framework_version_id == version.id)
            )
            active_version = FrameworkVersionSummary(
                id=version.id,
                version=version.version,
                requirement_count=requirement_count or 0,
            )
        result.append(
            FrameworkSummary(
                id=framework.id,
                slug=framework.slug,
                name=framework.name,
                description=framework.description,
                active_version=active_version,
            )
        )
    return result
