class RegosClient:
    async def create_customer(self, full_name, phone):
        return {"status": "stub", "regos_customer_id": None}

    async def create_card(self, customer_id, barcode_value):
        return {"status": "stub", "regos_card_id": None}

    async def get_balance(self, card_id):
        return {"status": "stub", "balance": 0}

    async def add_cashback(self, card_id, amount, document_uuid):
        return {"status": "stub"}

    async def spend_cashback(self, card_id, amount, document_uuid):
        return {"status": "stub"}
