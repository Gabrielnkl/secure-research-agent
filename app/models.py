# app/models.py
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class ResearchBrief(BaseModel):
    text: str
    run_id: str


class ResearchPlan(BaseModel):
    queries: list[str] = Field(description="Search queries to run in parallel")
    focus: str = Field(description="Core question the research should answer")
    depth: Literal["shallow", "deep"] = "shallow"


class SearchResult(BaseModel):
    query: str
    snippets: list[str]
    sources: list[str]


class SynthesisInput(BaseModel):
    plan: ResearchPlan
    results: list['SearchResult']


class SynthesisOutput(BaseModel):
    summary: str
    key_points: list[str]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class SecurityVerdict(BaseModel):
    safe: bool
    reason: str


class ApprovalInput(BaseModel):
    verdict: bool
    note: str = ""


class WorkflowResult(BaseModel):
    run_id: str
    synthesis: SynthesisOutput | None = None
    blocked: bool = False
    block_reason: str | None = None
    approved: bool = False
    completed_at: datetime | None = None

