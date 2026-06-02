import io
import uuid
import pytest
from unittest.mock import patch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, UserPhoto, ModerationStatus, utcnow

# ── Helpers ───────────────────────────────────────────────────────────────────


def _fake_image_bytes(img_size=(1, 1)) -> bytes:
    """Returns minimal valid JPEG bytes for upload testing."""
    from PIL import Image
    import io

    img = Image.new("RGB", img_size, color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _mock_upload():
    """Patches upload_photo so no real S3 call is made."""
    return patch(
        "app.api.routes.photos.upload_photo", return_value="photos/test/test.webp"
    )


def _mock_moderation():
    """Patches moderate_photo.delay so no real Celery task is queued."""
    return patch("app.api.routes.photos.moderate_photo")


# ── Upload ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_photo_success(
    client: AsyncClient, auth_headers, test_user, db: AsyncSession
):
    """A user can upload a valid image — returns 201 with photo_id."""
    buf = io.BytesIO(_fake_image_bytes())

    with _mock_upload(), _mock_moderation():
        response = await client.post(
            "/api/v1/photos/",
            files={"file": ("test.jpg", buf, "image/jpeg")},
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert "photo_id" in response.json()

    photo_id = uuid.UUID(response.json()["photo_id"])
    result = await db.execute(select(UserPhoto).where(UserPhoto.id == photo_id))

    photo = result.scalar_one_or_none()
    assert photo is not None
    assert photo.moderation_status == ModerationStatus.PENDING


@pytest.mark.asyncio
async def test_upload_photo_exceeds_limit(
    client: AsyncClient, auth_headers, db: AsyncSession
):
    """Uploading a 4th photo when 3 already exist returns 400."""
    # Seed 3 UserPhoto rows directly in DB for test_user
    # Attempt a 4th upload
    # Assert 400
    buf = io.BytesIO(_fake_image_bytes())

    for _ in range(3):
        with _mock_upload(), _mock_moderation():
            response = await client.post(
                "/api/v1/photos/",
                files={"file": ("test.jpg", buf, "image/jpeg")},
                headers=auth_headers,
            )
        assert response.status_code == 201
        assert "photo_id" in response.json()

    with _mock_upload(), _mock_moderation():
        response = await client.post(
            "/api/v1/photos/",
            files={"file": ("test.jpg", buf, "image/jpeg")},
            headers=auth_headers,
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_photo_too_large(client: AsyncClient, auth_headers):
    """Uploading a file larger than 10MB returns 413."""
    # Send bytes larger than 10 * 1024 * 1024
    # Assert 413
    buf = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1))

    with _mock_upload(), _mock_moderation():
        response = await client.post(
            "/api/v1/photos/",
            files={"file": ("test.jpg", buf, "image/jpeg")},
            headers=auth_headers,
        )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_photo_unauthenticated(client: AsyncClient):
    """Uploading without a token returns 401."""
    # POST to /api/v1/photos/ with no auth headers
    # Assert 401
    buf = io.BytesIO(_fake_image_bytes())

    with _mock_upload(), _mock_moderation():
        response = await client.post(
            "/api/v1/photos/",
            files={"file": ("test.jpg", buf, "image/jpeg")},
        )
    assert response.status_code == 401


