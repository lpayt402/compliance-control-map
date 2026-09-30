import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

RecordScope = Literal["requirement", "control", "document_metadata", "evidence_metadata"]


class RegistryError(RuntimeError):
    """Installed inference definitions are invalid and must not be loaded."""


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=120)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1_000)
    enabled: bool
    instructions_file: str = Field(min_length=1, max_length=240, pattern=r"^[^/\\].*\.md$")


class AgentManifest(_Manifest):
    provider_profile_ref: str | None = Field(default=None, max_length=120)
    skills: tuple[str, ...] = Field(max_length=20)
    tools: tuple[str, ...] = Field(max_length=20)
    record_scopes: tuple[RecordScope, ...] = Field(max_length=10)
    human_confirmation: tuple[
        Literal["workspace_write", "file_read", "file_download", "external_transfer", "export"],
        ...,
    ] = Field(max_length=10)
    max_iterations: int = Field(default=4, ge=1, le=25)
    timeout_seconds: int = Field(default=60, ge=1, le=300)


class SkillManifest(_Manifest):
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=40)
    allowed_tools: tuple[str, ...] = Field(max_length=20)
    record_scopes: tuple[RecordScope, ...] = Field(max_length=10)
    writes_workspace: bool
    requires_confirmation: bool
    output_schema_file: str | None = Field(
        default=None,
        max_length=240,
        pattern=r"^[^/\\].*\.json$",
    )


class LoadedAgent(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    manifest: AgentManifest
    instructions: str


class LoadedSkill(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest: SkillManifest
    instructions: str
    output_schema: dict[str, object]


class InferenceRegistry(BaseModel):
    model_config = ConfigDict(frozen=True)

    agents: dict[str, LoadedAgent]
    skills: dict[str, LoadedSkill]


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Invalid installed manifest: {path.name}.") from exc
    if not isinstance(value, dict):
        raise RegistryError(f"Installed manifest must be a JSON object: {path.name}.")
    return value


def _installed_file(directory: Path, relative_name: str) -> Path:
    relative = Path(relative_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise RegistryError("Installed instruction/schema paths must be relative and contained.")
    base = directory.resolve(strict=True)
    cursor = directory
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise RegistryError("Installed instruction/schema paths must not traverse symlinks.")
    try:
        target = (directory / relative).resolve(strict=True)
    except OSError as exc:
        raise RegistryError("Installed instruction/schema file is missing.") from exc
    if not target.is_relative_to(base) or not target.is_file():
        raise RegistryError("Installed instruction/schema path escaped its package.")
    return target


def _load_skills(root: Path) -> dict[str, LoadedSkill]:
    loaded: dict[str, LoadedSkill] = {}
    for manifest_path in sorted(root.glob("*/manifest.json")):
        if manifest_path.parent.is_symlink() or manifest_path.is_symlink():
            raise RegistryError("Installed skill packages must not be symlinks.")
        try:
            manifest = SkillManifest.model_validate(_read_json(manifest_path))
        except ValidationError as exc:
            raise RegistryError(f"Invalid skill manifest in {manifest_path.parent.name}.") from exc
        if manifest.id in loaded:
            raise RegistryError(f"Duplicate skill ID: {manifest.id}.")
        instructions = _installed_file(manifest_path.parent, manifest.instructions_file).read_text(
            encoding="utf-8"
        )
        output_schema: dict[str, object] = {}
        if manifest.output_schema_file:
            output_schema = _read_json(
                _installed_file(manifest_path.parent, manifest.output_schema_file)
            )
            if output_schema.get("type") != "object":
                raise RegistryError(f"Skill {manifest.id} output schema must describe an object.")
        if not manifest.enabled:
            continue
        if manifest.writes_workspace:
            raise RegistryError(f"Skill {manifest.id} requests workspace writes.")
        loaded[manifest.id] = LoadedSkill(
            manifest=manifest,
            instructions=instructions,
            output_schema=output_schema,
        )
    return loaded


def _load_agents(
    root: Path,
    skills: dict[str, LoadedSkill],
    *,
    max_iterations: int,
    timeout_seconds: int,
) -> dict[str, LoadedAgent]:
    loaded: dict[str, LoadedAgent] = {}
    for manifest_path in sorted(root.glob("*/agent.json")):
        if manifest_path.parent.is_symlink() or manifest_path.is_symlink():
            raise RegistryError("Installed agent packages must not be symlinks.")
        try:
            manifest = AgentManifest.model_validate(_read_json(manifest_path))
        except ValidationError as exc:
            raise RegistryError(f"Invalid agent manifest in {manifest_path.parent.name}.") from exc
        if manifest.id in loaded:
            raise RegistryError(f"Duplicate agent ID: {manifest.id}.")
        instructions = _installed_file(manifest_path.parent, manifest.instructions_file).read_text(
            encoding="utf-8"
        )
        if not manifest.enabled:
            continue
        if manifest.max_iterations > max_iterations or manifest.timeout_seconds > timeout_seconds:
            raise RegistryError(f"Agent {manifest.id} exceeds configured run limits.")
        agent_tools = set(manifest.tools)
        agent_scopes = set(manifest.record_scopes)
        for skill_id in manifest.skills:
            skill = skills.get(skill_id)
            if skill is None:
                raise RegistryError(f"Agent {manifest.id} references unavailable skill {skill_id}.")
            if not set(skill.manifest.allowed_tools).issubset(agent_tools):
                raise RegistryError(f"Skill {skill_id} requests an undeclared tool.")
            if not set(skill.manifest.record_scopes).issubset(agent_scopes):
                raise RegistryError(f"Skill {skill_id} exceeds the agent record scope.")
        loaded[manifest.id] = LoadedAgent(manifest=manifest, instructions=instructions)
    return loaded


def load_registry(
    agent_root: Path,
    skill_root: Path,
    *,
    max_iterations: int,
    timeout_seconds: int,
) -> InferenceRegistry:
    try:
        agent_root.resolve(strict=True)
        skill_root.resolve(strict=True)
    except OSError as exc:
        raise RegistryError("Configured inference package roots are unavailable.") from exc
    skills = _load_skills(skill_root)
    agents = _load_agents(
        agent_root,
        skills,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
    )
    return InferenceRegistry(agents=agents, skills=skills)
