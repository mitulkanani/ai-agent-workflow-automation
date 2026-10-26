from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.models.schemas import Decision, RunStatus, StepStatus, TraceEvent, WorkflowRun
from app.services.planner import build_demo_plan
from app.services.tool_registry import TOOLS, invoke_tool, validate_tool_input


class WorkflowNotFoundError(KeyError):
    """The requested run does not exist."""


class InvalidWorkflowStateError(ValueError):
    """A state transition is not valid for the current run."""


class WorkflowEngine:
    """Small in-memory engine demonstrating explicit approval-gated execution.

    A lock protects state transitions within one Python process. Production
    deployments need transactional persistence and distributed coordination.
    """

    def __init__(self) -> None:
        self._runs: dict[UUID, WorkflowRun] = {}
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _event(
        self,
        run: WorkflowRun,
        event: str,
        message: str,
        step_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        run.trace.append(TraceEvent(
            timestamp=self._now(), event=event, message=message,
            step_id=step_id, details=details or {},
        ))

    def create_run(self, goal: str, context: dict[str, Any]) -> WorkflowRun:
        plan = build_demo_plan(goal, context)
        # Validate the entire plan before executing any part of it.
        for step in plan:
            tool = TOOLS.get(step.tool_name)
            if tool is None:
                raise ValueError(f"Planner returned unknown tool '{step.tool_name}'.")
            if step.requires_approval != tool.requires_approval:
                raise ValueError(f"Approval policy mismatch for tool '{step.tool_name}'.")
            validate_tool_input(step.tool_name, step.input)

        now = self._now()
        run = WorkflowRun(
            run_id=uuid4(), goal=goal, context=context, status=RunStatus.QUEUED,
            plan=plan, created_at=now, updated_at=now,
        )
        with self._lock:
            self._runs[run.run_id] = run
            self._event(run, "run_created", "Workflow run created.")
            run.status = RunStatus.RUNNING
            self._event(run, "run_started", "Workflow execution started.")
            self._execute_until_pause_or_finish(run)
            run.updated_at = self._now()
            return run.model_copy(deep=True)

    def get_run(self, run_id: UUID) -> WorkflowRun:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise WorkflowNotFoundError(str(run_id))
            return run.model_copy(deep=True)

    def list_runs(self, limit: int = 20) -> list[WorkflowRun]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda item: item.created_at, reverse=True)
            return [run.model_copy(deep=True) for run in runs[:limit]]

    def decide(self, run_id: UUID, decision: Decision, comment: str | None = None) -> WorkflowRun:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise WorkflowNotFoundError(str(run_id))
            if run.status != RunStatus.WAITING_FOR_APPROVAL:
                raise InvalidWorkflowStateError(f"Run is '{run.status.value}', not waiting for approval.")

            step_id = run.pending_approval_step_id
            step = next((candidate for candidate in run.plan if candidate.step_id == step_id), None)
            if step is None:
                raise InvalidWorkflowStateError("Pending approval step was not found.")

            self._event(
                run, "approval_decision", f"Approval decision: {decision.value}.",
                step_id=step.step_id, details={"comment": comment} if comment else {},
            )
            run.pending_approval_step_id = None

            if decision == Decision.REJECT:
                step.status = StepStatus.REJECTED
                run.status = RunStatus.REJECTED
                self._event(run, "step_rejected", "Approval-required step rejected; no tool was invoked.", step_id=step.step_id)
            else:
                # Re-check policy at decision time, not only during planning.
                definition = TOOLS.get(step.tool_name)
                if definition is None or not definition.requires_approval:
                    run.status = RunStatus.FAILED
                    run.error = "Approval policy could not be verified."
                    self._event(run, "run_failed", run.error, step_id=step.step_id)
                else:
                    try:
                        step.status = StepStatus.RUNNING
                        self._event(run, "step_started", f"Executing approved tool '{step.tool_name}'.", step_id=step.step_id)
                        result = invoke_tool(step.tool_name, step.input)
                        run.results[step.step_id] = result
                        step.status = StepStatus.SUCCEEDED
                        self._event(run, "step_succeeded", f"Tool '{step.tool_name}' completed.", step_id=step.step_id)
                        run.status = RunStatus.RUNNING
                        self._execute_until_pause_or_finish(run)
                    except (ValidationError, ValueError, TypeError) as exc:
                        step.status = StepStatus.FAILED
                        run.status = RunStatus.FAILED
                        run.error = f"{type(exc).__name__}: {exc}"
                        self._event(run, "step_failed", run.error, step_id=step.step_id)

            run.updated_at = self._now()
            return run.model_copy(deep=True)

    def _execute_until_pause_or_finish(self, run: WorkflowRun) -> None:
        for step in run.plan:
            if step.status != StepStatus.PENDING:
                continue

            tool = TOOLS.get(step.tool_name)
            if tool is None:
                step.status = StepStatus.FAILED
                run.status = RunStatus.FAILED
                run.error = f"Tool '{step.tool_name}' is not allowlisted."
                self._event(run, "run_failed", run.error, step_id=step.step_id)
                return

            # Registry policy is authoritative; a planner cannot bypass approval.
            if tool.requires_approval:
                step.status = StepStatus.WAITING_FOR_APPROVAL
                run.status = RunStatus.WAITING_FOR_APPROVAL
                run.pending_approval_step_id = step.step_id
                self._event(
                    run, "approval_required", f"Approval required for tool '{step.tool_name}'.",
                    step_id=step.step_id, details={"tool_name": step.tool_name},
                )
                return

            try:
                step.status = StepStatus.RUNNING
                self._event(run, "step_started", f"Executing tool '{step.tool_name}'.", step_id=step.step_id)
                result = invoke_tool(step.tool_name, step.input)
                run.results[step.step_id] = result
                step.status = StepStatus.SUCCEEDED
                self._event(run, "step_succeeded", f"Tool '{step.tool_name}' completed.", step_id=step.step_id)
            except (ValidationError, ValueError, TypeError) as exc:
                step.status = StepStatus.FAILED
                run.status = RunStatus.FAILED
                run.error = f"{type(exc).__name__}: {exc}"
                self._event(run, "step_failed", run.error, step_id=step.step_id)
                return

        if run.status not in (RunStatus.FAILED, RunStatus.REJECTED):
            run.status = RunStatus.COMPLETED
            self._event(run, "run_completed", "All workflow steps completed.")


engine = WorkflowEngine()
