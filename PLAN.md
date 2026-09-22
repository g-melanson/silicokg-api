# silicokg-api — Execution Plan

A Neo4j Knowledge Graph API built in Python with FastAPI.

---

## How to Use This Plan

Each phase introduces one or two **design patterns**. A design pattern is a named, reusable solution to a recurring problem in software engineering. Knowing the name lets you look them up, discuss them with other engineers, and recognise them in other codebases.

The phases are ordered so that after every phase you have a **working, runnable system** — not a half-built skeleton. Verify each phase manually before moving to the next.

**Current status:**
- [x] Phase 0 — Scaffolding (venv created, packages installed, `config.py` written)
- [x] Phase 1 — Repository skeleton (`graph_repository.py`, `dependencies.py` stubs)
- [ ] Phase 1 — Repository implementation (complete the method bodies)
- [ ] Phase 2 — API layer and first endpoint
- [ ] Phase 3 — Security
- [ ] Phase 4 — Testing
- [ ] Phase 5 — Observability

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│               HTTP Clients                  │
│   (curl, Swagger UI, another service)        │
└──────────────────┬──────────────────────────┘
                   │  HTTP Request / Response
┌──────────────────▼──────────────────────────┐
│          API Layer  (FastAPI)                │
│   Parses the request. Validates input.       │
│   Calls the service. Returns the response.  │
└──────────────────┬──────────────────────────┘
                   │  Python function call
┌──────────────────▼──────────────────────────┐
│            Service Layer                     │
│   Owns business logic: timing, validation,  │
│   transforming data between layers.          │
└──────────────────┬──────────────────────────┘
                   │  Python function call
┌──────────────────▼──────────────────────────┐
│         Repository / Data Access Layer       │
│   The only code that talks to Neo4j.        │
│   Translates Python ↔ graph queries.         │
└──────────────────┬──────────────────────────┘
                   │  Bolt protocol (network)
              [ Neo4j ]
```

**Why three layers?** Each layer has exactly one job.

- The **API layer** knows about HTTP — status codes, request parsing, headers.
- The **service layer** knows about business rules — what is allowed, how to shape data.
- The **repository layer** knows about Neo4j — how to open sessions and run queries.

No layer reaches past its immediate neighbour. This means you can change how Neo4j is queried without touching any route, and you can test each layer independently by mocking the one below it.

---

## A Note on `async` / `asyncio`

You will see `async def` and `await` throughout this codebase. Here is the mental model:

Python runs on a single thread. Normally, when it makes a network call (like a Neo4j query), it **sits and waits** — doing nothing — until the response arrives. During that wait, it cannot handle any other requests.

`asyncio` solves this by letting Python say *"I am waiting for Neo4j — go do something else in the meantime."* Tasks voluntarily yield control while they wait, so other tasks can run on the same thread.

**The simple rule: follow the I/O.**

Use `async def` whenever the function waits for something external (a database, a network call). Use a regular `def` everywhere else.

| Code | `async`? | Reason |
|---|---|---|
| `Neo4JAsyncGraphRepository.execute_read()` | ✅ Yes | Waits for Neo4j over the network |
| `GraphService.run_cypher()` | ✅ Yes | Calls the async repository |
| Route handler in FastAPI | ✅ Yes | Calls the async service |
| `CypherQueryGuard.validate()` | ❌ No | Pure CPU work — regex on a string, no I/O |
| `Settings` / `config.py` | ❌ No | Just reads environment variables |

**The propagation rule:** `async` propagates upward. If a function calls an `async def`, it must itself be `async def` and must use `await`. You can always call a regular function from an async one — the reverse is not true.

---

## Phase 0 — Project Scaffolding ✅

> **Pattern: Convention over Configuration**

Instead of inventing your own layout, follow the community-agreed structure so any Python developer can open the project and immediately know where to find things.

### Target Directory Structure

```
silicokg-api/
├── app/
│   ├── __init__.py
│   ├── main.py               ← FastAPI app and lifespan (Phase 2)
│   ├── config.py             ← Typed environment variable loading ✅
│   ├── dependencies.py       ← Shared FastAPI dependency providers (Phase 1) ✅
│   │
│   ├── api/
│   │   └── v1/
│   │       └── routes/
│   │           └── query.py  ← POST /query endpoint (Phase 2)
│   │
│   ├── services/
│   │   └── graph_service.py  ← Business logic (Phase 2)
│   │
│   ├── repositories/
│   │   └── graph_repository.py  ← Neo4j data access ✅
│   │
│   ├── schemas/
│   │   └── query.py          ← Request / response shapes (Phase 2)
│   │
│   └── security/
│       ├── auth.py           ← API key / JWT (Phase 3)
│       └── query_guard.py    ← Cypher query validation (Phase 3)
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
├── .env.example              ← Committed to git. Shows required variable names, no values.
├── .env                      ← Never committed. Holds your real secrets.
├── .gitignore                ✅
├── PLAN.md                   ← This file
└── README.md
```

### What `config.py` Does and Why

`config.py` uses `pydantic-settings` to read environment variables:

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    api_env: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
```

