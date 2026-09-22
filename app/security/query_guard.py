import re
from fastapi import HTTPException, status

WRITE_KEYWORDS = {"CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "FOREACH"}


class CypherQueryGuard:
    def __init__(self, max_match_clauses: int = 10):
        self._max_match = max_match_clauses

    def validate(self, query: str) -> None:
        self._check_no_write_keywords(query)
        self._check_complexity(query)
        self._check_no_string_interpolation(query)

    def _check_no_write_keywords(self, query: str) -> None:
        upper = query.upper()
        for keyword in WRITE_KEYWORDS:
            if re.search(rf"\b{keyword}\b", upper):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Write operation '{keyword}' is not permitted on this endpoint.",
                )

    def _check_complexity(self, query: str) -> None:
        match_count = len(re.findall(r"\bMATCH\b", query.upper()))
        if match_count > self._max_match:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Query complexity limit exceeded "
                    f"({match_count} MATCH clauses, max {self._max_match})."
                ),
            )

    def _check_no_string_interpolation(self, query: str) -> None:
        """Reject queries that contain Python f-string-style interpolations like
        {variable} instead of proper $param placeholders.  Cypher map literals
        (e.g. {name: 'Alice'}) are safe because they always contain a colon.
        """
        if re.search(r"\{[a-zA-Z_]\w*\}", query):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Query appears to contain interpolated values. "
                    "Use $param placeholders instead."
                ),
            )
