import json
from datetime import datetime

import pytest

from ticket_triage.coordinator import log


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "triage.jsonl"
    monkeypatch.setenv("TICKET_TRIAGE_LOG_PATH", str(path))
    return path


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_log_writes_json_line_with_event_and_fields(log_path):
    log("received", ticket="hello", domain="billing")

    lines = read_lines(log_path)
    assert len(lines) == 1
    assert lines[0]["event"] == "received"
    assert lines[0]["ticket"] == "hello"
    assert lines[0]["domain"] == "billing"


def test_log_appends_multiple_calls_as_separate_lines(log_path):
    log("received", ticket="one")
    log("classified", domain="billing")

    lines = read_lines(log_path)
    assert len(lines) == 2
    assert lines[0]["event"] == "received"
    assert lines[1]["event"] == "classified"


def test_log_auto_adds_iso_utc_timestamp(log_path):
    log("received", ticket="hello")

    lines = read_lines(log_path)
    timestamp = lines[0]["timestamp"]
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_log_defaults_to_project_relative_path_when_env_unset(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("TICKET_TRIAGE_LOG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    log("received", ticket="hello")

    default_path = tmp_path / "ticket_triage.log.jsonl"
    assert default_path.exists()
    lines = read_lines(default_path)
    assert lines[0]["event"] == "received"
