from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.schemas import Decision, RunStatus, StepStatus
from app.services.tool_registry import invoke_tool, validate_tool_input
from app.services.workflow_engine import InvalidWorkflowStateError, WorkflowEngine, WorkflowNotFoundError


def make_engine() -> WorkflowEngine:
    return WorkflowEngine()


def test_create_run_executes_safe_tool_then_pauses_for_approval() -> None:
    workflow = make_engine().create_run(
        "Summarize an incident and create a follow-up ticket",
        {"incident": "Checkout timed out after deployment."},
    )
    assert workflow.status == RunStatus.WAITING_FOR_APPROVAL
    assert workflow.plan[0].status == StepStatus.SUCCEEDED
    assert workflow.plan[1].status == StepStatus.WAITING_FOR_APPROVAL
    assert workflow.pending_approval_step_id == workflow.plan[1].step_id
    assert workflow.plan[0].step_id in workflow.results
    assert any(item.event == "approval_required" for item in workflow.trace)


def test_approval_resumes_workflow_and_completes() -> None:
    engine = make_engine()
    workflow = engine.create_run("Create a follow-up ticket", {"incident": "API error"})
    result = engine.decide(workflow.run_id, Decision.APPROVE, comment="Reviewed in test")
    assert result.status == RunStatus.COMPLETED
    assert result.pending_approval_step_id is None
    assert result.plan[1].status == StepStatus.SUCCEEDED
    ticket = result.results[result.plan[1].step_id]
    assert ticket["simulated"] is True
    assert "no ticketing system was contacted" in ticket["message"]


def test_rejection_never_executes_approval_required_tool() -> None:
    engine = make_engine()
    workflow = engine.create_run("Create a follow-up ticket", {"incident": "API error"})
    result = engine.decide(workflow.run_id, Decision.REJECT)
    assert result.status == RunStatus.REJECTED
    assert result.plan[1].status == StepStatus.REJECTED
    assert result.plan[1].step_id not in result.results


def test_second_decision_is_rejected_as_invalid_transition() -> None:
    engine = make_engine()
    workflow = engine.create_run("Create a follow-up ticket", {"incident": "API error"})
    engine.decide(workflow.run_id, Decision.REJECT)
    with pytest.raises(InvalidWorkflowStateError):
        engine.decide(workflow.run_id, Decision.APPROVE)


def test_unknown_run_raises_not_found() -> None:
    with pytest.raises(WorkflowNotFoundError):
        make_engine().get_run(uuid4())


def test_tool_registry_rejects_unknown_tools() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        invoke_tool("run_shell_command", {"command": "echo unsafe"})


def test_tool_registry_rejects_extra_or_invalid_fields() -> None:
    with pytest.raises(ValidationError):
        validate_tool_input("create_ticket", {"title": "x", "unknown": "value"})


def test_summary_tool_normalizes_whitespace() -> None:
    result = invoke_tool("summarize_text", {"text": "  checkout\n\t timeout  "})
    assert result["summary"] == "checkout timeout"
    assert result["word_count"] == 2
