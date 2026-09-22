import json
from datetime import datetime

import pytest

from ticket_triage.coordinator import write_audit_event
from ticket_triage.schemas import Classification


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "triage.jsonl"
    monkeypatch.setenv("TICKET_TRIAGE_LOG_PATH", str(path))
    return path


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_write_audit_event_writes_json_line_with_event_and_fields(log_path):
    write_audit_event("received", ticket="hello", domain="billing")

    lines = read_lines(log_path)
    assert len(lines) == 1
    assert lines[0]["event"] == "received"
    assert lines[0]["ticket"] == "hello"
    assert lines[0]["domain"] == "billing"


def test_write_audit_event_appends_multiple_calls_as_separate_lines(log_path):
    write_audit_event("received", ticket="one")
    write_audit_event("classified", domain="billing")

    lines = read_lines(log_path)
    assert len(lines) == 2
    assert lines[0]["event"] == "received"
    assert lines[1]["event"] == "classified"


def test_write_audit_event_auto_adds_iso_utc_timestamp(log_path):
    write_audit_event("received", ticket="hello")

    lines = read_lines(log_path)
    timestamp = lines[0]["timestamp"]
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_write_audit_event_defaults_to_project_relative_path_when_env_unset(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("TICKET_TRIAGE_LOG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    write_audit_event("received", ticket="hello")

    default_path = tmp_path / "ticket_triage.log.jsonl"
    assert default_path.exists()
    lines = read_lines(default_path)
    assert lines[0]["event"] == "received"


def test_write_audit_event_serializes_pydantic_model_field_as_nested_dict(log_path):
    classification = Classification(
        domain="billing", confidence=0.9, reasoning="clear signal"
    )

    write_audit_event("escalated", classification=classification)

    lines = read_lines(log_path)
    assert lines[0]["classification"] == {
        "domain": "billing",
        "confidence": 0.9,
        "reasoning": "clear signal",
    }
