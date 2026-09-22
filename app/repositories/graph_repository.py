from typing import Protocol
from neo4j import AsyncDriver


class RepositoryService(Protocol):
    async def execute_read(self, query: str, params: dict) -> list[dict]: ...
    async def execute_write(self, query: str, params: dict) -> list[dict]: ...


class Neo4JAsyncGraphRepository:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    async def execute_read(self, query: str, params: dict) -> list[dict]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.data()

    async def execute_write(self, query: str, params: dict) -> list[dict]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.data()
