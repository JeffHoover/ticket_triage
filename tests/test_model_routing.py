from types import SimpleNamespace
from unittest.mock import MagicMock

from ticket_triage.coordinator import classify
from ticket_triage.subagents import CLASSIFIER_MODEL, SUBAGENT_MODEL


def _classification_api_response(domain: str, confidence: float, reasoning: str):
    import json
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text=json.dumps(
                    {"domain": domain, "confidence": confidence, "reasoning": reasoning}
                ),
            )
        ],
        stop_reason="end_turn",
    )


def test_classify_uses_classifier_model(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _classification_api_response(
        domain="billing", confidence=0.9, reasoning="double-charge mention"
    )
    monkeypatch.setattr("ticket_triage.coordinator._client", fake_client)

    classify("I was charged twice for order ORD-001")

    assert fake_client.messages.create.call_args.kwargs["model"] == CLASSIFIER_MODEL


def test_classifier_model_is_cheaper_than_subagent_model():
    assert "haiku" in CLASSIFIER_MODEL
    assert "haiku" not in SUBAGENT_MODEL
