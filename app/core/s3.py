import os
import boto3

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL")

s3_client = boto3.client(
    "s3", endpoint_url=LOCALSTACK_URL or None, region_name=AWS_REGION
)

ses_client = boto3.client(
    "ses", endpoint_url=LOCALSTACK_URL or None, region_name=AWS_REGION
)


def upload_photo(file_bytes: bytes, s3_key: str) -> str:
    """Uploads a photo to S3 and returns the s3_key."""
    s3_client.put_object(
        Bucket=S3_BUCKET, Key=s3_key, Body=file_bytes, ContentType="image/webp"
    )

    return s3_key


def get_photo_url(s3_key: str) -> str:
    """Returns a presigned URL for a photo — valid for 1 hour."""
    response = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": S3_BUCKET, "Key": s3_key}, ExpiresIn=3600
    )

    return response
