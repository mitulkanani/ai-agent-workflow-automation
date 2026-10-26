from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.models.schemas import DecisionRequest, RunStatus, WorkflowCreate, WorkflowCreated, WorkflowRun
from app.services.workflow_engine import InvalidWorkflowStateError, WorkflowNotFoundError, engine

router = APIRouter()


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/runs", response_model=WorkflowCreated, status_code=status.HTTP_201_CREATED, tags=["workflow"])
def create_run(payload: WorkflowCreate) -> WorkflowCreated:
    try:
        run = engine.create_run(payload.goal, payload.context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    message = "Workflow is waiting for approval." if run.status == RunStatus.WAITING_FOR_APPROVAL else f"Workflow started with status '{run.status.value}'."
    return WorkflowCreated(run_id=run.run_id, status=run.status, message=message)


@router.get("/runs", response_model=list[WorkflowRun], tags=["workflow"])
def list_runs(limit: int = Query(default=20, ge=1, le=100)) -> list[WorkflowRun]:
    return engine.list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=WorkflowRun, tags=["workflow"])
def get_run(run_id: UUID) -> WorkflowRun:
    try:
        return engine.get_run(run_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow run not found.") from exc


@router.post("/runs/{run_id}/decision", response_model=WorkflowRun, tags=["workflow"])
def decide(run_id: UUID, payload: DecisionRequest) -> WorkflowRun:
    try:
        return engine.decide(run_id, payload.decision, payload.comment)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow run not found.") from exc
    except InvalidWorkflowStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
