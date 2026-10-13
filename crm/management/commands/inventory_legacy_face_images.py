"""Inventory historical biometric enrollment objects without deleting them."""
from django.core.management.base import BaseCommand
from crm.aws_utils import get_s3_client, get_bucket_name


class Command(BaseCommand):
    help = "READ ONLY inventory of legacy face-enrollments/ S3 objects"

    def add_arguments(self, parser):
        parser.add_argument("--prefix", default="face-enrollments/")

    def handle(self, *args, **options):
        prefix = options["prefix"]
        if prefix != "face-enrollments/":
            raise ValueError("Only the historical face-enrollments/ prefix is permitted")
        client = get_s3_client()
        bucket = get_bucket_name()
        count = 0
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                self.stdout.write(f"REVIEW ONLY key={obj['Key']} size={obj['Size']} modified={obj['LastModified']}")
                count += 1
        self.stdout.write(f"Found {count} historical objects. No deletion performed.")
