import uuid

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_aws_settings():
    missing = []
    for name in [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "AWS_STORAGE_BUCKET",
    ]:
        if not getattr(settings, name, None):
            missing.append(name)
    if missing:
        raise ImproperlyConfigured(
            f"Missing AWS settings: {', '.join(missing)}"
        )

    return (
        settings.AWS_ACCESS_KEY_ID,
        settings.AWS_SECRET_ACCESS_KEY,
        settings.AWS_REGION,
        settings.AWS_STORAGE_BUCKET,
    )


def get_rekognition_client():
    access_key, secret_key, region, _ = get_aws_settings()
    return boto3.client(
        "rekognition",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def get_s3_client():
    access_key, secret_key, region, _ = get_aws_settings()
    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def get_collection_id():
    return getattr(settings, "AWS_REKOGNITION_COLLECTION", "bjj-members")


def get_bucket_name():
    _, _, _, bucket = get_aws_settings()
    return bucket


def build_s3_url(key):
    """Generate a signed URL for S3 object that's valid for 7 days."""
    s3 = get_s3_client()
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': get_bucket_name(), 'Key': key},
            ExpiresIn=604800  # 7 days
        )
        return url
    except Exception:
        # Fallback to public URL if signing fails
        bucket = get_bucket_name()
        region = settings.AWS_REGION
        if region == "us-east-1":
            return f"https://{bucket}.s3.amazonaws.com/{key}"
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def get_signed_s3_url(s3_key):
    """Generate a fresh signed URL for an S3 key (useful for templates to refresh expired URLs)."""
    if not s3_key:
        return None
    return build_s3_url(s3_key)


def ensure_collection():
    client = get_rekognition_client()
    collection_id = get_collection_id()
    try:
        client.create_collection(CollectionId=collection_id)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in ("ResourceAlreadyExistsException", "ResourceAlreadyExistsException"):
            raise
    return collection_id


def upload_image_to_s3(image_file, key):
    s3 = get_s3_client()
    image_file.seek(0)
    content_type = getattr(image_file, "content_type", "image/jpeg") or "image/jpeg"
    s3.upload_fileobj(
        image_file,
        get_bucket_name(),
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return build_s3_url(key)


def index_member_face(member, image_file):
    collection_id = ensure_collection()
    object_key = f"face-enrollments/member-{member.id}-{uuid.uuid4().hex}.jpg"
    image_url = upload_image_to_s3(image_file, object_key)
    rekognition = get_rekognition_client()
    response = rekognition.index_faces(
        CollectionId=collection_id,
        Image={"S3Object": {"Bucket": get_bucket_name(), "Name": object_key}},
        ExternalImageId=str(member.id),
        DetectionAttributes=["DEFAULT"],
        MaxFaces=1,
    )
    face_records = response.get("FaceRecords", [])
    if not face_records:
        raise ValueError("No face was detected in the uploaded image. Please upload a clear, front-facing photo.")
    face_id = face_records[0]["Face"]["FaceId"]
    return face_id, image_url, object_key


def search_faces_by_image(image_file, threshold=90, max_faces=20):
    collection_id = ensure_collection()
    object_key = f"face-attendance/{uuid.uuid4().hex}.jpg"
    upload_image_to_s3(image_file, object_key)
    rekognition = get_rekognition_client()
    response = rekognition.search_faces_by_image(
        CollectionId=collection_id,
        Image={"S3Object": {"Bucket": get_bucket_name(), "Name": object_key}},
        FaceMatchThreshold=threshold,
        MaxFaces=max_faces,
    )
    return response.get("FaceMatches", []), object_key
