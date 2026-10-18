from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class NoticeInput(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{3,60}$')
    supplier: str = Field(default='SUP-1', pattern=r'^SUP-[1-3]$')
    title: str = Field(min_length=5, max_length=200)
    allergen: Literal['milk', 'sesame', 'peanut', 'almond'] = 'milk'
    lots: list[str] = Field(min_length=1, max_length=50)
    effective_from: date = date(2026, 9, 1)
    effective_to: date = date(2026, 9, 30)
    scope: Literal['exact', 'ambiguous'] = 'exact'
    evidence: str = Field(default='Synthetic supplier corrective declaration', min_length=10, max_length=2000)

    @model_validator(mode='after')
    def dates(self):
        if self.effective_to < self.effective_from:
            raise ValueError('Effective end precedes start')
        if any(len(x) < 3 or len(x) > 80 for x in self.lots):
            raise ValueError('Invalid lot identifier')
        return self


class InvestigationInput(BaseModel):
    notice: str
    mode: Literal['auto', 'offline', 'llm', 'restricted'] = 'auto'


class DecisionInput(BaseModel):
    investigation: str
    batch: str
    role: Literal['QA', 'Warehouse', 'Viewer'] = 'Viewer'
    decision: Literal['release', 'dispose', 'reject', 'request_evidence']
    reason: str = Field(min_length=10, max_length=2000)


class EvidenceInput(BaseModel):
    investigation: str
    batch: str
    role: Literal['QA', 'Warehouse', 'Viewer'] = 'Viewer'
    prerequisite: Literal['supplier_reconciliation', 'label_review', 'quality_review', 'relabeling_validation']
    reason: str = Field(min_length=10, max_length=2000)


class ResetInput(BaseModel):
    confirmation: Literal['RESET SYNTHETIC DEMO']


class HealthOutput(BaseModel):
    status: str
    graph: str
    falkordb: str
    client_version: str
    mode: str


class InvestigationOutput(BaseModel):
    id: str
    kind: str
    status: str
    notice: str
    mode: str
    synthetic: bool
    name: str
    created_at: str


class GraphOutput(BaseModel):
    nodes: list[dict]
    edges: list[dict]
