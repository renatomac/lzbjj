"""Read-only reconciliation of historical S3 enrollment photos and Rekognition.

This report is an inventory, NOT an authorization to delete any data.
Run against each environment's own CRM database before taking any action.
"""
import csv
import re
from collections import Counter
from pathlib import Path

from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand, CommandError

from crm.aws_utils import get_bucket_name, get_collection_id, get_rekognition_client, get_s3_client
from crm.models import Member, WaiverSignature
from crm.services.biometric_consent import approved_notice_versions

PREFIX = "face-enrollments/"
KEY_PATTERN = re.compile(r"^face-enrollments/member-(\d+)-[^/]+$")
FIELDS = [
    "record_type", "member_id", "s3_key", "s3_size_bytes", "s3_last_modified",
    "member_exists", "active_profile_photo_reference", "legacy_photo_reference",
    "historical_image_count", "rekognition_face_count", "stored_face_id_present",
    "consent_status", "classification", "notes",
]


def latest_consent_status(signatures, member):
    if member is None:
        return "member_missing"
    sig = signatures.get(member.pk)
    if sig is None:
        return "no_linked_waiver"
    if sig.participant_type != ("minor" if member.member_type == "child" else "adult"):
        return "waiver_type_mismatch"
    if sig.biometric_consent is not True:
        return "not_consented"
    if sig.biometric_notice_version not in approved_notice_versions():
        return "notice_not_approved"
    return "approved_consent"


def classify(member, key, count, aws_count, consent):
    if member is None:
        return "INVESTIGATE_MISSING_MEMBER", "No matching member in this database; check other environments"
    if key == (member.face_image_s3_key or "") or key in (member.photo or ""):
        return "PROTECT_PROFILE_PHOTO", "Referenced by Member.face_image_s3_key or Member.photo; never bulk-delete"
    if count > 1:
        return "REVIEW_MULTIPLE_IMAGES", "Multiple enrollment images; confirm usage and references"
    if consent != "approved_consent":
        return "REVIEW_CONSENT", "Consent is absent, declined, draft, or not approved"
    if aws_count:
        return "REVIEW_REKOGNITION", "Rekognition has indexed faces; confirm ownership and purpose"
    return "REVIEW_UNREFERENCED", "Not a direct member photo reference; still not proven safe to delete"


class Command(BaseCommand):
    help = "READ ONLY reconcile historical enrollment S3 objects, CRM members, and Rekognition faces"

    def add_arguments(self, parser):
        parser.add_argument("--csv", dest="csv_path", help="Write a local CSV report (contains sensitive identifiers)")
        parser.add_argument("--skip-rekognition", action="store_true", help="Skip Rekognition API; report count as unknown")

    def handle(self, *args, **options):
        members = {m.pk: m for m in Member.objects.all().iterator()}
        signatures = {}
        for sig in WaiverSignature.objects.filter(is_void=False, agreed=True).order_by("-signed_at", "-pk").iterator():
            if sig.member_id not in signatures:
                signatures[sig.member_id] = sig

        s3 = get_s3_client()
        bucket = get_bucket_name()
        objects = []
        try:
            for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX):
                objects.extend(page.get("Contents", []))
        except Exception as exc:
            raise CommandError(f"S3 inventory failed; report not generated: {exc}") from exc

        face_counts = Counter()
        if not options["skip_rekognition"]:
            try:
                rekognition = get_rekognition_client()
                token = None
                while True:
                    params = {"CollectionId": get_collection_id(), "MaxResults": 4096}
                    if token:
                        params["NextToken"] = token
                    response = rekognition.list_faces(**params)
                    for face in response.get("Faces", []):
                        face_counts[str(face.get("ExternalImageId", ""))] += 1
                    token = response.get("NextToken")
                    if not token:
                        break
            except Exception as exc:
                raise CommandError(
                    f"Rekognition inventory failed; no complete report generated: {exc}. "
                    "Use --skip-rekognition for an explicitly partial report."
                ) from exc

        by_member = Counter()
        for obj in objects:
            match = KEY_PATTERN.match(obj["Key"])
            if match:
                by_member[int(match.group(1))] += 1

        rows = []
        classifications = Counter()
        for obj in sorted(objects, key=lambda item: item["Key"]):
            key = obj["Key"]
            match = KEY_PATTERN.match(key)
            member_id = int(match.group(1)) if match else None
            member = members.get(member_id) if member_id is not None else None
            consent = latest_consent_status(signatures, member)
            count = by_member.get(member_id, 0)
            aws_count = face_counts.get(str(member_id), 0) if not options["skip_rekognition"] else None
            if not match:
                classification, notes = "INVESTIGATE_UNKNOWN_KEY", "Object name does not match expected member-ID pattern"
            else:
                classification, notes = classify(member, key, count, aws_count, consent)
            classifications[classification] += 1
            rows.append({
                "record_type": "s3_object",
                "member_id": member_id if member_id is not None else "",
                "s3_key": key,
                "s3_size_bytes": obj.get("Size", ""),
                "s3_last_modified": str(obj.get("LastModified", "")),
                "member_exists": "yes" if member else "no",
                "active_profile_photo_reference": "yes" if member and (key == (member.face_image_s3_key or "") or key in (member.photo or "")) else "no",
                "legacy_photo_reference": "unknown",
                "historical_image_count": count,
                "rekognition_face_count": aws_count if aws_count is not None else "unknown",
                "stored_face_id_present": "yes" if member and member.rekognition_face_id else "no",
                "consent_status": consent,
                "classification": classification,
                "notes": notes,
            })

        # A Rekognition vector can exist even when no corresponding S3 object exists.
        if not options["skip_rekognition"]:
            for external_id, count in sorted(face_counts.items()):
                if not external_id or not external_id.isdecimal():
                    member_id = None
                else:
                    member_id = int(external_id)
                if member_id is not None and by_member.get(member_id):
                    continue
                member = members.get(member_id)
                classification = "REVIEW_REKOGNITION_ONLY"
                classifications[classification] += 1
                rows.append({
                    "record_type": "rekognition_only", "member_id": member_id or "",
                    "s3_key": "", "s3_size_bytes": "", "s3_last_modified": "",
                    "member_exists": "yes" if member else "no",
                    "active_profile_photo_reference": "no", "legacy_photo_reference": "unknown",
                    "historical_image_count": 0, "rekognition_face_count": count,
                    "stored_face_id_present": "yes" if member and member.rekognition_face_id else "no",
                    "consent_status": latest_consent_status(signatures, member),
                    "classification": classification,
                    "notes": f"Rekognition ExternalImageId={external_id!r}; verify collection and database",
                })

        if options["csv_path"]:
            destination = Path(options["csv_path"])
            if destination.exists():
                raise CommandError(f"Refusing to overwrite existing report: {destination}")
            if not destination.parent.exists():
                raise CommandError(f"Directory does not exist: {destination.parent}")
            with destination.open("x", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(f"Sensitive local report written to {destination}; do not commit to Git")

        self.stdout.write(f"READ ONLY: {len(objects)} S3 objects; {len(face_counts) if not options['skip_rekognition'] else 'UNKNOWN'} distinct Rekognition external IDs; {len(rows)} report rows")
        for category, count in sorted(classifications.items()):
            self.stdout.write(f"  {category}: {count}")
        self.stdout.write("No deletion performed. Review against the production DB separately before deciding retention.")
