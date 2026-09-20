from anthropic import Anthropic
from pydantic import ValidationError

from ticket_triage.schemas import Classification, SubagentResult
from ticket_triage.tools import (
    IssueRefundInput,
    LookUpOrderInput,
    issue_refund,
    look_up_order,
)

RESPONSE_TOOL_NAME = "submit_response"
BILLING_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
MAX_VALIDATION_RETRIES = 2

BILLING_SYSTEM_PROMPT = (
    "You are a billing support specialist. Use the available tools to look "
    "up orders and issue refunds as needed. When you're done, call the "
    f"{RESPONSE_TOOL_NAME} tool with your final structured response."
)

_client: Anthropic | None = None

_TOOL_REGISTRY = {
    "look_up_order": (LookUpOrderInput, look_up_order),
    "issue_refund": (IssueRefundInput, issue_refund),
}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _build_tool_defs() -> list[dict]:
    return [
        {
            "name": "look_up_order",
            "description": "Look up a customer's order by order_id.",
            "input_schema": LookUpOrderInput.model_json_schema(),
        },
        {
            "name": "issue_refund",
            "description": "Issue a refund for an order.",
            "input_schema": IssueRefundInput.model_json_schema(),
        },
        {
            "name": RESPONSE_TOOL_NAME,
            "description": (
                "Submit your final structured response. Call this exactly "
                "once when you're done handling the ticket."
            ),
            "input_schema": SubagentResult.model_json_schema(),
        },
    ]


def billing_agent(
    ticket: str, classification: Classification
) -> SubagentResult:
    client = _get_client()
    tools = _build_tool_defs()
    messages = [
        {
            "role": "user",
            "content": (
                f"{ticket}\n\n(routing reason: {classification.reasoning})"
            ),
        }
    ]
    validation_retries = 0

    while True:
        response = client.messages.create(
            model=BILLING_MODEL,
            max_tokens=MAX_TOKENS,
            system=BILLING_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        tool_use_blocks = [
            block for block in response.content if block.type == "tool_use"
        ]

        response_tool_call = next(
            (
                block
                for block in tool_use_blocks
                if block.name == RESPONSE_TOOL_NAME
            ),
            None,
        )

        if response_tool_call is not None:
            try:
                return SubagentResult(**response_tool_call.input)
            except ValidationError as validation_error:
                validation_retries += 1
                if validation_retries > MAX_VALIDATION_RETRIES:
                    return SubagentResult(status="failed")
                messages.append(
                    {"role": "assistant", "content": response.content}
                )
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
            input_schema, tool_fn = _TOOL_REGISTRY[block.name]
            tool_output = tool_fn(input_schema(**block.input))
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_output.model_dump_json(),
                }
            )

        messages.append({"role": "user", "content": tool_results})
