from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.database import DatabaseManager
from app.models import Document, FrameworkRequirement, OrganizationalControl, User, Workspace
from app.services.assessments import AssessmentService
from app.services.controls import create_control, link_control
from app.services.documents import create_document
from app.services.evidence import create_evidence
from app.storage import FileStorage

DEMO_DOCUMENT_NAME = "DEMO — Access Control Policy"
DEMO_EVIDENCE_NAME = "DEMO — Quarterly Access Review"


def load_demo_data(
    manager: DatabaseManager,
    storage: FileStorage,
    demo_path: Path,
) -> bool:
    with manager.session() as session:
        existing = session.scalar(select(Document.id).where(Document.name == DEMO_DOCUMENT_NAME))
        if existing is not None:
            return False
        workspace = session.scalar(select(Workspace).where(Workspace.slug == "default"))
        if workspace is None:
            raise RuntimeError("Import a framework pack before loading demo data.")
        owner = session.scalar(
            select(User).where(
                User.workspace_id == workspace.id,
                User.normalized_email == "demo.owner@local.invalid",
            )
        )
        if owner is None:
            owner = User(
                workspace_id=workspace.id,
                email="demo.owner@local.invalid",
                normalized_email="demo.owner@local.invalid",
                display_name="Demo Control Owner",
                role="EDITOR",
                can_login=False,
            )
            session.add(owner)
            session.flush()
        requirements = {
            requirement.external_id: requirement
            for requirement in session.scalars(
                select(FrameworkRequirement).where(
                    FrameworkRequirement.external_id.in_(
                        ["CC6.1", "CC6.2", "CC6.3", "CC7.1", "CC8.1"]
                    )
                )
            )
        }
        service = AssessmentService(session, workspace.id, owner.id)
        demo_states = {
            "CC6.1": ("READY", None, "Access is reviewed quarterly."),
            "CC6.2": ("PARTIAL", date.today() + timedelta(days=30), "MFA rollout remains."),
            "CC7.1": ("GAP", date.today() - timedelta(days=7), "Alert triage is not documented."),
            "CC8.1": (
                "IN_PROGRESS",
                date.today() + timedelta(days=14),
                "Change sampling is being formalized.",
            ),
        }
        for external_id, (status, due_date, notes) in demo_states.items():
            assessment = service._assessment(requirements[external_id].id)
            service.update(
                requirements[external_id].id,
                {
                    "status_code": status,
                    "applicability": "APPLICABLE",
                    "owner_user_id": owner.id,
                    "due_date": due_date,
                    "implementation_notes": notes,
                    "tags": ["demo"],
                },
                expected_revision=assessment.revision,
            )
        control = session.scalar(
            select(OrganizationalControl).where(
                OrganizationalControl.workspace_id == workspace.id,
                OrganizationalControl.code == "AC-01",
            )
        )
        if control is None:
            control = create_control(
                session,
                workspace.id,
                owner.id,
                {
                    "code": "AC-01",
                    "name": "Quarterly access review",
                    "description": "Review access and resolve exceptions each quarter.",
                    "status_code": "OPERATING",
                    "owner_user_id": owner.id,
                    "implementation_notes": "Demo control; replace with your operating process.",
                    "tags": ["demo", "access"],
                },
            )
        for external_id in ("CC6.1", "CC6.2", "CC6.3"):
            link_control(
                session,
                workspace.id,
                owner.id,
                requirements[external_id].id,
                control.id,
                "SUPPORTING",
                "Demo access-review coverage.",
            )
        policy_path = demo_path / "demo-access-policy.txt"
        with policy_path.open("rb") as stream:
            create_document(
                session,
                storage,
                workspace_id=workspace.id,
                actor_user_id=owner.id,
                name=DEMO_DOCUMENT_NAME,
                document_type="POLICY",
                description="Clearly labeled placeholder policy for the demo workspace.",
                version="DEMO",
                effective_date=None,
                owner_user_id=owner.id,
                notes="Replace before real use.",
                requirement_ids=[requirements["CC6.1"].id, requirements["CC6.2"].id],
                control_ids=[control.id],
                filename=policy_path.name,
                declared_media_type="text/plain",
                stream=stream,
                limit=1024 * 1024,
                allowed_extensions={".txt"},
            )
        evidence_path = demo_path / "demo-quarterly-access-review.txt"
        with evidence_path.open("rb") as stream:
            create_evidence(
                session,
                storage,
                workspace_id=workspace.id,
                actor_user_id=owner.id,
                name=DEMO_EVIDENCE_NAME,
                description="Clearly labeled placeholder evidence for the demo workspace.",
                evidence_date=date.today(),
                owner_user_id=owner.id,
                notes="Not real audit evidence.",
                requirement_ids=[requirements["CC6.1"].id],
                control_ids=[control.id],
                filename=evidence_path.name,
                declared_media_type="text/plain",
                stream=stream,
                limit=1024 * 1024,
                allowed_extensions={".txt"},
            )
    return True
