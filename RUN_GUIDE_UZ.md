# UBAY Cashback Bot — Juda sodda ishga tushirish

## 1. Papkaga kiring

```bash
cd Downloads/ubay-cashback-starter-sqlite-v2
```

## 2. `.env` yarating

```bash
cp .env.example .env
```

## 3. `.env` oching

```bash
open .env
```

`BOT_TOKEN=PUT_YOUR_NEW_BOT_TOKEN_HERE` joyiga BotFather tokenini qo'ying.

## 4. Python muhit yarating

```bash
python3 -m venv .venv
```

## 5. Muhitni yoqing

```bash
source .venv/bin/activate
```

## 6. Kutubxonalarni o'rnating

```bash
pip install -r requirements.txt
```

## 7. Botni ishga tushiring

```bash
python -m app.bot.main
```

## 8. Telegramda test qiling

`@ubayuzbekistanbot` ga kiring va `/start` bosing.
