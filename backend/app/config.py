from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OriginChain API"
    database_url: str = "sqlite:///./originchain.db"
    chain_adapter: str = "mock"
    solana_rpc_url: str = "https://api.devnet.solana.com"
    solana_program_id: str = "J6grB9Db5FjKYkGLWf4n81BZg75WEE9KVXbnq5XZBcg1"
    max_upload_bytes: int = 100 * 1024 * 1024
    request_timeout_seconds: float = 20.0
    auto_create_tables: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
