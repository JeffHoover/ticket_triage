from unittest.mock import MagicMock
from types import SimpleNamespace

from ticket_triage.evals import (
    EvalCase,
    EvalReport,
    EvalResult,
    build_report,
    grade_reply,
    score_case,
)
from ticket_triage.schemas import Classification, TriageReply


def _classification(domain: str) -> Classification:
    return Classification(domain=domain, confidence=0.9, reasoning="test")


def _reply(status: str, text: str = "reply") -> TriageReply:
    return TriageReply(status=status, text=text, escalation_reason=None)


# ── score_case ──────────────────────────────────────────────────────────────

def test_score_case_domain_correct_when_domain_matches():
    case = EvalCase(ticket="t", expected_domain="billing")
    result = score_case(case, _classification("billing"), _reply("resolved"))
    assert result.domain_correct is True


def test_score_case_domain_incorrect_when_domain_mismatches():
    case = EvalCase(ticket="t", expected_domain="billing")
    result = score_case(case, _classification("refund"), _reply("resolved"))
    assert result.domain_correct is False


def test_score_case_status_correct_when_status_matches():
    case = EvalCase(ticket="t", expected_domain="billing", expected_status="resolved")
    result = score_case(case, _classification("billing"), _reply("resolved"))
    assert result.status_correct is True


def test_score_case_status_incorrect_when_status_mismatches():
    case = EvalCase(ticket="t", expected_domain="billing", expected_status="resolved")
    result = score_case(case, _classification("billing"), _reply("escalated"))
    assert result.status_correct is False


def test_score_case_status_none_when_expected_status_not_specified():
    case = EvalCase(ticket="t", expected_domain="technical")
    result = score_case(case, _classification("technical"), _reply("needs_info"))
    assert result.status_correct is None


def test_score_case_preserves_case_classification_and_reply():
    case = EvalCase(ticket="t", expected_domain="billing")
    classification = _classification("billing")
    reply = _reply("resolved")
    result = score_case(case, classification, reply)
    assert result.case is case
    assert result.classification is classification
    assert result.reply is reply


# ── EvalReport ──────────────────────────────────────────────────────────────

def _result(domain_correct: bool, status_correct: bool | None, reply_score: int | None = None) -> EvalResult:
    case = EvalCase(ticket="t", expected_domain="billing")
    return EvalResult(
        case=case,
        classification=_classification("billing"),
        reply=_reply("resolved"),
        domain_correct=domain_correct,
        status_correct=status_correct,
        reply_score=reply_score,
    )


def test_report_domain_accuracy_all_correct():
    report = build_report([_result(True, None), _result(True, None)])
    assert report.domain_accuracy == 1.0


def test_report_domain_accuracy_half_correct():
    report = build_report([_result(True, None), _result(False, None)])
    assert report.domain_accuracy == 0.5


def test_report_status_accuracy_excludes_unchecked_cases():
    # Only the case with status_correct=True should count.
    report = build_report([_result(True, True), _result(True, None)])
    assert report.status_accuracy == 1.0


def test_report_status_accuracy_none_when_no_cases_have_expected_status():
    report = build_report([_result(True, None), _result(False, None)])
    assert report.status_accuracy is None


def test_report_avg_reply_score_averages_scored_results():
    report = build_report([_result(True, None, 4), _result(True, None, 2)])
    assert report.avg_reply_score == 3.0


def test_report_avg_reply_score_none_when_no_graded_results():
    report = build_report([_result(True, None), _result(False, None)])
    assert report.avg_reply_score is None


# ── grade_reply ─────────────────────────────────────────────────────────────

def test_grade_reply_parses_score_and_rationale_from_model_response():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text='{"score": 4, "rationale": "Clear and helpful."}')]
    )
    score, rationale = grade_reply("ticket text", "reply text", fake_client)
    assert score == 4
    assert rationale == "Clear and helpful."


def test_grade_reply_uses_haiku_model():
    fake_client = MagicMock()
    fake_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text='{"score": 3, "rationale": "ok"}')]
    )
    grade_reply("ticket", "reply", fake_client)
    assert "haiku" in fake_client.messages.create.call_args.kwargs["model"]
