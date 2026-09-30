from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


ROLE_RANK = {Role.VIEWER: 10, Role.EDITOR: 20, Role.ADMIN: 30}


@dataclass(frozen=True)
class Principal:
    workspace_id: UUID
    user_id: UUID | None
    role: Role
    display_name: str
    auth_disabled: bool = False

    def has_role(self, minimum: Role) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum]