The naive alternative is `os.getenv("NEO4J_URI")` scattered throughout your code. The problem: if `NEO4J_URI` is missing, you get `None` at runtime — possibly deep inside a request handler, possibly in production. `pydantic-settings` reads all environment variables **at application startup**, validates their types, and raises a clear error immediately if anything is missing. The app refuses to start rather than silently failing later. This is called **fail-fast** behaviour.

### Tasks

- [x] Create `.venv` and activate it
- [x] Install packages: `fastapi`, `uvicorn`, `neo4j`, `pydantic-settings`, `pytest`, `pytest-asyncio`, `httpx`, `pytest-mock`
- [x] Write `app/config.py`
- [ ] Create `.env.example` with placeholder values (copy `.env` but replace real values with `""` or descriptions)
- [ ] Add `.env` to `.gitignore` so secrets are never committed

---

## Phase 1 — Data Access Layer

> **Patterns: Repository Pattern · Factory Pattern · Protocol (Interface)**

### What Each Pattern Means

**Repository Pattern:** The repository is the only object in the system that knows it is talking to Neo4j. Everything else asks the repository for data through a stable interface (`execute_read`). If you ever swap Neo4j for a different database, you change only the repository — nothing in the service or API layers changes.

**Protocol (Interface):** `RepositoryService` in `graph_repository.py` defines *what methods a repository must have* without specifying how they work. This lets you create a `FakeGraphRepository` in tests that returns hardcoded data — no real Neo4j connection needed to test the layers above.

**Factory Pattern:** Creating the `AsyncDriver` requires a URI, credentials, and connection pool configuration. That construction logic should live in exactly one place. In this project, that place is the `lifespan` function in `main.py`. The `dependencies.py` functions then simply *provide* the already-created driver to routes that request it.

### The Driver Lifecycle — Important

The `AsyncDriver` holds open a **connection pool** to Neo4j. This is expensive to create. The rules are:

1. Create the driver **once** at application startup.
2. Reuse it for every request.
3. Close it **once** at application shutdown.

Creating a new driver per request (as a naive factory would do) spins up a new connection pool on every HTTP request and never closes the old ones — a resource leak.

FastAPI provides the `lifespan` context manager for exactly this purpose:

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import neo4j
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything before `yield` runs at startup
    driver = neo4j.AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    app.state.driver = driver   # store on app so dependencies can retrieve it
    yield
    # Everything after `yield` runs at shutdown
    await driver.close()        # release all connections cleanly

app = FastAPI(lifespan=lifespan)
```

The `dependencies.py` functions then retrieve the driver from `app.state`:

```python
# app/dependencies.py
import neo4j
from fastapi import Request
from app.repositories.graph_repository import Neo4JAsyncGraphRepository

def get_neo4j_driver(request: Request) -> neo4j.AsyncDriver:
    return request.app.state.driver   # same driver instance every time

def get_graph_repo(request: Request) -> Neo4JAsyncGraphRepository:
    return Neo4JAsyncGraphRepository(driver=get_neo4j_driver(request))
