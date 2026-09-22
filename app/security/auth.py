import hmac
from fastapi import Header, HTTPException, status
from app.config import settings


async def get_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate the X-API-Key request header using a timing-safe comparison.

    Returning a 401 for both missing and wrong keys avoids leaking information
    about which headers the API accepts.
    """
    _UNAUTHORIZED = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
    )
    if x_api_key is None:
        raise _UNAUTHORIZED
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise _UNAUTHORIZED
    return x_api_key
