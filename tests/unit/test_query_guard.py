import pytest
from fastapi import HTTPException
from app.security.query_guard import CypherQueryGuard

guard = CypherQueryGuard(max_match_clauses=3)


# ---------------------------------------------------------------------------
# Rule 1 — write keyword detection
# ---------------------------------------------------------------------------

def test_valid_read_query_passes():
    guard.validate("MATCH (n) RETURN n LIMIT 10")


def test_delete_query_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("MATCH (n) DETACH DELETE n")
    assert exc.value.status_code == 403
    assert "DELETE" in exc.value.detail


def test_create_query_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("CREATE (n:Person {name: 'Alice'})")
    assert exc.value.status_code == 403


def test_merge_query_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("MERGE (n:Person {name: 'Alice'}) RETURN n")
    assert exc.value.status_code == 403


def test_set_query_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("MATCH (n) SET n.x = 1")
    assert exc.value.status_code == 403


def test_foreach_query_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("FOREACH (n IN nodes | SET n.visited = true)")
    assert exc.value.status_code == 403


def test_keyword_matching_is_case_insensitive():
    with pytest.raises(HTTPException):
        guard.validate("match (n) detach delete n")


# ---------------------------------------------------------------------------
# Rule 2 — complexity limit
# ---------------------------------------------------------------------------

def test_too_many_match_clauses_raises_403():
    query = "MATCH (a) MATCH (b) MATCH (c) MATCH (d) RETURN a, b, c, d"
    with pytest.raises(HTTPException) as exc:
        guard.validate(query)
    assert exc.value.status_code == 403
    assert "complexity" in exc.value.detail.lower()


def test_exactly_at_limit_passes():
    query = "MATCH (a) MATCH (b) MATCH (c) RETURN a, b, c"
    guard.validate(query)  # 3 MATCH clauses, limit is 3 — should not raise


# ---------------------------------------------------------------------------
# Rule 3 — no string interpolation
# ---------------------------------------------------------------------------

def test_interpolated_value_raises_403():
    with pytest.raises(HTTPException) as exc:
        guard.validate("MATCH (n {name: {user_input}}) RETURN n")
    assert exc.value.status_code == 403
    assert "interpolated" in exc.value.detail.lower()


def test_dollar_param_placeholder_passes():
    guard.validate("MATCH (n {name: $name}) RETURN n")


def test_cypher_map_literal_passes():
    # Map literals contain a colon and should not be flagged
    guard.validate("MATCH (n) WHERE n.props = {key: 'value'} RETURN n")
