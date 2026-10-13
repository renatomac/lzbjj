"""Read-only biometric privacy inventory for staff review. No deletion APIs."""
from collections import Counter, defaultdict
from crm.aws_utils import get_bucket_name, get_collection_id, get_rekognition_client, get_s3_client
from crm.management.commands.reconcile_biometric_assets import KEY_PATTERN, PREFIX, classify, latest_consent_status
from crm.models import BiometricDeletionJob, Member, WaiverSignature


def build_privacy_inventory(include_aws=False):
    members = {m.pk: m for m in Member.objects.all().iterator()}
    signatures = {}
    for sig in WaiverSignature.objects.filter(is_void=False, agreed=True).order_by("-signed_at", "-pk").iterator():
        signatures.setdefault(sig.member_id, sig)
    statuses = {pk: latest_consent_status(signatures, m) for pk, m in members.items()}
    jobs = list(BiometricDeletionJob.objects.select_related("member").order_by("-requested_at")[:30])
    result = {
        "members_total": len(members),
        "consent_counts": dict(Counter(statuses.values())),
        "indexed_members": sum(bool(m.rekognition_face_id) for m in members.values()),
        "jobs": jobs, "job_counts": dict(Counter(BiometricDeletionJob.objects.values_list("status", flat=True))),
        "aws_scanned": False, "rows": [], "counts": {}, "face_total": None, "s3_total": None,
    }
    if not include_aws:
        return result
    objects = []
    for page in get_s3_client().get_paginator("list_objects_v2").paginate(Bucket=get_bucket_name(), Prefix=PREFIX):
        objects.extend(page.get("Contents", []))
    faces = Counter()
    token = None
    client = get_rekognition_client()
    while True:
        args = {"CollectionId": get_collection_id(), "MaxResults": 4096}
        if token:
            args["NextToken"] = token
        response = client.list_faces(**args)
        for face in response.get("Faces", []):
            faces[str(face.get("ExternalImageId", ""))] += 1
        token = response.get("NextToken")
        if not token:
            break
    historical = Counter()
    for obj in objects:
        match = KEY_PATTERN.match(obj["Key"])
        if match:
            historical[int(match.group(1))] += 1
    rows = []
    for obj in sorted(objects, key=lambda x: x["Key"]):
        key = obj["Key"]
        match = KEY_PATTERN.match(key)
        pk = int(match.group(1)) if match else None
        member = members.get(pk)
        consent = statuses.get(pk, "member_missing")
        if match:
            classification, note = classify(member, key, historical[pk], faces.get(str(pk), 0), consent)
        else:
            classification, note = "INVESTIGATE_UNKNOWN_KEY", "Unexpected S3 key naming"
        rows.append({
            "member_id": pk, "member": member, "key": key, "size": obj.get("Size", 0),
            "date": obj.get("LastModified"), "faces": faces.get(str(pk), 0),
            "consent": consent, "classification": classification, "note": note,
        })
    for external_id, count in sorted(faces.items()):
        pk = int(external_id) if external_id.isdecimal() else None
        if pk is not None and historical[pk]:
            continue
        rows.append({
            "member_id": pk, "member": members.get(pk), "key": "",
            "size": 0, "date": None, "faces": count,
            "consent": statuses.get(pk, "member_missing"),
            "classification": "REVIEW_REKOGNITION_ONLY",
            "note": f"Rekognition ExternalImageId: {external_id}",
        })
    result.update({
        "aws_scanned": True, "rows": rows, "counts": dict(Counter(r["classification"] for r in rows)),
        "face_total": sum(faces.values()), "s3_total": len(objects),
    })
    return result
