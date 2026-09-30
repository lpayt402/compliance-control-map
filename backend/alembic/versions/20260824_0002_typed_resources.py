"""typed requirement and control text resources

Revision ID: 20260824_0002
Revises: 20260821_0001
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0002"
down_revision: str | None = "20260821_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("requirement_notes") as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(length=16), nullable=False, server_default="NOTE")
        )
        batch_op.add_column(
            sa.Column("title", sa.String(length=240), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("contact_user_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_check_constraint(
            "requirement_note_kind", "kind IN ('NOTE', 'PLAYBOOK', 'CONTACT')"
        )
        batch_op.create_foreign_key(
            "fk_requirement_notes_contact_user_id_users",
            "users",
            ["contact_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "control_notes",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("contact_user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('NOTE', 'PLAYBOOK', 'CONTACT')", name="control_note_kind"
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_control_notes_author_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["contact_user_id"],
            ["users.id"],
            name=op.f("fk_control_notes_contact_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["organizational_controls.id"],
            name=op.f("fk_control_notes_control_id_organizational_controls"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_control_notes_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_notes")),
    )
    with op.batch_alter_table("control_notes") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_control_notes_workspace_id"), ["workspace_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_control_notes_control_id"), ["control_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("control_notes") as batch_op:
        batch_op.drop_index(batch_op.f("ix_control_notes_control_id"))
        batch_op.drop_index(batch_op.f("ix_control_notes_workspace_id"))
    op.drop_table("control_notes")
    with op.batch_alter_table("requirement_notes") as batch_op:
        batch_op.drop_constraint(
            "fk_requirement_notes_contact_user_id_users", type_="foreignkey"
        )
        batch_op.drop_constraint("requirement_note_kind", type_="check")
        batch_op.drop_column("revision")
        batch_op.drop_column("contact_user_id")
        batch_op.drop_column("title")
        batch_op.drop_column("kind")
