import json
from pathlib import Path
from pydantic import BaseModel, Field


class Config(BaseModel):
    username: str = ""
    accounts: list[str] = []
    account_types: dict[str, str] = {}
    user_agent: str = "osrs-mcp/0.1.0 - OSRS MCP Server"


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is not None:
        return _config

    config_path = Path(__file__).parent.parent.parent / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            _config = Config(**json.load(f))
    else:
        _config = Config()
    return _config
