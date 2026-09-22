from typing import Any
from pydantic import BaseModel


class CypherQueryRequest(BaseModel):
    query: str
    parameters: dict[str, Any] = {}


class CypherQueryResponse(BaseModel):
    results: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
