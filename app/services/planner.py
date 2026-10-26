from typing import Any
from uuid import uuid4

from app.models.schemas import PlannedStep


def build_demo_plan(goal: str, context: dict[str, Any]) -> list[PlannedStep]:
    """Build a predictable demo plan without invoking an external LLM.

    The demo intentionally supports a small, transparent set of actions. Every
    plan is validated against the tool registry before execution.
    """
    incident = str(context.get("incident") or goal)
    summary = incident.strip()[:1200]
    return [
        PlannedStep(
            step_id=str(uuid4()),
            tool_name="summarize_text",
            description="Create a concise summary from the supplied context.",
            input={"text": summary},
        ),
        PlannedStep(
            step_id=str(uuid4()),
            tool_name="create_ticket",
            description="Prepare a follow-up ticket (simulation; approval required).",
            input={
                "title": f"Follow-up: {goal[:100]}",
                "description": summary,
                "priority": "normal",
            },
            requires_approval=True,
        ),
    ]
