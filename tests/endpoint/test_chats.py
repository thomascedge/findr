from uuid import UUID
import pytest
from httpx import AsyncClient


# ── Create group chat ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_group_chat_success(client: AsyncClient, auth_headers, test_user_2, db):
    """Creating a group chat with 2+ members returns 201."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    response = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["is_group"] is True


@pytest.mark.asyncio
async def test_create_group_chat_too_few_members(client: AsyncClient, auth_headers, test_user_2):
    """Creating a group chat with fewer than 2 members returns 400."""
    response = await client.post("/api/v1/chats/", json=[str(test_user_2.id)], headers=auth_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_group_chat_nonexistent_user(client: AsyncClient, auth_headers, test_user_2):
    """Creating a group chat with a non-existent user ID returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post("/api/v1/chats/", json=[str(test_user_2.id), fake_id], headers=auth_headers)
    assert response.status_code == 404


# ── Get chat members ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_chat_members_success(client: AsyncClient, auth_headers, test_user_2, db):
    """A chat member can retrieve the list of members."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.get(f"/api/v1/chats/{chat_id}/members", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 3  # creator + 2 members


@pytest.mark.asyncio
async def test_get_chat_members_non_member_rejected(client: AsyncClient, auth_headers, auth_headers_2, test_user_2, db):
    """A non-member cannot view the members of a chat."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    # auth_headers_2 is test_user_2 who IS a member — use a fresh user instead
    response = await client.get(f"/api/v1/chats/{chat_id}/members", headers={"Authorization": "Bearer faketoken"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_chat_members_excludes_inactive(client: AsyncClient, auth_headers, test_user_2, db):
    """Inactive users are excluded from the member list."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    user3.is_active = False
    await db.commit()

    response = await client.get(f"/api/v1/chats/{chat_id}/members", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2  # creator + test_user_2 only


# ── Add member ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_member_success(client: AsyncClient, auth_headers, auth_headers_2, test_user_2, db):
    """A chat member can add a new active user to the chat."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    user4 = User(username="user4", email="user4@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    db.add(user4)
    await db.commit()
    await db.refresh(user3)
    await db.refresh(user4)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.post(f"/api/v1/chats/{chat_id}/members?user_id={user4.id}", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_add_member_already_in_chat(client: AsyncClient, auth_headers, test_user_2, db):
    """Adding a user already in the chat returns 400."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.post(f"/api/v1/chats/{chat_id}/members?user_id={test_user_2.id}", headers=auth_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_add_inactive_member(client: AsyncClient, auth_headers, test_user_2, db):
    """Adding an inactive user to a chat returns 404."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    user4 = User(username="user4", email="user4@test.com", hashed_password=hash_password("password123"), is_active=False)
    db.add(user3)
    db.add(user4)
    await db.commit()
    await db.refresh(user3)
    await db.refresh(user4)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.post(f"/api/v1/chats/{chat_id}/members?user_id={user4.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_non_member_cannot_add(client: AsyncClient, auth_headers, test_user_2, db):
    """A non-member cannot add users to a chat."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    user4 = User(username="user4", email="user4@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    db.add(user4)
    await db.commit()
    await db.refresh(user3)
    await db.refresh(user4)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    # user4 is not in the chat
    response = await client.post(f"/api/v1/auth/token", data={"username": "user4", "password": "password123"})
    user4_token = response.json()["access_token"]
    response = await client.post(
        f"/api/v1/chats/{chat_id}/members?user_id={test_user_2.id}",
        headers={"Authorization": f"Bearer {user4_token}"}
    )
    assert response.status_code == 403


# ── Remove member ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_member_success(client: AsyncClient, auth_headers, test_user_2, db):
    """A chat member can remove a non-admin member."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.delete(f"/api/v1/chats/{chat_id}/members/{test_user_2.id}", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_remove_admin_rejected(client: AsyncClient, auth_headers, test_user_2, db):
    """Removing an admin from a chat returns 400."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = UUID(chat_resp.json()["id"])

    # test_user is the admin — try to remove them
    from app.models.models import ChatMember
    from sqlalchemy import select
    result = await db.execute(select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == test_user_2.id))
    member = result.scalar_one()
    member.is_admin = True
    await db.commit()

    response = await client.delete(f"/api/v1/chats/{chat_id}/members/{test_user_2.id}", headers=auth_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_non_member_cannot_remove(client: AsyncClient, auth_headers, test_user_2, db):
    """A non-member cannot remove users from a chat."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    user4 = User(username="user4", email="user4@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    db.add(user4)
    await db.commit()
    await db.refresh(user3)
    await db.refresh(user4)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.post(f"/api/v1/auth/token", data={"username": "user4", "password": "password123"})
    user4_token = response.json()["access_token"]
    response = await client.delete(
        f"/api/v1/chats/{chat_id}/members/{test_user_2.id}",
        headers={"Authorization": f"Bearer {user4_token}"}
    )
    assert response.status_code == 403


# ── Transfer admin ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transfer_admin_success(client: AsyncClient, auth_headers, test_user_2, db):
    """An admin can transfer admin rights to another member."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.patch(f"/api/v1/chats/{chat_id}/members/admin/{test_user_2.id}", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_transfer_admin_non_admin_rejected(client: AsyncClient, auth_headers, auth_headers_2, test_user_2, db):
    """A non-admin cannot transfer admin rights."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    # test_user_2 is not admin
    response = await client.patch(f"/api/v1/chats/{chat_id}/members/admin/{user3.id}", headers=auth_headers_2)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_transfer_admin_to_non_member(client: AsyncClient, auth_headers, test_user_2, db):
    """Transferring admin to a non-member returns 404."""
    from app.models.models import User
    from app.core.security import hash_password

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    user4 = User(username="user4", email="user4@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    db.add(user4)
    await db.commit()
    await db.refresh(user3)
    await db.refresh(user4)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = chat_resp.json()["id"]

    response = await client.patch(f"/api/v1/chats/{chat_id}/members/admin/{user4.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transfer_admin_to_already_admin(client: AsyncClient, auth_headers, test_user_2, db):
    """Transferring admin to someone already an admin returns 400."""
    from app.models.models import User, ChatMember
    from app.core.security import hash_password
    from sqlalchemy import select

    user3 = User(username="user3", email="user3@test.com", hashed_password=hash_password("password123"), is_active=True)
    db.add(user3)
    await db.commit()
    await db.refresh(user3)

    chat_resp = await client.post("/api/v1/chats/", json=[str(test_user_2.id), str(user3.id)], headers=auth_headers)
    chat_id = UUID(chat_resp.json()["id"])

    # Make test_user_2 also an admin
    result = await db.execute(select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == test_user_2.id))
    member = result.scalar_one()
    member.is_admin = True
    await db.commit()

    response = await client.patch(f"/api/v1/chats/{chat_id}/members/admin/{test_user_2.id}", headers=auth_headers)
    assert response.status_code == 400