# ── Delete ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_photo_success(
    client: AsyncClient, auth_headers, test_photo, db: AsyncSession
):
    """A user can soft delete their own photo."""
    user_photo = await test_photo()

    response = await client.delete(
        f"/api/v1/photos/{user_photo.id}", headers=auth_headers
    )
    assert response.status_code == 200

    await db.refresh(user_photo)
    assert user_photo.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_photo_not_owner(
    client: AsyncClient, auth_headers, auth_headers_2, test_user_2, test_photo
):
    """A user cannot delete another user's photo."""
    user_photo = await test_photo(user=test_user_2)

    response = await client.delete(
        f"/api/v1/photos/{user_photo.id}", headers=auth_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_photo_not_found(client: AsyncClient, auth_headers):
    """Deleting a non-existent photo returns 404."""
    photo_id = uuid.uuid4()
    response = await client.delete(f"/api/v1/photos/{photo_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_primary_photo_clears_primary(
    client: AsyncClient, auth_headers, test_user, test_photo, db: AsyncSession
):
    """Deleting a user's primary photo clears primary_photo_id on the user."""
    user_photo = await test_photo()

    user = await db.get(User, test_user.id)
    user.primary_photo_id = user_photo.id
    await db.commit()

    response = await client.delete(
        f"/api/v1/photos/{user_photo.id}", headers=auth_headers
    )
    assert response.status_code == 200

    db.expire_all()
    await db.refresh(user)
    assert user.primary_photo_id is None


# ── Set primary ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_primary_photo_success(
    client: AsyncClient, auth_headers, test_user, test_photo, db: AsyncSession
):
    """A user can set a moderation-complete photo as their primary."""
    user_photo = await test_photo(moderation_status=ModerationStatus.COMPLETE)
    photo_id = user_photo.id

    response = await client.patch(
        f"/api/v1/photos/{photo_id}/primary", headers=auth_headers
    )
    assert response.status_code == 200

    db.expire_all()
    await db.refresh(test_user)
    assert test_user.primary_photo_id == photo_id


@pytest.mark.asyncio
async def test_set_primary_photo_pending(client: AsyncClient, auth_headers, test_photo):
    """A photo with moderation_status=PENDING cannot be set as primary."""
    user_photo = await test_photo()

    response = await client.patch(
        f"/api/v1/photos/{user_photo.id}/primary", headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_set_primary_photo_not_owner(
    client: AsyncClient, auth_headers, auth_headers_2, test_user_2, test_photo
):
    """A user cannot set another user's photo as their primary."""
    user_photo = await test_photo(user=test_user_2)

    response = await client.patch(
        f"/api/v1/photos/{user_photo.id}/primary", headers=auth_headers
    )
    assert response.status_code == 403


# ── Update order ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_photo_order_success(
    client: AsyncClient, auth_headers, test_photo, db: AsyncSession
):
    """A user can update the display order of their photo."""
    user_photo = await test_photo()

    response = await client.patch(
        f"/api/v1/photos/{user_photo.id}/order?display_order=2", headers=auth_headers
    )
    assert response.status_code == 200

    await db.refresh(user_photo)
    assert user_photo.display_order == 2


@pytest.mark.asyncio
async def test_update_photo_order_not_owner(
    client: AsyncClient, auth_headers, auth_headers_2, test_user_2, test_photo
):
    """A user cannot update another user's photo order."""
    user_photo = await test_photo(user=test_user_2)

    response = await client.patch(
        f"/api/v1/photos/{user_photo.id}/order?display_order=2", headers=auth_headers
    )
    assert response.status_code == 403


# ── Get photos ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_photos_success(client: AsyncClient, auth_headers, test_photo):
    """Returns all active photos for the current user ordered by display_order."""
    await test_photo(display_order=1)
    await test_photo(display_order=2)

    response = await client.get("/api/v1/photos/", headers=auth_headers)
    assert response.status_code == 200
    photos = response.json()
    assert len(photos) == 2
    assert photos[0]["display_order"] == 1
    assert photos[1]["display_order"] == 2


@pytest.mark.asyncio
async def test_get_user_photos_excludes_deleted(
    client: AsyncClient, auth_headers, test_photo
):
    """Soft-deleted photos do not appear in the list."""
    await test_photo(deleted_at=utcnow())
    await test_photo(display_order=2)

    response = await client.get("/api/v1/photos/", headers=auth_headers)
    assert response.status_code == 200
    photos = response.json()
    assert len(photos) == 1


@pytest.mark.asyncio
async def test_get_user_photos_empty(client: AsyncClient, auth_headers):
    """Returns empty list when user has no photos."""
    response = await client.get("/api/v1/photos/", headers=auth_headers)
    assert response.status_code == 200
    photos = response.json()
    assert len(photos) == 0
