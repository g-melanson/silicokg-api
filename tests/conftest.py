"""
Shared fixtures for the test suite.

Environment variables are set here before any app imports so that
pydantic-settings loads valid values during module initialisation.
"""
import os

os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("API_KEY", "test-api-key")

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies import get_graph_service
from app.repositories.graph_repository import RepositoryService
from app.security.query_guard import CypherQueryGuard
from app.services.graph_service import GraphService

TEST_API_KEY = "test-api-key"


@pytest.fixture
def mock_repo() -> RepositoryService:
    """An async mock that satisfies the RepositoryService Protocol."""
    repo = AsyncMock(spec=RepositoryService)
    repo.execute_read.return_value = [{"n": {"id": 1}}, {"n": {"id": 2}}]
    return repo


@pytest_asyncio.fixture
async def async_client(mock_repo: RepositoryService) -> AsyncClient:
    """
    Full ASGI test client.

    httpx's ASGITransport does not trigger the ASGI lifespan (and therefore
    never calls neo4j.AsyncGraphDatabase.driver), so we override get_graph_service
    — the actual Depends target in the route — to return a GraphService backed by
    mock_repo.  No live Neo4j instance is required.
    """
    def _override() -> GraphService:
        return GraphService(repo=mock_repo, guard=CypherQueryGuard())

    app.dependency_overrides[get_graph_service] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
