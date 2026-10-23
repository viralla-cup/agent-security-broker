"""Release only pytest-owned per-case files inside the bounded test tmpfs."""

import re
import shutil

import pytest


@pytest.fixture
def tmp_path(tmp_path_factory, request):
    # Durable-journal tests must not inherit temporary evidence from hundreds of
    # already completed tests. Production Docker resource limits stay unchanged.
    base = tmp_path_factory.getbasetemp().resolve()
    path = tmp_path_factory.mktemp(re.sub(r'[^A-Za-z0-9_-]', '_', request.node.name)[:40])
    yield path
    if path.exists():
        target = path.resolve()
        assert target != base and target.is_relative_to(base)
        shutil.rmtree(target)
