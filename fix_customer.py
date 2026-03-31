import asyncio, sys
sys.path.insert(0, '/app')

async def main():
    from common.database import AsyncSessionLocal
    from sqlalchemy import text
    from passlib.hash import bcrypt

    h = bcrypt.using(rounds=12).hash("Cliente2026!")

    async with AsyncSessionLocal() as db:
        # Check current state
        r = await db.execute(text("SELECT id, realm, email FROM users WHERE email = 'christian@yastubo.com'"))
        row = r.first()
        if row:
            print(f"BEFORE: id={row[0]} realm={row[1]}")
            await db.execute(
                text("UPDATE users SET password = :p, realm = 'customer' WHERE id = :id"),
                {"p": h, "id": row[0]}
            )
            await db.commit()
            print("UPDATED")
        else:
            print("USER NOT FOUND")

asyncio.run(main())
