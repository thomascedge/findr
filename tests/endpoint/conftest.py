from dotenv import load_dotenv
load_dotenv()

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db
from app.core.security import hash_password
from app.models.models import User, Chat, Message, UserPhoto, ModerationStatus

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Default date of birth for test users — 25 years old (passes 18+ check)
DEFAULT_DOB = datetime.now(timezone.utc) - timedelta(days=25 * 365)


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
        date_of_birth=DEFAULT_DOB,
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
        date_of_birth=DEFAULT_DOB,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(client, test_user):
    """Auth headers for test_user."""
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


@pytest_asyncio.fixture
async def test_photo(db: AsyncSession, test_user: User):
    """Factory fixture to seed a UserPhoto with customizable fields.

    Usage:
        photo = await test_photo()
        photo = await test_photo(user=test_user_2, display_order=2)
        photo = await test_photo(moderation_status=ModerationStatus.COMPLETE)
        photo = await test_photo(deleted_at=utcnow())
    """
    async def _factory(
        user=None,
        display_order=1,
        moderation_status=ModerationStatus.PENDING,
        deleted_at=None,
    ):
        owner = user or test_user
        photo_id = uuid.uuid4()
        user_photo = UserPhoto(
            id=photo_id,
            user_id=owner.id,
            s3_key=f'photos/{owner.id}/{photo_id}.webp',
            display_order=display_order,
            moderation_status=moderation_status,
            deleted_at=deleted_at,
        )
        db.add(user_photo)
        await db.commit()
        await db.refresh(user_photo)
        return user_photo
    return _factory


# ── Sync DB fixture for worker tests ──────────────────────────────────────────

SYNC_TEST_DATABASE_URL = "sqlite:///./test_sync.db"
sync_engine = create_engine(SYNC_TEST_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine)


@pytest.fixture
def db_sync():
    """Sync DB session for testing Celery worker tasks directly."""
    Base.metadata.create_all(sync_engine)
    session = SyncSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(sync_engine)

@pytest.fixture
def test_user_sync(db_sync):
    """Sync version of test_user for worker tests."""
    from app.models.models import User
    user = User(
        username="testuser",
        email="test@test.com",
        hashed_password=hash_password("password123"),
        date_of_birth=DEFAULT_DOB,
        is_active=True,
    )
    db_sync.add(user)
    db_sync.commit()
    db_sync.refresh(user)
    return user

@pytest.fixture
def test_message_sync(db_sync, test_user_sync):
    """Seeds a Chat and Message for worker tests. Pass deleted_at to control retention."""
    def _factory(deleted_at=None):
        chat = Chat(is_group=False)
        db_sync.add(chat)
        db_sync.commit()
        db_sync.refresh(chat)

        message = Message(
            chat_id=chat.id,
            sender_id=test_user_sync.id,
            body="test message body",
            deleted_at=deleted_at,
        )
        db_sync.add(message)
        db_sync.commit()
        db_sync.refresh(message)
        return message

    return _factory

@pytest.fixture
def test_photo_sync(db_sync, test_user_sync):
    """Seeds a User photo for worker tests."""
    photo_id = uuid.uuid4()

    user_photo = UserPhoto(
        id=photo_id,
        user_id=test_user_sync.id,
        s3_key=f'photos/{test_user_sync.id}/{photo_id}.webp',
        display_order=1,
    )
    db_sync.add(user_photo)
    db_sync.commit()
    db_sync.refresh(user_photo)
    return user_photo
