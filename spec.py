"""
Spec schema and utilities for E2E flow specification.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json


class APICall(BaseModel):
    url: str
    method: str = "GET"
    response: Dict[str, Any] = Field(default_factory=dict)
    request_body: Optional[Dict[str, Any]] = None


class FlowStep(BaseModel):
    action: str  # "navigate", "click", "fill", "wait", etc.
    selector: Optional[str] = None
    url: Optional[str] = None
    value: Optional[str] = None
    data_testid: Optional[str] = None


class Flow(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    steps: List[FlowStep]
    mocked_apis: List[APICall] = Field(default_factory=list)
    components_involved: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Spec(BaseModel):
    version: str = "1.0"
    flows: Dict[str, Flow] = Field(default_factory=dict)
    mocks: Dict[str, str] = Field(default_factory=dict)  # Global mocks
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, path: str) -> "Spec":
        with open(path) as f:
            return cls(**json.load(f))

    def save(self, path: str):
        with open(path, 'w') as f:
            f.write(self.to_json())
