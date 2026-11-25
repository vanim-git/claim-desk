import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _action_log_in_tmp(tmp_path, monkeypatch):
    """No test may write to the real action log in data/."""
    monkeypatch.setenv("ACTION_LOG", str(tmp_path / "action_log.jsonl"))
