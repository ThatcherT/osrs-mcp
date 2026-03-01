import httpx
from osrs_mcp.config import get_config

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Get shared httpx client with required User-Agent."""
    global _client
    if _client is None or _client.is_closed:
        config = get_config()
        _client = httpx.AsyncClient(
            headers={"User-Agent": config.user_agent},
            timeout=30.0,
            follow_redirects=True,
        )
    return _client
