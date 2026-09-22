import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel


def _serialize_log_value(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON serializable"
    )


def write_audit_event(event: str, **fields) -> None:
    path = os.environ.get("TICKET_TRIAGE_LOG_PATH", "ticket_triage.log.jsonl")
    entry = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    with open(path, "a") as output_file:
        output_file.write(json.dumps(entry, default=_serialize_log_value) + "\n")
