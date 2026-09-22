"""
Integration tests — full HTTP request → response cycle using the real FastAPI
app with a mocked repository (no live Neo4j required).
"""
import pytest
from httpx import AsyncClient

TEST_API_KEY = "test-api-key"
QUERY_URL = "/api/v1/query"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def test_missing_api_key_returns_401(async_client: AsyncClient):
    response = await async_client.post(QUERY_URL, json={"query": "MATCH (n) RETURN n"})
    assert response.status_code == 401


async def test_wrong_api_key_returns_401(async_client: AsyncClient):
    response = await async_client.post(
        QUERY_URL,
        headers={"X-API-Key": "wrong-key"},
        json={"query": "MATCH (n) RETURN n"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Successful query
# ---------------------------------------------------------------------------

async def test_valid_query_returns_200(async_client: AsyncClient):
    response = await async_client.post(
        QUERY_URL,
        headers={"X-API-Key": TEST_API_KEY},
        json={"query": "MATCH (n) RETURN n LIMIT 2"},
    )
    assert response.status_code == 200


async def test_response_schema(async_client: AsyncClient):
    response = await async_client.post(
        QUERY_URL,
        headers={"X-API-Key": TEST_API_KEY},
        json={"query": "MATCH (n) RETURN n LIMIT 2"},
    )
    body = response.json()
    assert "results" in body
    assert "row_count" in body
    assert "execution_time_ms" in body
    assert body["row_count"] == 2
    assert isinstance(body["execution_time_ms"], float)


async def test_response_includes_request_id_header(async_client: AsyncClient):
    response = await async_client.post(
        QUERY_URL,
        headers={"X-API-Key": TEST_API_KEY},
        json={"query": "MATCH (n) RETURN n LIMIT 2"},
    )
    assert "x-request-id" in response.headers


# ---------------------------------------------------------------------------
# Guard enforcement
# ---------------------------------------------------------------------------

async def test_write_query_returns_403(async_client: AsyncClient):
    response = await async_client.post(
        QUERY_URL,
        headers={"X-API-Key": TEST_API_KEY},
        json={"query": "MATCH (n) DETACH DELETE n"},
    )
    assert response.status_code == 403


async def test_invalid_request_body_returns_422(async_client: AsyncClient):
    response = await async_client.post(
        QUERY_URL,
        headers={"X-API-Key": TEST_API_KEY},
        json={"not_a_query": "oops"},
    )
    assert response.status_code == 422
