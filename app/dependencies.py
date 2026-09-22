import neo4j
from fastapi import Request
from app.config import settings
from app.repositories.graph_repository import Neo4JAsyncGraphRepository
from app.security.query_guard import CypherQueryGuard
from app.services.graph_service import GraphService


def get_neo4j_driver(request: Request) -> neo4j.AsyncDriver:
    return request.app.state.driver


def get_neo4j_repo(request: Request) -> Neo4JAsyncGraphRepository:
    return Neo4JAsyncGraphRepository(driver=get_neo4j_driver(request))


def get_graph_service(request: Request) -> GraphService:
    repo = get_neo4j_repo(request)
    guard = CypherQueryGuard(max_match_clauses=settings.max_match_clauses)
    return GraphService(repo=repo, guard=guard)
