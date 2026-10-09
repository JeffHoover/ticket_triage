"""
Eval harness for the ticket-triage coordinator.

Two eval types, reflecting a deliberate tradeoff:

- Code-based (classification accuracy, status accuracy): cheap, deterministic,
  fast. Use for anything with an exact expected answer.
- Model-graded (reply quality): necessary when the output is natural language
  and "correct" can't be expressed as an exact match. Uses Claude-as-judge
  (Haiku — adequate for grading, much cheaper than Sonnet).

The fixed EVAL_CASES set is the source of truth for regression detection:
run before and after any change to a system prompt, model version, or tool
schema. A drop in domain_accuracy or avg_reply_score is a signal to investigate.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from ticket_triage.schemas import Classification, TriageReply


@dataclass
class EvalCase:
    ticket: str
    expected_domain: str
    expected_status: str | None = None  # None = don't assert on status
    description: str = ""


@dataclass
class EvalResult:
    case: EvalCase
    classification: Classification
    reply: TriageReply
    domain_correct: bool
    status_correct: bool | None  # None when expected_status not specified
    reply_score: int | None = None
    reply_rationale: str | None = None


@dataclass
class EvalReport:
    results: list[EvalResult]

    @property
    def domain_accuracy(self) -> float:
        return sum(r.domain_correct for r in self.results) / len(self.results)

    @property
    def status_accuracy(self) -> float | None:
        checked = [r for r in self.results if r.status_correct is not None]
        if not checked:
            return None
        return sum(r.status_correct for r in checked) / len(checked)

    @property
    def avg_reply_score(self) -> float | None:
        scored = [r.reply_score for r in self.results if r.reply_score is not None]
        if not scored:
            return None
        return sum(scored) / len(scored)


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        ticket="I was charged twice for order ORD-001",
        expected_domain="billing",
        expected_status="resolved",
        description="Double charge with order ID — should look up order and resolve",
    ),
    EvalCase(
        ticket="My app crashes every time I try to log in",
        expected_domain="technical",
        expected_status=None,
        description="Technical bug report with no order — domain check only",
    ),
    EvalCase(
        ticket="I want a refund",
        expected_domain="refund",
        expected_status="needs_info",
        description="Refund request without order ID — should ask for it",
    ),
    EvalCase(
        ticket="I returned my item two weeks ago and still haven't received my refund for order ORD-002",
        expected_domain="refund",
        expected_status="resolved",
        description="Refund request with order ID — should look up and issue refund",
    ),
    EvalCase(
        ticket="xkcd 327",
        expected_domain="unknown",
        expected_status="escalated",
        description="Unintelligible ticket — low confidence, should escalate",
    ),
]


def score_case(
    case: EvalCase,
    classification: Classification,
    reply: TriageReply,
) -> EvalResult:
    domain_correct = classification.domain == case.expected_domain
    status_correct = None
    if case.expected_status is not None:
        status_correct = reply.status == case.expected_status
    return EvalResult(
        case=case,
        classification=classification,
        reply=reply,
        domain_correct=domain_correct,
        status_correct=status_correct,
    )


def build_report(results: list[EvalResult]) -> EvalReport:
    return EvalReport(results=results)


_GRADER_PROMPT = """\
You are evaluating a customer support response.

Ticket: {ticket}

Response: {reply}

Rate the response quality on this scale:
1 = Inappropriate, harmful, or completely wrong
2 = Unhelpful or confusing
3 = Acceptable but generic
4 = Good — addresses the issue clearly
5 = Excellent — clear, complete, and appropriately warm

Respond with JSON only: {{"score": <1-5>, "rationale": "<one sentence>"}}"""


def grade_reply(ticket: str, reply: str, client) -> tuple[int, str]:
    """Call Claude-as-judge to score a reply draft. Returns (score, rationale)."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
        messages=[{"role": "user", "content": _GRADER_PROMPT.format(ticket=ticket, reply=reply)}],
    )
    import re
    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", text).strip()
    parsed = json.loads(text)
    return int(parsed["score"]), parsed["rationale"]


def run_evals(grade: bool = False) -> EvalReport:
    """
    Run all EVAL_CASES through the coordinator and score them.

    grade=False: code-based only (cheap, deterministic).
    grade=True: also run model-graded reply quality (costs extra tokens).
    """
    from ticket_triage.coordinator import classify, coordinator

    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    headers = {"anthropic-workspace-id": workspace_id} if workspace_id else {}

    results = []
    for case in EVAL_CASES:
        classification = classify(case.ticket)
        reply = coordinator.__wrapped__(case.ticket) if hasattr(coordinator, "__wrapped__") else coordinator(case.ticket)

        result = score_case(case, classification, reply)

        if grade and reply.text:
            from anthropic import Anthropic
            grader = Anthropic(default_headers=headers)
            score, rationale = grade_reply(case.ticket, reply.text, grader)
            result.reply_score = score
            result.reply_rationale = rationale

        results.append(result)

    return build_report(results)


def print_report(report: EvalReport) -> None:
    print(f"\n{'─' * 60}")
    print(f"  Eval results  ({len(report.results)} cases)")
    print(f"{'─' * 60}")
    for r in report.results:
        domain_marker = "✓" if r.domain_correct else "✗"
        status_marker = ("✓" if r.status_correct else "✗") if r.status_correct is not None else "–"
        score_str = f"  reply={r.reply_score}/5" if r.reply_score is not None else ""
        print(f"  [{domain_marker}] domain  [{status_marker}] status{score_str}  {r.case.description}")
        if r.reply_rationale:
            print(f"       {r.reply_rationale}")
    print(f"{'─' * 60}")
    print(f"  Domain accuracy : {report.domain_accuracy:.0%}")
    if report.status_accuracy is not None:
        print(f"  Status accuracy : {report.status_accuracy:.0%}")
    if report.avg_reply_score is not None:
        print(f"  Avg reply score : {report.avg_reply_score:.1f}/5")
    print(f"{'─' * 60}\n")