```

### Completing `graph_repository.py`

The current `execute_read` implementation has two problems:

1. `self._driver.session()` opens a session but never closes it. Sessions must be opened inside `async with` so they are closed even if an exception occurs.
2. `session.run()` returns a `Result` object, not a list of dicts. You need to call `.data()` on it to get plain Python dictionaries.

The correct implementation:

```python
# app/repositories/graph_repository.py
from typing import Protocol, Any
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
            return await result.data()    # converts records to plain dicts

    async def execute_write(self, query: str, params: dict) -> list[dict]:
        async with self._driver.session() as session:
            result = await session.run(query, params)
            return await result.data()
```

**Why `async with` for sessions?** A context manager (`with` / `async with`) guarantees that the cleanup code runs no matter what — even if an exception is raised mid-query. Without it, a failed query would leave the session open indefinitely, eventually exhausting the connection pool.

### Tasks

- [ ] Write `app/main.py` with the `lifespan` context manager (create driver on startup, close on shutdown)
- [ ] Rewrite `app/dependencies.py` to retrieve the driver from `request.app.state`
- [ ] Complete `execute_read` in `graph_repository.py` using `async with self._driver.session() as session`
- [ ] Add `execute_write` stub (reserve for later)
- [ ] Update the `RepositoryService` Protocol to declare both methods with correct signatures

---

## Phase 2 — API Layer: The First Endpoint

> **Patterns: Dependency Injection · DTO (Data Transfer Object) · Service Layer**

### What Each Pattern Means

**DTO (Data Transfer Object):** An object whose only job is to carry data across a boundary — from HTTP into your Python code, or from Python out to the client. Pydantic `BaseModel` subclasses serve this role. They validate incoming data, reject unexpected fields, provide type hints, and serialise cleanly to JSON. Never pass raw request body dicts through your system — always deserialise into a DTO at the boundary.

**Service Layer:** The route's job is HTTP. The repository's job is data access. The service layer lives between them and owns the *business logic* — timing the query, shaping the result into the response DTO, and (in Phase 3) calling the query guard before executing. Keeping this in a separate class means you can call the same logic from a route, a CLI command, or a background job without duplicating code.

**Dependency Injection:** Instead of creating objects inside the functions that need them, you push construction to the framework. FastAPI's `Depends()` system is a first-class dependency injection container. Your route declares what it needs (`service: GraphService = Depends(get_graph_service)`) and FastAPI builds and provides it. This makes your route functions easy to test — swap the real service for a mock by overriding the dependency.

### Schemas

```python
# app/schemas/query.py
from pydantic import BaseModel
from typing import Any

class CypherQueryRequest(BaseModel):
    query: str                          # the Cypher string to execute
    parameters: dict[str, Any] = {}    # optional parameterised values

class CypherQueryResponse(BaseModel):
    results: list[dict[str, Any]]       # list of result records as dicts
    row_count: int                      # how many records were returned
    execution_time_ms: float            # how long the query took
```

### Service Layer

```python
# app/services/graph_service.py
import time
from app.repositories.graph_repository import RepositoryService
from app.schemas.query import CypherQueryRequest, CypherQueryResponse

class GraphService:
    def __init__(self, repo: RepositoryService):  # typed to the Protocol, not the concrete class
        self._repo = repo

    async def run_cypher(self, request: CypherQueryRequest) -> CypherQueryResponse:
        start = time.perf_counter()
        results = await self._repo.execute_read(request.query, request.parameters)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CypherQueryResponse(
            results=results,
            row_count=len(results),
            execution_time_ms=round(elapsed_ms, 2),
        )
```

Note that `GraphService` takes a `RepositoryService` Protocol, not a concrete `Neo4JAsyncGraphRepository`. This is called **programming to an interface** — a fundamental principle that makes code testable and substitutable.

### Route

```python
# app/api/v1/routes/query.py
from fastapi import APIRouter, Depends
from app.schemas.query import CypherQueryRequest, CypherQueryResponse
from app.services.graph_service import GraphService
from app.dependencies import get_graph_service

router = APIRouter()

@router.post("/query", response_model=CypherQueryResponse)
async def run_query(
    body: CypherQueryRequest,
    service: GraphService = Depends(get_graph_service),
):
    """Execute a read-only Cypher query against the knowledge graph."""
    return await service.run_cypher(body)
