from uuid import UUID

from pydantic import BaseModel


class FrameworkVersionSummary(BaseModel):
    id: UUID
    version: str
    requirement_count: int


class FrameworkSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    active_version: FrameworkVersionSummary | None
