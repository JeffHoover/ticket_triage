from anthropic import Anthropic
from pydantic import ValidationError

from ticket_triage.schemas import Classification, SubagentResult
from ticket_triage.rag import search_docs as _search_docs
from ticket_triage.tools import (
    IssueRefundInput,
    LookUpOrderInput,
    SearchDocsChunk,
    SearchDocsInput,
    SearchDocsResult,
    issue_refund,
    look_up_order,
)

RESPONSE_TOOL_NAME = "submit_response"
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
SUBAGENT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
MAX_VALIDATION_RETRIES = 2
# Max messages passed to the API per turn. When exceeded, oldest
# assistant+tool-result pairs are dropped to keep the context bounded while
# preserving messages[0] (the original ticket) and role alternation.
MAX_HISTORY_MESSAGES = 10

BILLING_SYSTEM_PROMPT = (
    "You are a billing support specialist. Use the available tools to look "
    "up orders and issue refunds as needed. When you're done, call the "
    f"{RESPONSE_TOOL_NAME} tool with your final structured response."
)
TECHNICAL_SYSTEM_PROMPT = (
    "You are a technical support specialist. Use the available tools to look "
    "up order details that may be relevant to a technical issue. When you're "
    f"done, call the {RESPONSE_TOOL_NAME} tool with your final structured response."
)

_client: Anthropic | None = None

_LOOK_UP_ORDER_DEF = {
    "name": "look_up_order",
    "description": "Look up a customer's order by order_id.",
    "input_schema": LookUpOrderInput.model_json_schema(),
}

_ISSUE_REFUND_DEF = {
    "name": "issue_refund",
    "description": "Issue a refund for an order.",
    "input_schema": IssueRefundInput.model_json_schema(),
}

_RESPONSE_TOOL_DEF = {
    "name": RESPONSE_TOOL_NAME,
    "description": (
        "Submit your final structured response. Call this exactly "
        "once when you're done handling the ticket."
    ),
    "input_schema": SubagentResult.model_json_schema(),
    "cache_control": {"type": "ephemeral"},
}

_BILLING_TOOL_DEFS = [_LOOK_UP_ORDER_DEF, _ISSUE_REFUND_DEF, _RESPONSE_TOOL_DEF]
_BILLING_TOOL_REGISTRY = {
    "look_up_order": (LookUpOrderInput, look_up_order),
    "issue_refund": (IssueRefundInput, issue_refund),
}

_SEARCH_DOCS_DEF = {
    "name": "search_docs",
    "description": (
        "Search the product documentation for information relevant to this ticket. "
        "Call this when you need grounding from policy or known-issue docs before responding."
    ),
    "input_schema": SearchDocsInput.model_json_schema(),
}

_TECHNICAL_TOOL_DEFS = [_LOOK_UP_ORDER_DEF, _SEARCH_DOCS_DEF, _RESPONSE_TOOL_DEF]
_TECHNICAL_TOOL_REGISTRY = {
    "look_up_order": (LookUpOrderInput, look_up_order),
    "search_docs": (
        SearchDocsInput,
        lambda req: SearchDocsResult(
            chunks=[SearchDocsChunk(**chunk) for chunk in _search_docs(req.query)]
        ),
    ),
}

def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _cached_system(text: str) -> list[dict]:
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _run_agent(
    ticket: str,
    classification: Classification,
    system_prompt: str,
    tool_defs: list[dict],
    tool_registry: dict,
) -> SubagentResult:
    client = _get_client()
    messages = [
        {
            "role": "user",
            "content": f"{ticket}\n\n(routing reason: {classification.reasoning})",
        }
    ]
    validation_retries = 0

    while True:
        response = client.messages.create(
            model=SUBAGENT_MODEL,
            max_tokens=MAX_TOKENS,
            system=_cached_system(system_prompt),
            tools=tool_defs,
            messages=messages,
        )

        tool_use_blocks = [
            block for block in response.content if block.type == "tool_use"
        ]

        response_tool_call = next(
            (block for block in tool_use_blocks if block.name == RESPONSE_TOOL_NAME),
            None,
        )

        if response_tool_call is not None:
            try:
                return SubagentResult(**response_tool_call.input)
            except ValidationError as validation_error:
                validation_retries += 1
                if validation_retries > MAX_VALIDATION_RETRIES:
                    return SubagentResult(status="failed")
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": response_tool_call.id,
                                "content": (
                                    f"Validation error: {validation_error}. "
                                    "Retry with valid input."
                                ),
                                "is_error": True,
                            }
                        ],
                    }
                )
                continue

        if not tool_use_blocks:
            raise RuntimeError(
                "Subagent produced no tool_use blocks "
                f"(stop_reason={response.stop_reason})"
            )

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            input_schema, tool_fn = tool_registry[block.name]
            tool_output = tool_fn(input_schema(**block.input))
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_output.model_dump_json(),
                }
            )

        messages.append({"role": "user", "content": tool_results})

        while len(messages) > MAX_HISTORY_MESSAGES:
            del messages[1:3] # Remove the oldest assistant+tool-result pair, preserving messages[0] (the original ticket) and role alternation.


def billing_agent(ticket: str, classification: Classification) -> SubagentResult:
    return _run_agent(
        ticket, classification,
        BILLING_SYSTEM_PROMPT, _BILLING_TOOL_DEFS, _BILLING_TOOL_REGISTRY,
    )


def technical_agent(ticket: str, classification: Classification) -> SubagentResult:
    return _run_agent(
        ticket, classification,
        TECHNICAL_SYSTEM_PROMPT, _TECHNICAL_TOOL_DEFS, _TECHNICAL_TOOL_REGISTRY,
    )


REFUND_SYSTEM_PROMPT = (
    "You are a refund-eligibility specialist. Look up the order, determine "
    "whether a refund is warranted, and issue it if eligible. When you're "
    f"done, call the {RESPONSE_TOOL_NAME} tool with your final structured response."
)

_REFUND_TOOL_DEFS = [_LOOK_UP_ORDER_DEF, _ISSUE_REFUND_DEF, _RESPONSE_TOOL_DEF]
_REFUND_TOOL_REGISTRY = {
    "look_up_order": (LookUpOrderInput, look_up_order),
    "issue_refund": (IssueRefundInput, issue_refund),
}


def refund_agent(ticket: str, classification: Classification) -> SubagentResult:
    return _run_agent(
        ticket, classification,
        REFUND_SYSTEM_PROMPT, _REFUND_TOOL_DEFS, _REFUND_TOOL_REGISTRY,
    )
