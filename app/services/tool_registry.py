from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class SummarizeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)


class CreateTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], dict[str, Any]]
    requires_approval: bool = False


def _summarize(payload: BaseModel) -> dict[str, Any]:
    data = SummarizeInput.model_validate(payload.model_dump())
    text = " ".join(data.text.split())
    excerpt = text[:240]
    if len(text) > 240:
        excerpt += "…"
    return {"summary": excerpt, "character_count": len(text), "word_count": len(text.split())}


def _simulate_ticket(payload: BaseModel) -> dict[str, Any]:
    """Return a simulated ticket receipt; never contacts an external service."""
    data = CreateTicketInput.model_validate(payload.model_dump())
    return {
        "simulated": True,
        "ticket_reference": "DEMO-" + data.title[:24].upper().replace(" ", "-"),
        "title": data.title,
        "priority": data.priority,
        "message": "Demo only: no ticketing system was contacted.",
    }


TOOLS: dict[str, ToolDefinition] = {
    "summarize_text": ToolDefinition(
        name="summarize_text",
        description="Normalize and summarize a short text input.",
        input_model=SummarizeInput,
        handler=_summarize,
        requires_approval=False,
    ),
    "create_ticket": ToolDefinition(
        name="create_ticket",
        description="Simulate preparing a ticket; must be explicitly approved.",
        input_model=CreateTicketInput,
        handler=_simulate_ticket,
        requires_approval=True,
    ),
}


def validate_tool_input(tool_name: str, payload: dict[str, Any]) -> BaseModel:
    """Validate a payload only against a known, allowlisted tool."""
    tool = TOOLS.get(tool_name)
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' is not allowlisted.")
    return tool.input_model.model_validate(payload)


def invoke_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke a registered tool after validating its schema."""
    tool = TOOLS.get(tool_name)
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' is not allowlisted.")
    validated = tool.input_model.model_validate(payload)
    return tool.handler(validated)
