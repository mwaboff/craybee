import pytest

from backend.orchestration.commands import dispatch
from backend.orchestration.registry import Run


def _run() -> Run:
    return Run(id="r1", prompt="/", conversation_id="c1")


@pytest.mark.parametrize("prompt", ["/", "/  "])
async def test_dispatch_bare_slash_is_not_a_command(prompt):
    assert await dispatch(_run(), prompt) is False
