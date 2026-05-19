from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    # This is a FastAPI dependency — injected into route handlers via Depends(get_db)
    # It opens a session, yields it to the route, then closes it when the request is done
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    # Creates all tables defined in models.py on app startup
    # Later you'll replace this with Alembic migrations
    from app.models import models  # noqa — ensures models are registered with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