```

The route is intentionally thin — four lines of logic. All complexity lives in the service and repository.

### Add `get_graph_service` to `dependencies.py`

```python
# add to app/dependencies.py
from app.services.graph_service import GraphService

def get_graph_service(request: Request) -> GraphService:
    repo = get_graph_repo(request)
    return GraphService(repo=repo)
```

### Register the Route in `main.py`

```python
# add to app/main.py
from app.api.v1.routes.query import router as query_router

app.include_router(query_router, prefix="/api/v1")
```

### Tasks

- [ ] Write `app/schemas/query.py` with `CypherQueryRequest` and `CypherQueryResponse`
- [ ] Write `app/services/graph_service.py` with `GraphService.run_cypher()`
- [ ] Add `get_graph_service` to `app/dependencies.py`
- [ ] Write `app/api/v1/routes/query.py` and register it in `main.py`
- [ ] Start the server: `uvicorn app.main:app --reload`
- [ ] Open `http://localhost:8000/docs` — FastAPI auto-generates an interactive Swagger UI from your schemas
- [ ] Test `POST /api/v1/query` with `{"query": "MATCH (n) RETURN n LIMIT 5"}` and confirm results come back

> **Milestone:** You now have a complete, working, unauthenticated API. Verify this before adding security — it is much easier to debug a connection problem when you are not also debugging auth at the same time.

---

## Phase 3 — Security

> **Patterns: Guard / Policy Object · Middleware · Defense in Depth**

Security is not one thing bolted on at the end. It is a set of independent concerns that each address a different attack surface. **Defense in Depth** is the principle of layering multiple independent defences so that no single failure compromises the system. This phase has three tracks — implement them in order.

---

### Track A — Authentication: Who Are You?

Authentication answers: *is this caller allowed to talk to the API at all?*

Start with **API key auth** — it is stateless, simple to implement, and sufficient for server-to-server use (one service querying another).

The caller includes a secret string in the `X-API-Key` request header. Your API checks that string against the stored key. Match → proceed. No match → `HTTP 401 Unauthorized`.

**Critical detail — timing-safe comparison:**

Never use `==` to compare secrets. Python's string equality short-circuits — it returns `False` as soon as it finds the first mismatched character. An attacker who can make thousands of requests can measure how long each comparison takes and brute-force your key one character at a time. This is called a **timing attack**.

`hmac.compare_digest()` is designed to take the same amount of time regardless of where the strings differ:

```python
# app/security/auth.py
import hmac
from fastapi import Header, HTTPException, status
from app.config import settings

async def get_api_key(x_api_key: str = Header(...)):
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return x_api_key
```

Add `api_key: str = Depends(get_api_key)` to your route signature. FastAPI calls this before the route handler runs and returns `401` automatically if it raises.

**Tasks**
- [ ] Add `api_key: str` to `Settings` in `config.py` and add `API_KEY` to `.env`
- [ ] Write `app/security/auth.py` with the `get_api_key` dependency
- [ ] Add `Depends(get_api_key)` to the `/query` route
- [ ] Verify: requests without the header return `401`, requests with the correct key return `200`

---

### Track B — Query Validation: What Can You Ask?

Authentication checks if you are allowed in the door. Query validation checks what you are allowed to do once inside.

Consider: `MATCH (n) DETACH DELETE n` is a valid Cypher query that deletes every node in your graph. Without validation, any authenticated caller can run arbitrary graph operations.

The **Guard Pattern** (also called Policy Object) encapsulates a validation rule as a standalone, testable class. Instead of `if "DELETE" in query` checks scattered through your service, you write a `CypherQueryGuard` with a `validate()` method. The service calls it before touching the repository. Each rule is independently testable.

**The three rules to implement:**

**Rule 1 — Write keyword detection:** Reject queries containing `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`. This API is read-only by default.

**Rule 2 — Complexity limit:** Reject queries with more than N `MATCH` clauses (make N configurable). An unbounded traversal on a large graph can exhaust memory and CPU, acting as a denial-of-service from an authenticated user.

