from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import APIModel


class ControlCreate(APIModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=20_000)
    status_code: str = Field(default="PLANNED", min_length=1, max_length=40)
    owner_user_id: UUID | None = None
    implementation_notes: str = Field(default="", max_length=100_000)
    tags: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_tags(self) -> Self:
        if any(not tag.strip() or len(tag.strip()) > 80 for tag in self.tags):
            raise ValueError("Tags must contain 1 to 80 visible characters.")
        return self


class ControlUpdate(APIModel):
    revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20_000)
    status_code: str | None = Field(default=None, min_length=1, max_length=40)
    owner_user_id: UUID | None = None
    implementation_notes: str | None = Field(default=None, max_length=100_000)
    tags: list[str] | None = Field(default=None, max_length=30)


class RequirementControlCreate(APIModel):
    control_id: UUID
    coverage: str = Field(default="SUPPORTING", pattern="^(PRIMARY|SUPPORTING|LIMITED)$")
    rationale: str = Field(default="", max_length=20_000)
