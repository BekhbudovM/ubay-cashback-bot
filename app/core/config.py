from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./ubay_cashback.db"
    regos_api_base_url: str = "https://api.regos.uz"
    regos_api_token: str = ""
    admin_ids: str = ""  # comma-separated telegram IDs

    def get_admin_ids(self) -> List[int]:
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
