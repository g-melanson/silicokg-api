from fastapi import APIRouter, Depends, Request
from silicokg_api.dependencies import get_graph_service
from silicokg_api.limiter import limiter
from silicokg_api.security.auth import get_api_key
from silicokg_api.services.graph_service import GraphService
from silicokg_api.schemas.query import CypherQueryRequest, CypherQueryResponse
from silicokg_api.config import settings

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
