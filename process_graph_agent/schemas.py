from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ActivityType = Literal["task", "gateway", "sendTask", "subProcess"]


class Activity(BaseModel):
    ref: str = Field(..., description="Local reference used only within this pipeline run, e.g. 'A3'.")
    label: str = Field(..., description="Short human-readable name of the step.")
    type: ActivityType = "task"
    quote: str = Field(..., description="Verbatim excerpt from the transcript supporting this activity.")
    grounded: bool = Field(
        True,
        description="False if the model could not find solid transcript support and is flagging it rather than guessing.",
    )
    note: Optional[str] = Field(
        None, description="Optional note on ambiguity/contradiction the model noticed for this step."
    )


class ExtractionResult(BaseModel):
    activities: list[Activity]


class Edge(BaseModel):
    source_ref: str = Field(..., description="Activity.ref this edge starts from.")
    target_ref: str = Field(..., description="Activity.ref this edge points to.")
    condition: Optional[str] = Field(None, description="Branch condition, if this edge is a conditional branch.")
    is_default_branch: bool = Field(False, description="True if this is the fallback/else branch of a gateway.")
    quote: Optional[str] = Field(
        None, description="Verbatim excerpt supporting this ordering/condition. None if inferred, not stated."
    )
    inferred: bool = Field(
        False, description="True if this ordering was inferred (e.g. from narrative sequence) rather than stated directly."
    )


class OrderingResult(BaseModel):
    edges: list[Edge]
    start_ref: str = Field(..., description="Activity.ref of the first step in the process.")
    terminal_refs: list[str] = Field(..., description="Activity.ref(s) that end the process.")
