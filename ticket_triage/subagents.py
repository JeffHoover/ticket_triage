from anthropic import Anthropic

from ticket_triage.schemas import Classification, SubagentResult

RESPONSE_TOOL_NAME = "submit_response"
BILLING_MODEL = "claude-sonnet-4-6"

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def billing_agent(
    ticket: str, classification: Classification
) -> SubagentResult:
    raise NotImplementedError
