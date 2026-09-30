from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.permissions import Principal, Role
from app.inference.models import RecordReference
from app.inference.tools import ReadOnlyToolRegistry, ToolAuthorizationError, ToolLimitError
from app.models import FrameworkRequirement, Workspace


@pytest.mark.anyio
async def test_read_only_tool_reauthorizes_scope_and_bounds_results(
    inference_client,
) -> None:
    _client, manager = inference_client
    with manager.session() as session:
        workspace_id = session.scalar(select(Workspace.id).where(Workspace.slug == "default"))
        requirement = session.scalar(
            select(FrameworkRequirement).where(FrameworkRequirement.external_id == "CC8.1")
        )
    assert workspace_id is not None and requirement is not None
    selected = RecordReference(kind="requirement", record_id=requirement.id)
    registry = ReadOnlyToolRegistry(
        manager,
        Principal(
            workspace_id=workspace_id,
            user_id=None,
            role=Role.EDITOR,
            display_name="Test editor",
        ),
        approved_references={"requirement:CC8.1": selected},
        allowed_tool_ids={"get_requirement_context"},
        max_calls=1,
        max_result_chars=800,
    )

    result = await registry.get_requirement_context("requirement:CC8.1")

    assert "requirement:CC8.1" in result
    assert len(result) <= 800
    with pytest.raises(ToolAuthorizationError):
        await registry.get_requirement_context("requirement:CC7.1")
    with pytest.raises(ToolLimitError):
        await registry.get_requirement_context("requirement:CC8.1")


@pytest.mark.anyio
async def test_tool_cannot_use_forged_workspace_or_undeclared_tool(
    inference_client,
) -> None:
    _client, manager = inference_client
    foreign_principal = Principal(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=Role.EDITOR,
        display_name="Foreign editor",
    )
    registry = ReadOnlyToolRegistry(
        manager,
        foreign_principal,
        approved_references={
            "requirement:CC8.1": RecordReference(kind="requirement", record_id=uuid4())
        },
        allowed_tool_ids=set(),
        max_calls=8,
        max_result_chars=1_000,
    )

    with pytest.raises(ToolAuthorizationError):
        await registry.get_requirement_context("requirement:CC8.1")


def test_registry_exposes_only_named_read_only_handlers(inference_client) -> None:
    _client, manager = inference_client
    registry = ReadOnlyToolRegistry(
        manager,
        Principal(
            workspace_id=UUID(int=1),
            user_id=None,
            role=Role.EDITOR,
            display_name="Editor",
        ),
        approved_references={},
        allowed_tool_ids={"get_requirement_context", "shell", "write_control"},
        max_calls=8,
        max_result_chars=1_000,
    )

    assert set(registry.handlers()) == {"get_requirement_context"}