**Rule 3 — Parameterisation enforcement:** The `parameters` dict in the request exists so that dynamic values are passed separately from the query string — the Neo4j driver handles them safely. If a caller bakes dynamic values directly into the query string (like an f-string), they bypass this protection. This is the Cypher equivalent of SQL injection. Detect and reject queries that look like they contain interpolated values rather than `$param` placeholders.

```python
# app/security/query_guard.py
import re
from fastapi import HTTPException, status

WRITE_KEYWORDS = {"CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"}

class CypherQueryGuard:
    def __init__(self, max_match_clauses: int = 10):
        self._max_match = max_match_clauses

    def validate(self, query: str) -> None:
        self._check_no_write_keywords(query)
        self._check_complexity(query)

    def _check_no_write_keywords(self, query: str) -> None:
        upper = query.upper()
        for keyword in WRITE_KEYWORDS:
            if re.search(rf'\b{keyword}\b', upper):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Write operation '{keyword}' is not permitted on this endpoint.",
                )

    def _check_complexity(self, query: str) -> None:
        match_count = len(re.findall(r'\bMATCH\b', query.upper()))
        if match_count > self._max_match:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Query complexity limit exceeded ({match_count} MATCH clauses, max {self._max_match}).",
            )
```

Inject the guard into `GraphService.run_cypher()` — call `guard.validate(request.query)` before calling the repository.

**Tasks**
- [ ] Write `app/security/query_guard.py` with `CypherQueryGuard`
- [ ] Inject a `CypherQueryGuard` instance into `GraphService` and call `validate()` before `execute_read()`
- [ ] Unit test the guard: valid queries pass, write queries raise `403`, queries with too many MATCH clauses raise `403`

---

### Track C — Infrastructure-Level Protection

These defences operate at the network/middleware level and protect against abuse at scale.

**Rate Limiting:** Prevents a single caller from flooding the API. Even an authenticated user running expensive queries in a tight loop can exhaust the Neo4j connection pool. Add `slowapi` and apply a per-IP limit (e.g. 30 requests per minute) to the `/query` route. Make the limit a config variable.

**CORS (Cross-Origin Resource Sharing):** If this API is ever called from a browser, you need CORS headers. FastAPI's built-in `CORSMiddleware` handles this. Configure it with an explicit allowlist of origins rather than `allow_origins=["*"]` — the wildcard allows any website to call your API from a visitor's browser.

**Request ID Middleware:** Every request should be assigned a unique ID (a UUID) when it arrives. Attach it to all log lines produced during that request and return it in the response as `X-Request-ID`. When something goes wrong in production, a client can give you their Request ID and you can trace exactly what happened.

**Tasks**
- [ ] Install `slowapi` and configure rate limiting on `/query`; make the limit a config variable
- [ ] Add `CORSMiddleware` to `main.py` with an allowlisted origins config variable
- [ ] Write a middleware that generates a UUID `request_id` per request, stores it in `request.state`, and adds it to response headers

---

## Phase 4 — Testing

> **Patterns: Test Pyramid · Arrange–Act–Assert**

The **Test Pyramid** describes how to distribute testing effort:

```
        /\
       /  \     Few end-to-end tests (slow, fragile, expensive)
      /────\
     /      \   Some integration tests (medium speed, need infrastructure)
    /────────\
   /          \ Many unit tests (fast, no infrastructure needed)
  /────────────\
```

The pyramid shape reflects cost. Unit tests run in milliseconds with no external dependencies. Integration tests take seconds and need a running Neo4j. Build the base first.

**Arrange–Act–Assert** is the standard structure for a single test:
- **Arrange:** Set up inputs and mocks
- **Act:** Call the function under test
- **Assert:** Check the output

| Test | What it tests | How |
|---|---|---|
| Unit | `CypherQueryGuard`, `GraphService`, auth helpers | `pytest` + `pytest-mock`; mock the repo with a fake |
| Integration | Full HTTP request → response cycle | `httpx.AsyncClient` against the real FastAPI app |
| Contract | Response schema never breaks | Assert response keys and types in integration tests |

### Example Unit Test

