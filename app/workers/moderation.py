import os
import logging
import boto3
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.workers.celery_app import celery
from app.models.models import UserPhoto, PhotoModerationTag, ModerationStatus, utcnow

LOG = logging.getLogger(__name__)

LOCALSTACK_URL = os.getenv("LOCALSTACK_URL")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
DATABASE_URL = os.getenv("SYNC_DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

rekognition = boto3.client(
    "rekognition",
    endpoint_url=LOCALSTACK_URL or None,
    region_name=AWS_REGION,
)


@celery.task(bind=True, max_retries=3)
def moderate_photo(self, photo_id: str, s3_key: str):
    """
    Calls AWS Rekognition to detect moderation labels on a photo.
    Writes tags to PhotoModerationTag and updates moderation_status.
    Retries up to 3 times on failure before marking status as 'failed'.
    """
    db = SessionLocal()

    try:
        response = rekognition.detect_moderation_labels(
            Image={
                "S3Object": {
                    "Bucket": S3_BUCKET,
                    "Name": s3_key
                }
            },
            MinConfidence=50
        )

        for label in response["ModerationLabels"]:
            category = label["Name"]
            confidence = label['Confidence']

            photo_moderation_tag_data = {
                "id": uuid.uuid4(),
                "photo_id": uuid.UUID(photo_id),
                "category": category,
                "confidence": confidence,
                "created_at": utcnow()
            }
            new_tag = PhotoModerationTag(**photo_moderation_tag_data)
            db.add(new_tag)
        db.commit()

        result = db.execute(select(UserPhoto).where(UserPhoto.id == uuid.UUID(photo_id)))
        photo = result.scalar_one_or_none()
        photo.moderation_status = ModerationStatus.COMPLETE
        db.commit()

        tag_count = len(response["ModerationLabels"])
        LOG.info(f'{tag_count} tags written for photo.')

    except Exception as e:
        LOG.error(f"Photo moderation failed with exception: {e}")
        if self.request.retries >= self.max_retries:
            photo = db.execute(select(UserPhoto).where(UserPhoto.id == uuid.UUID(photo_id))).scalar_one_or_none()
            if photo:
                photo.moderation_status = ModerationStatus.FAILED
                db.commit()
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()
