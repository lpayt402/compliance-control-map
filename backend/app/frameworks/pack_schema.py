import hashlib
import json
from pathlib import Path
from typing import Self

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameworkDefinition(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=120)
    description: str
    source_uri: str
    verified_on: str
    published_at: str | None = None
    disclaimer: str


class DomainDefinition(StrictModel):
    external_id: str
    name: str
    description: str = ""
    parent_id: str | None = None
    sort_order: int = 0


class RequirementDefinition(StrictModel):
    external_id: str
    domain_id: str
    parent_id: str | None = None
    title: str
    summary: str
    guidance: str = ""
    source_reference: str = ""
    sort_order: int = 0


class FrameworkPack(StrictModel):
    framework: FrameworkDefinition
    domains: list[DomainDefinition]
    requirements: list[RequirementDefinition]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        domain_ids = [item.external_id for item in self.domains]
        requirement_ids = [item.external_id for item in self.requirements]
        if len(domain_ids) != len(set(domain_ids)):
            raise ValueError("domain identifiers must be unique")
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirement identifiers must be unique")

        known_domains = set(domain_ids)
        known_requirements = set(requirement_ids)
        for domain in self.domains:
            if domain.parent_id is not None and domain.parent_id not in known_domains:
                raise ValueError(f"unknown parent domain: {domain.parent_id}")
            if domain.parent_id == domain.external_id:
                raise ValueError(f"domain cannot parent itself: {domain.external_id}")
        for requirement in self.requirements:
            if requirement.domain_id not in known_domains:
                raise ValueError(f"unknown requirement domain: {requirement.domain_id}")
            if (
                requirement.parent_id is not None
                and requirement.parent_id not in known_requirements
            ):
                raise ValueError(f"unknown parent requirement: {requirement.parent_id}")
            if requirement.parent_id == requirement.external_id:
                raise ValueError(f"requirement cannot parent itself: {requirement.external_id}")
        return self

    def canonical_hash(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


def _load_yaml(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    if not isinstance(content, dict):
        raise ValueError(f"{path.name} must contain a YAML object")
    return content


def load_pack(path: Path) -> FrameworkPack:
    manifest = _load_yaml(path / "manifest.yaml")
    domains = _load_yaml(path / "domains.yaml")
    requirements = _load_yaml(path / "requirements.yaml")
    return FrameworkPack.model_validate(
        {
            "framework": manifest.get("framework"),
            "domains": domains.get("domains"),
            "requirements": requirements.get("requirements"),
        }
    )