```python
# tests/unit/test_query_guard.py
import pytest
from fastapi import HTTPException
from app.security.query_guard import CypherQueryGuard

guard = CypherQueryGuard(max_match_clauses=3)

def test_valid_read_query_passes():
    guard.validate("MATCH (n) RETURN n LIMIT 10")  # should not raise

def test_delete_query_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("MATCH (n) DETACH DELETE n")
    assert exc.value.status_code == 403

def test_too_many_match_clauses_raises_403():
    query = "MATCH (a) MATCH (b) MATCH (c) MATCH (d) RETURN a, b, c, d"
    with pytest.raises(HTTPException) as exc:
        guard.validate(query)
    assert exc.value.status_code == 403
```

### Tasks

- [ ] Write `tests/conftest.py` with an `async_client` fixture and a `mock_repo` fixture
- [ ] Unit test `CypherQueryGuard` — valid queries pass, write queries raise, complexity limit raises
- [ ] Unit test `GraphService.run_cypher()` — mock the repo to return two records, assert `row_count == 2` and `execution_time_ms > 0`
- [ ] Integration test: `POST /api/v1/query` with no `X-API-Key` returns `401`
- [ ] Integration test: `POST /api/v1/query` with valid key and `{"query": "MATCH (n) RETURN n LIMIT 1"}` returns `200` with correct schema

---

## Phase 5 — Observability & Documentation

> **Patterns: Structured Logging · OpenAPI-First Design**

**Structured Logging** means log output is machine-readable JSON rather than human-readable strings.

Instead of:
```
[INFO] Query executed in 42ms
```

You emit:
```json
{"event": "query_executed", "execution_time_ms": 42, "row_count": 7, "request_id": "a3f2..."}
```

Log aggregation tools (Datadog, Grafana Loki, Splunk) can filter, group, and alert on structured fields. `structlog` is the best Python library for this — it binds context (like `request_id`) to all log lines produced during a request.

**OpenAPI-First Design** means you treat the auto-generated `/docs` page as a first-class artifact. FastAPI generates it for free from your Pydantic schemas and route docstrings.

### Tasks

- [ ] Install `structlog` and configure it to emit pretty-printed output in development and JSON in production (based on `api_env`)
- [ ] Add a `structlog` log call inside `GraphService.run_cypher()` recording `execution_time_ms`, `row_count`, and `request_id`
- [ ] Add docstrings to all route functions — these appear as descriptions in the Swagger UI
- [ ] Set FastAPI app metadata in `main.py`: `title`, `description`, `version`
- [ ] Write `README.md`: setup steps, required env vars, how to run locally, how to run tests, auth flow

---

## Dependency Reference

```
# Runtime
fastapi             ^0.115
uvicorn[standard]   ^0.30
neo4j               ^5.24   (async driver included)
pydantic-settings   ^2.5
slowapi             ^0.1    (Phase 3C)
python-jose[cryptography] ^3.3  (Phase 3A JWT stretch goal)
structlog           ^24.4   (Phase 5)

# Dev / Test
pytest              ^8.3
pytest-asyncio      ^0.24
httpx               ^0.27
pytest-mock         ^3.14
```

---

## Design Pattern Reference

| Pattern | Where it appears | The problem it solves |
|---|---|---|
| Convention over Configuration | Project layout | Everyone knows where to look for things |
| Repository | `Neo4JAsyncGraphRepository` | Only one class ever talks to Neo4j |
| Factory | `lifespan` in `main.py` | One place constructs the driver; it is reused everywhere |
| Protocol / Interface | `RepositoryService` | Services depend on a contract, not a concrete class — enables test mocks |
| Dependency Injection | `Depends(get_graph_service)` | Objects receive what they need; they do not build it themselves |
| DTO | `CypherQueryRequest`, `CypherQueryResponse` | Strict, validated contracts at every layer boundary |
| Service Layer | `GraphService` | Business logic lives in one place, callable from routes, CLIs, or tests |
| Guard / Policy Object | `CypherQueryGuard` | Validation rules are encapsulated, composable, and independently testable |
| Middleware | CORS, rate limiting, request ID | Cross-cutting concerns applied uniformly to every request |
| Defense in Depth | Auth + guard + rate limiting + CORS | No single failure compromises the whole system |
| Test Pyramid | `tests/unit/`, `tests/integration/` | Most tests are fast and cheap; few are slow and expensive |
