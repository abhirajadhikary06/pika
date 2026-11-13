"""S3-compatible object storage client for persistent ticket attachments."""
import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=current_app.config["AWS_ENDPOINT_URL_S3"],
        region_name=current_app.config["AWS_REGION"],
        aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )
