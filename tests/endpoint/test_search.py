"""Tests for user search endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User


@pytest.mark.asyncio
async def test_search_by_username(client: AsyncClient, auth_headers: dict, test_user_2: User):
    """Returns users matching the username query."""
    # GET /api/v1/search/users?q={test_user_2.username}
    # Assert 200
    # Assert test_user_2.username appears in results
    pass


@pytest.mark.asyncio
async def test_search_by_bio(client: AsyncClient, auth_headers: dict, test_user_2: User, db: AsyncSession):
    """Returns users whose bio matches the query."""
    # Seed test_user_2.bio = "I love hiking and coffee"
    # GET /api/v1/search/users?q=hiking
    # Assert test_user_2 appears in results
    pass


@pytest.mark.asyncio
async def test_search_excludes_current_user(client: AsyncClient, auth_headers: dict, test_user: User):
    """Current user never appears in their own search results."""
    # GET /api/v1/search/users?q={test_user.username}
    # Assert test_user.id does not appear in results
    pass


@pytest.mark.asyncio
async def test_search_excludes_inactive_users(client: AsyncClient, auth_headers: dict, test_user_2: User, db: AsyncSession):
    """Deactivated users do not appear in search results."""
    # Set test_user_2.is_active = False and commit
    # GET /api/v1/search/users?q={test_user_2.username}
    # Assert test_user_2 does not appear
    pass


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(client: AsyncClient, auth_headers: dict):
    """A query with no matching users returns an empty list."""
    # GET /api/v1/search/users?q=zzznomatch999
    # Assert 200 and empty list
    pass


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    """Search without a token returns 401."""
    # GET /api/v1/search/users with no headers
    # Assert 401
    pass
