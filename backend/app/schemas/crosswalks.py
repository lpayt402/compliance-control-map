from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import APIModel

RelationshipType = Literal["EQUIVALENT", "STRONG_OVERLAP", "PARTIAL_OVERLAP", "RELATED"]


class RequirementMappingCreate(APIModel):
    source_requirement_id: UUID
    target_requirement_id: UUID
    relationship_type: RelationshipType
    confidence: int | None = Field(default=None, ge=0, le=100)
    mapping_source: str = Field(min_length=1, max_length=400)
    notes: str = Field(default="", max_length=20_000)

    @model_validator(mode="after")
    def reject_self_link(self) -> Self:
        if self.source_requirement_id == self.target_requirement_id:
            raise ValueError("A requirement cannot map to itself.")
        return self
