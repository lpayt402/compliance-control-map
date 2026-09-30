from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import APIModel


class AssessmentUpdate(APIModel):
    revision: int = Field(ge=1)
    status_code: str | None = Field(default=None, min_length=1, max_length=40)
    applicability: Literal["UNDETERMINED", "APPLICABLE", "NOT_APPLICABLE"] | None = None
    owner_user_id: UUID | None = None
    assignee_user_id: UUID | None = None
    due_date: date | None = None
    implementation_notes: str | None = Field(default=None, max_length=100_000)
    tags: list[str] | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def validate_tags(self) -> Self:
        if self.tags is not None and any(
            not tag.strip() or len(tag.strip()) > 80 for tag in self.tags
        ):
            raise ValueError("Tags must contain 1 to 80 visible characters.")
        return self


class NotePayload(APIModel):
    body: str = Field(min_length=1, max_length=10_000)
