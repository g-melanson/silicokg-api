import pytest
from unittest.mock import AsyncMock
from app.services.graph_service import GraphService
from app.security.query_guard import CypherQueryGuard
from app.schemas.query import CypherQueryRequest
from fastapi import HTTPException


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.execute_read.return_value = [{"n": {"id": 1}}, {"n": {"id": 2}}]
    return repo


@pytest.fixture
def service(mock_repo):
    return GraphService(repo=mock_repo, guard=CypherQueryGuard())


async def test_run_cypher_returns_correct_row_count(service):
    request = CypherQueryRequest(query="MATCH (n) RETURN n LIMIT 2")
    response = await service.run_cypher(request)
    assert response.row_count == 2


async def test_run_cypher_returns_results(service):
    request = CypherQueryRequest(query="MATCH (n) RETURN n LIMIT 2")
    response = await service.run_cypher(request)
    assert len(response.results) == 2


async def test_run_cypher_records_execution_time(service):
    request = CypherQueryRequest(query="MATCH (n) RETURN n LIMIT 2")
    response = await service.run_cypher(request)
    assert response.execution_time_ms >= 0


async def test_run_cypher_passes_parameters_to_repo(service, mock_repo):
    request = CypherQueryRequest(
        query="MATCH (n {id: $id}) RETURN n",
        parameters={"id": 42},
    )
    await service.run_cypher(request)
    mock_repo.execute_read.assert_awaited_once_with(
        "MATCH (n {id: $id}) RETURN n", {"id": 42}
    )


async def test_run_cypher_rejects_write_query(service):
    request = CypherQueryRequest(query="MATCH (n) DETACH DELETE n")
    with pytest.raises(HTTPException) as exc:
        await service.run_cypher(request)
    assert exc.value.status_code == 403
