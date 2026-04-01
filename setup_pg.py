"""Create all tables in PostgreSQL from SQLAlchemy models, then import data."""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from common.config import settings
from common.models import Base  # noqa: F401 – triggers all model imports


async def main() -> None:
    print(f"Connecting to: {settings.db_url}")
    engine = create_async_engine(settings.db_url, echo=False)

    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Done! Tables created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
