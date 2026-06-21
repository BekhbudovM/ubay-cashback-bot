from fastapi import FastAPI

from app.services.cashback import calculate_cashback, get_cashback_percent

app = FastAPI(title="UBAY Cashback API", version="0.1.0")


@app.get("/")
async def root():
    return {"service": "UBAY Cashback API", "status": "ok"}


@app.get("/cashback/calculate")
async def cashback_calculate(amount: int):
    return {
        "amount": amount,
        "percent": float(get_cashback_percent(amount)),
        "cashback": int(calculate_cashback(amount)),
    }


@app.post("/webhooks/regos")
async def regos_webhook(payload: dict):
    return {"received": True, "payload": payload}
