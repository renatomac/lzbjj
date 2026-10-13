"""Mocked tests for multi-face recognition; no AWS calls or biometric fixtures."""
import io
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from PIL import Image

from crm.services.face_recognition import recognize_faces


def photo_bytes():
    output = io.BytesIO()
    Image.new("RGB", (500, 300), "white").save(output, format="JPEG")
    output.seek(0)
    return output


class MultiFaceRecognitionTests(SimpleTestCase):
    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_each_face_is_searched_independently(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        client.detect_faces.return_value = {"FaceDetails": [
            {"BoundingBox": {"Left": .1, "Top": .1, "Width": .25, "Height": .5}},
            {"BoundingBox": {"Left": .6, "Top": .1, "Width": .25, "Height": .5}},
        ]}
        client.search_faces_by_image.side_effect = [
            {"FaceMatches": [{"Similarity": 96, "Face": {"ExternalImageId": "10"}}]},
            {"FaceMatches": [{"Similarity": 94, "Face": {"ExternalImageId": "20"}}]},
        ]
        result = recognize_faces(photo_bytes())
        self.assertEqual([r["member_id"] for r in result], [10, 20])
        self.assertEqual(client.search_faces_by_image.call_count, 2)

    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_ambiguous_match_is_not_selected(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        client.detect_faces.return_value = {"FaceDetails": [
            {"BoundingBox": {"Left": .2, "Top": .1, "Width": .4, "Height": .7}},
        ]}
        client.search_faces_by_image.return_value = {"FaceMatches": [
            {"Similarity": 96, "Face": {"ExternalImageId": "10"}},
            {"Similarity": 94, "Face": {"ExternalImageId": "20"}},
        ]}
        result = recognize_faces(photo_bytes())
        self.assertIsNone(result[0]["member_id"])
        self.assertEqual(result[0]["status"], "ambiguous")
