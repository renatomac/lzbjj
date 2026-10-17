"""Multi-person photo recognition without retaining attendance photos in S3."""
import io

from PIL import Image, ImageOps

from crm.aws_utils import ensure_collection, get_rekognition_client


def recognize_faces(image_file, *, threshold=90, max_people=25):
    raw = image_file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Photo exceeds the 8 MB limit.")
    if not raw:
        raise ValueError("Please provide a photo.")
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    if image.width * image.height > 20_000_000:
        raise ValueError("Photo resolution is too large.")
    client = get_rekognition_client()
    collection = ensure_collection()
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    detected = client.detect_faces(Image={"Bytes": buffer.getvalue()}, Attributes=["DEFAULT"]).get("FaceDetails", [])
    if len(detected) > max_people:
        raise ValueError("Too many faces in one photo. Please take smaller group photos.")
    results = []
    for index, face in enumerate(detected):
        bbox = face["BoundingBox"]
        left = max(0, int(bbox["Left"] * image.width))
        top = max(0, int(bbox["Top"] * image.height))
        right = min(image.width, int((bbox["Left"] + bbox["Width"]) * image.width))
        bottom = min(image.height, int((bbox["Top"] + bbox["Height"]) * image.height))
        if right - left < 60 or bottom - top < 60:
            results.append({"face_number": index + 1, "member_id": None, "confidence": 0, "status": "low_quality"})
            continue
        # Add margin so the cropped face includes chin, hair and ears.
        margin = int(max(right-left, bottom-top) * .20)
        crop = image.crop((max(0, left-margin), max(0, top-margin), min(image.width, right+margin), min(image.height, bottom+margin)))
        face_bytes = io.BytesIO()
        crop.save(face_bytes, format="JPEG", quality=90)
        try:
            response = client.search_faces_by_image(
                CollectionId=collection,
                Image={"Bytes": face_bytes.getvalue()},
                FaceMatchThreshold=threshold,
                MaxFaces=20,
            )
        except client.exceptions.InvalidParameterException:
            results.append({"face_number": index + 1, "member_id": None, "confidence": 0, "status": "low_quality"})
            continue
        matches = response.get("FaceMatches", [])
        # Each member can have several enrolled poses with the same ExternalImageId.
        # Compare distinct members, not individual Rekognition face records.
        candidates = {}
        for match in matches:
            external_id = str(match.get("Face", {}).get("ExternalImageId", ""))
            if not external_id.isdigit():
                continue
            similarity = float(match["Similarity"])
            candidates[external_id] = max(candidates.get(external_id, 0), similarity)
        ranked = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
        best_id, best_score = ranked[0] if ranked else (None, 0)
        second_score = ranked[1][1] if len(ranked) > 1 else None
        ambiguous = second_score is not None and best_score - second_score < 5
        member_id = int(best_id) if best_id is not None and not ambiguous else None
        results.append({
            "face_number": index + 1,
            "member_id": member_id,
            "confidence": round(best_score, 1),
            "status": "candidate" if member_id else ("ambiguous" if ambiguous else "unmatched"),
        })
    return results
