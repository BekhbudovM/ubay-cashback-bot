from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./ubay_cashback.db"
    regos_api_base_url: str = "https://api.regos.uz"
    regos_api_token: str = ""
    admin_ids: str = ""  # comma-separated telegram IDs

    # REGOS integration (https://docs.regos.uz/ru/api)
    # Endpoint: https://integration.regos.uz/gateway/out/{integration_key}/v1
    regos_endpoint: str = ""
    regos_connected_integration_id: str = ""  # webhook source verification
    regos_customer_group_id: int = 1
    regos_card_group_id: int = 1
    regos_barcode_type_id: int = 1
    regos_promo_id: int = 1

    # Evening seller sales report to admins, Tashkent time "HH:MM" ("" disables it)
    seller_report_time: str = "22:10"

    def get_admin_ids(self) -> List[int]:
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
