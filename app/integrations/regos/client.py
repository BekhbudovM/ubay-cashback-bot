"""REGOS API client.

Endpoint format: https://integration.regos.uz/gateway/out/{integration_key}/v1/{Method}
All requests are POST with JSON body. Response: {"ok": bool, "result": ...}
"""

import aiohttp

from app.core.config import settings


class RegosError(Exception):
    def __init__(self, error_code, description):
        self.error_code = error_code
        self.description = description
        super().__init__(f"REGOS error {error_code}: {description}")


class RegosClient:
    @property
    def base_url(self) -> str:
        return settings.regos_endpoint.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(settings.regos_endpoint)

    async def _post(self, method: str, payload: dict) -> dict:
        url = f"{self.base_url}/{method}"
        headers = {"Content-Type": "application/json;charset=utf-8"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json(content_type=None)

        if not data.get("ok"):
            result = data.get("result") or {}
            raise RegosError(result.get("error"), result.get("description"))
        return data["result"]

    async def create_customer(self, full_name: str, phone: str) -> int:
        parts = full_name.strip().split(maxsplit=1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        result = await self._post("retailcustomer/add", {
            "group_id": settings.regos_customer_group_id,
            "first_name": first_name,
            "last_name": last_name,
            "main_phone": phone,
            "description": "UBAY Telegram bot",
        })
        return result["new_id"]

    async def create_card(self, customer_id: int, barcode_value: str) -> int:
        result = await self._post("retailcard/add", {
            "group_id": settings.regos_card_group_id,
            "customer_id": customer_id,
            "barcode_value": barcode_value,
            "barcode_type_id": settings.regos_barcode_type_id,
            "promo_id": settings.regos_promo_id,
            "unlimited": True,
            "enabled": True,
        })
        return result["new_id"]

    async def get_balance(self, card_id: int) -> float:
        result = await self._post("retailcard/getbalance", {
            "card_id": card_id,
            "promo_id": settings.regos_promo_id,
        })
        return float(result["value"])

    async def add_cashback(self, card_id: int, amount, description: str = "UBAY cashback") -> int:
        result = await self._post("promobonus/createmanualincomeoperation", {
            "card_id": card_id,
            "promo_id": settings.regos_promo_id,
            "value": float(amount),
            "description": description,
        })
        return result.get("row_affected", 0)

    async def get_cheque(self, uuid: str):
        result = await self._post("doccheque/get", {"uuids": [uuid]})
        if isinstance(result, list):
            return result[0] if result else None
        return None


regos_client = RegosClient()
