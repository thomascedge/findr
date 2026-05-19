import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.db import Base, get_db
from app.core.security import hash_password
from app.models.models import User

# Use a separate in-memory SQLite DB for tests
# Switch to a test Postgres DB when you need PostGIS or upsert support
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async test client with DB override."""
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db():
    """Raw DB session for seeding test data directly."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db: AsyncSession):
    """A basic active user seeded directly into the DB."""
    user = User(
        username="testuser",
        email="test@test.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_2(db: AsyncSession):
    """A second active user for multi-user test scenarios."""
    user = User(
        username="testuser2",
        email="test2@test.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(client, test_user):
    """Auth headers for test_user — use in any protected route test."""
    response = await client.post("/api/v1/auth/token", data={
        "username": "testuser",
        "password": "password123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_2(client, test_user_2):
    """Auth headers for test_user_2."""
    response = await client.post("/api/v1/auth/token", data={
        "username": "testuser2",
        "password": "password123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
