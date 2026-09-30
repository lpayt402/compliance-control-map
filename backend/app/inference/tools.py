import re
from collections.abc import Awaitable, Callable, Mapping

from app.core.database import DatabaseManager
from app.core.permissions import Principal, Role
from app.inference.context import ContextError, build_context_preview
from app.inference.models import RecordReference

ToolHandler = Callable[[str], Awaitable[str]]
_SOURCE_REF = re.compile(r"^(requirement|control):[A-Za-z0-9._:-]{1,160}$")


class ToolAuthorizationError(PermissionError):
    pass


class ToolLimitError(RuntimeError):
    pass


class ReadOnlyToolRegistry:
    """Run-scoped tools that repeat workspace authorization on every database read."""

    def __init__(
        self,
        database: DatabaseManager,
        principal: Principal,
        *,
        approved_references: Mapping[str, RecordReference],
        allowed_tool_ids: set[str],
        max_calls: int,
        max_result_chars: int,
    ) -> None:
        self._database = database
        self._principal = principal
        self._approved_references = dict(approved_references)
        self._allowed_tool_ids = allowed_tool_ids
        self._max_calls = max_calls
        self._max_result_chars = max_result_chars
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def _authorize(self, tool_id: str, source_ref: str, kind: str) -> RecordReference:
        if tool_id not in self._allowed_tool_ids:
            raise ToolAuthorizationError("Tool is not declared for this run.")
        if not self._principal.has_role(Role.VIEWER) or not _SOURCE_REF.fullmatch(source_ref):
            raise ToolAuthorizationError("Tool request is not authorized.")
        selected = self._approved_references.get(source_ref)
        if selected is None or selected.kind != kind:
            raise ToolAuthorizationError("Tool source is outside the approved run scope.")
        return selected

    def _consume(self) -> None:
        if self._calls >= self._max_calls:
            raise ToolLimitError("The run reached its read-only tool-call limit.")
        self._calls += 1

    async def _context(
        self,
        tool_id: str,
        source_ref: str,
        kind: str,
        *,
        include_text_resources: bool,
        include_mapped_resources: bool,
    ) -> str:
        selected = self._authorize(tool_id, source_ref, kind)
        self._consume()
        try:
            with self._database.session() as db:
                preview = build_context_preview(
                    db,
                    self._principal.workspace_id,
                    record_references=(selected,),
                    instruction=f"Read-only tool result for {tool_id}.",
                    include_text_resources=include_text_resources,
                    include_mapped_resources=include_mapped_resources,
                    max_chars=self._max_result_chars,
                )
        except ContextError as exc:
            raise ToolAuthorizationError("Selected source is no longer available.") from exc
        return preview.text

    async def get_requirement_context(self, source_ref: str) -> str:
        """Return the authorized selected requirement fields."""

        return await self._context(
            "get_requirement_context",
            source_ref,
            "requirement",
            include_text_resources=False,
            include_mapped_resources=False,
        )

    async def get_control_context(self, source_ref: str) -> str:
        """Return the authorized selected control fields."""

        return await self._context(
            "get_control_context",
            source_ref,
            "control",
            include_text_resources=False,
            include_mapped_resources=False,
        )

    async def list_mapped_controls(self, source_ref: str) -> str:
        """List mapped controls for the authorized selected requirement."""

        return await self._context(
            "list_mapped_controls",
            source_ref,
            "requirement",
            include_text_resources=False,
            include_mapped_resources=True,
        )

    async def list_mapped_requirements(self, source_ref: str) -> str:
        """List mapped requirements for the authorized selected control."""

        return await self._context(
            "list_mapped_requirements",
            source_ref,
            "control",
            include_text_resources=False,
            include_mapped_resources=True,
        )

    async def list_text_resources(self, source_ref: str) -> str:
        """List typed notes, playbooks, and contacts for the authorized source."""

        kind = source_ref.split(":", 1)[0]
        return await self._context(
            "list_text_resources",
            source_ref,
            kind,
            include_text_resources=True,
            include_mapped_resources=False,
        )

    async def list_library_metadata(self, source_ref: str) -> str:
        """List mapped document and evidence metadata without attachment bytes."""

        kind = source_ref.split(":", 1)[0]
        return await self._context(
            "list_library_metadata",
            source_ref,
            kind,
            include_text_resources=False,
            include_mapped_resources=True,
        )

    async def list_crosswalk_metadata(self, source_ref: str) -> str:
        """List existing crosswalk metadata for the authorized requirement."""

        return await self._context(
            "list_crosswalk_metadata",
            source_ref,
            "requirement",
            include_text_resources=False,
            include_mapped_resources=True,
        )

    def handlers(self) -> dict[str, ToolHandler]:
        available: dict[str, ToolHandler] = {
            "get_requirement_context": self.get_requirement_context,
            "get_control_context": self.get_control_context,
            "list_mapped_controls": self.list_mapped_controls,
            "list_mapped_requirements": self.list_mapped_requirements,
            "list_text_resources": self.list_text_resources,
            "list_library_metadata": self.list_library_metadata,
            "list_crosswalk_metadata": self.list_crosswalk_metadata,
        }
        return {
            tool_id: handler
            for tool_id, handler in available.items()
            if tool_id in self._allowed_tool_ids
        }
