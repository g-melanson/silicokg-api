import time
import structlog
from app.repositories.graph_repository import RepositoryService
from app.schemas.query import CypherQueryRequest, CypherQueryResponse
from app.security.query_guard import CypherQueryGuard

log = structlog.get_logger()


class GraphService:
    def __init__(self, repo: RepositoryService, guard: CypherQueryGuard | None = None):
        self._repo = repo
        self._guard = guard or CypherQueryGuard()

    async def run_cypher(self, request: CypherQueryRequest) -> CypherQueryResponse:
        self._guard.validate(request.query)
        start = time.perf_counter()
        results = await self._repo.execute_read(request.query, request.parameters)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        log.info(
            "query_executed",
            row_count=len(results),
            execution_time_ms=elapsed_ms,
        )
        return CypherQueryResponse(
            results=results,
            row_count=len(results),
            execution_time_ms=elapsed_ms,
        )
