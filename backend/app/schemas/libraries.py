from uuid import UUID

from pydantic import Field

from app.schemas.base import APIModel


class RequirementMappingBatch(APIModel):
    requirement_ids: list[UUID] = Field(min_length=1, max_length=200)
    rationale: str = Field(default="", max_length=20_000)


class ControlMappingBatch(APIModel):
    control_ids: list[UUID] = Field(min_length=1, max_length=200)


class DocumentLinkBatch(APIModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=200)
    rationale: str = Field(default="", max_length=20_000)


class EvidenceLinkBatch(APIModel):
    evidence_ids: list[UUID] = Field(min_length=1, max_length=200)
    rationale: str = Field(default="", max_length=20_000)
