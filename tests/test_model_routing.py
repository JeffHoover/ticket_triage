import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from ticket_triage.coordinator import _CLASSIFY_SYSTEM, classify
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


def test_classify_passes_correct_kwargs_to_messages_create(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _classification_api_response(
        domain="billing", confidence=0.9, reasoning="double-charge mention"
    )
    monkeypatch.setattr("ticket_triage.coordinator._client", fake_client)

    classify("I was charged twice for order ORD-001")

    kwargs = fake_client.messages.create.call_args.kwargs
    assert kwargs["max_tokens"] == 256
    assert kwargs["system"] == _CLASSIFY_SYSTEM
    assert kwargs["messages"][0]["role"] == "user"
    assert kwargs["messages"][0]["content"] == "I was charged twice for order ORD-001"


def test_classifier_model_is_cheaper_than_subagent_model():
    assert "haiku" in CLASSIFIER_MODEL
    assert "haiku" not in SUBAGENT_MODEL


def test_classify_strips_markdown_fences_from_response(monkeypatch):
    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text="```json\n" + json.dumps(
                    {"domain": "billing", "confidence": 0.9, "reasoning": "double-charge"}
                ) + "\n```",
            )
        ],
        stop_reason="end_turn",
    )
    monkeypatch.setattr("ticket_triage.coordinator._client", fake_client)

    result = classify("I was charged twice for order ORD-001")

    assert result.domain == "billing"
