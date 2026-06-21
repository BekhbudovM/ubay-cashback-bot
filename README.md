# UBAY Cashback Starter — SQLite v2

Bu versiya Docker talab qilmaydi. Database oddiy `ubay_cashback.db` faylida saqlanadi.

## Ishga tushirish

```bash
cd Downloads/ubay-cashback-starter-sqlite-v2
cp .env.example .env
open .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.bot.main
```

`.env` ichiga BotFather bergan yangi tokenni qo'ying:

```env
BOT_TOKEN=YOUR_NEW_BOT_TOKEN_HERE
```

Agar terminalda `UBAY Cashback bot started...` chiqsa, bot ishlayapti.


## v4 update

- Bot endi shtrix-kodni Code128 PNG rasm ko'rinishida ham yuboradi.
- Kassada skaner bilan o'qish uchun shu rasm ishlatiladi.
