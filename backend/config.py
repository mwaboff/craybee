from functools import lru_cache
from pathlib import Path

from platformdirs import user_data_dir
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAYBEE_", env_file=".env", extra="ignore")

    app_name: str = "craybee"
    debug: bool = False

    # Loopback only. This process can spawn agent work; do not expose it to the LAN.
    host: str = "127.0.0.1"
    port: int = 8000

    data_dir: Path = Path(user_data_dir("craybee", "aboff"))

    @property
    def database_url(self) -> str:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.data_dir / 'craybee.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
