from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import APIModel

ResourceKind = Literal["NOTE", "PLAYBOOK", "CONTACT"]


class TextResourceCreate(APIModel):
    kind: ResourceKind = "NOTE"
    title: str = Field(default="", max_length=240)
    body: str = Field(min_length=1, max_length=10_000)
    contact_user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> Self:
        if not self.body.strip():
            raise ValueError("Resource text must contain visible characters.")
        if self.kind != "NOTE" and not self.title.strip():
            raise ValueError("Playbooks and contacts require a title.")
        if self.kind != "CONTACT" and self.contact_user_id is not None:
            raise ValueError("Only contact resources can reference a workspace user.")
        return self


class TextResourceUpdate(APIModel):
    revision: int = Field(ge=1)
    kind: ResourceKind | None = None
    title: str | None = Field(default=None, max_length=240)
    body: str | None = Field(default=None, min_length=1, max_length=10_000)
    contact_user_id: UUID | None = None
