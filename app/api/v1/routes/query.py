from fastapi import APIRouter, Depends, Request
from app.dependencies import get_graph_service
from app.limiter import limiter
from app.security.auth import get_api_key
from app.services.graph_service import GraphService
from app.schemas.query import CypherQueryRequest, CypherQueryResponse
from app.config import settings

router = APIRouter()


@router.post("/query", response_model=CypherQueryResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def run_query(
    request: Request,
    body: CypherQueryRequest,
    service: GraphService = Depends(get_graph_service),
    _api_key: str = Depends(get_api_key),
) -> CypherQueryResponse:
    """Execute a read-only Cypher query against the knowledge graph."""
    return await service.run_cypher(body)
