from uuid import UUID

import pytest

from app.inference.proposals import parse_structured_proposal
from app.services.inference_runs import RunLimiter

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "source_references"],
    "properties": {
        "summary": {"type": "string"},
        "source_references": {"type": "array", "items": {"type": "string"}},
    },
}


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"summary":"missing refs"}',
        '{"summary":"bad source","source_references":["requirement:FORGED"]}',
        '{"summary":"extra","source_references":["requirement:CC8.1"],"status":"READY"}',
    ],
)
def test_malformed_or_unsourced_structured_output_is_rejected(text: str) -> None:
    assert (
        parse_structured_proposal(
            text,
            SCHEMA,
            allowed_source_references={"requirement:CC8.1"},
        )
        is None
    )


@pytest.mark.anyio
async def test_limiter_enforces_one_run_per_actor_and_workspace_ceiling() -> None:
    limiter = RunLimiter(max_workspace_runs=2)
    workspace = UUID(int=1)
    first_user = UUID(int=2)
    second_user = UUID(int=3)
    third_user = UUID(int=4)

    assert await limiter.acquire(workspace, first_user) is True
    assert await limiter.acquire(workspace, first_user) is False
    assert await limiter.acquire(workspace, second_user) is True
    assert await limiter.acquire(workspace, third_user) is False

    await limiter.release(workspace, first_user)
    assert await limiter.acquire(workspace, third_user) is True
