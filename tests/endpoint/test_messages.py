import pytest
from httpx import AsyncClient


# ── Send message ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_dm_success(client: AsyncClient, auth_headers, test_user_2):
    """Sending a DM to an existing user creates the message and a new chat."""
    response = await client.post(
        f"/api/v1/messages/send?recipient_id={test_user_2.id}",
        json={"body": "Hello!"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["body"] == "Hello!"


@pytest.mark.asyncio
async def test_send_dm_reuses_existing_chat(client: AsyncClient, auth_headers, test_user_2):
    """Sending a second DM to the same user reuses the existing chat."""
    await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    response = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Again!"}, headers=auth_headers)

    assert response.status_code == 201
    # Both messages share the same chat_id
    first = (await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "One"}, headers=auth_headers)).json()
    second = (await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Two"}, headers=auth_headers)).json()
    assert first["chat_id"] == second["chat_id"]


@pytest.mark.asyncio
async def test_send_message_no_recipient_or_chat(client: AsyncClient, auth_headers):
    """Sending a message without recipient_id or chat_id returns 400."""
    response = await client.post("/api/v1/messages/send", json={"body": "Hello!"}, headers=auth_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_send_message_both_recipient_and_chat(client: AsyncClient, auth_headers, test_user_2):
    """Providing both recipient_id and chat_id returns 400."""
    response = await client.post(
        f"/api/v1/messages/send?recipient_id={test_user_2.id}&chat_id=00000000-0000-0000-0000-000000000000",
        json={"body": "Hello!"},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_send_message_to_inactive_user(client: AsyncClient, auth_headers, test_user_2, db):
    """Sending a DM to a deactivated user returns 404."""
    test_user_2.is_active = False
    await db.commit()

    response = await client.post(
        f"/api/v1/messages/send?recipient_id={test_user_2.id}",
        json={"body": "Hello!"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message_empty_body(client: AsyncClient, auth_headers, test_user_2):
    """Sending a message with empty body returns 422."""
    response = await client.post(
        f"/api/v1/messages/send?recipient_id={test_user_2.id}",
        json={"body": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_message_body_too_long(client: AsyncClient, auth_headers, test_user_2):
    """Sending a message over 2000 chars returns 422."""
    response = await client.post(
        f"/api/v1/messages/send?recipient_id={test_user_2.id}",
        json={"body": "a" * 2001},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ── Get thread ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_thread_success(client: AsyncClient, auth_headers, test_user_2):
    """A user can retrieve their message thread with another user."""
    await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)

    response = await client.get(f"/api/v1/messages/thread?recipient_id={test_user_2.id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_thread_no_messages(client: AsyncClient, auth_headers, test_user_2):
    """Getting a thread that doesn't exist yet returns 404."""
    response = await client.get(f"/api/v1/messages/thread?recipient_id={test_user_2.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_thread_excludes_deleted(client: AsyncClient, auth_headers, test_user_2):
    """Soft-deleted messages do not appear in the thread."""
    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    await client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers)

    response = await client.get(f"/api/v1/messages/thread?recipient_id={test_user_2.id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0


# ── Edit message ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_message_success(client: AsyncClient, auth_headers, test_user_2):
    """A user can edit their own message."""
    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    response = await client.patch(f"/api/v1/messages/{message_id}", json={"body": "Updated!"}, headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_edit_someone_elses_message(client: AsyncClient, auth_headers, auth_headers_2, test_user_2, test_user):
    """Editing another user's message returns 403."""
    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    response = await client.patch(f"/api/v1/messages/{message_id}", json={"body": "Hacked!"}, headers=auth_headers_2)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_edit_deleted_message(client: AsyncClient, auth_headers, test_user_2):
    """Editing a soft-deleted message should not succeed."""
    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    await client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers)
    response = await client.patch(f"/api/v1/messages/{message_id}", json={"body": "Updated!"}, headers=auth_headers)
    assert response.status_code == 400


# ── Delete message ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_message_success(client: AsyncClient, auth_headers, test_user_2, db):
    """Deleting a message sets deleted_at and returns 200."""
    from app.models.models import Message
    from sqlalchemy import select

    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    response = await client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers)
    assert response.status_code == 200

    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one()
    assert message.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_someone_elses_message(client: AsyncClient, auth_headers, auth_headers_2, test_user_2):
    """Deleting another user's message returns 403."""
    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    response = await client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers_2)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_already_deleted_message(client: AsyncClient, auth_headers, test_user_2):
    """Deleting an already deleted message should return 400."""
    send_resp = await client.post(f"/api/v1/messages/send?recipient_id={test_user_2.id}", json={"body": "Hello!"}, headers=auth_headers)
    message_id = send_resp.json()["id"]

    await client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers)
    response = await client.delete(f"/api/v1/messages/{message_id}", headers=auth_headers)
    assert response.status_code == 400
