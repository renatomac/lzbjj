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

    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_multiple_enrolled_poses_of_same_student_are_not_ambiguous(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        client.detect_faces.return_value = {"FaceDetails": [
            {"BoundingBox": {"Left": .2, "Top": .1, "Width": .4, "Height": .7}},
        ]}
        client.search_faces_by_image.return_value = {"FaceMatches": [
            {"Similarity": 100, "Face": {"ExternalImageId": "98"}},
            {"Similarity": 99.8, "Face": {"ExternalImageId": "98"}},
            {"Similarity": 99.1, "Face": {"ExternalImageId": "98"}},
        ]}
        result = recognize_faces(photo_bytes())
        self.assertEqual(result[0]["member_id"], 98)
        self.assertEqual(result[0]["status"], "candidate")
        self.assertEqual(result[0]["confidence"], 100)
        self.assertEqual(client.search_faces_by_image.call_args.kwargs["MaxFaces"], 20)

    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_distinct_student_with_close_similarity_remains_ambiguous(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        client.detect_faces.return_value = {"FaceDetails": [
            {"BoundingBox": {"Left": .2, "Top": .1, "Width": .4, "Height": .7}},
        ]}
        client.search_faces_by_image.return_value = {"FaceMatches": [
            {"Similarity": 100, "Face": {"ExternalImageId": "98"}},
            {"Similarity": 99.9, "Face": {"ExternalImageId": "98"}},
            {"Similarity": 98.5, "Face": {"ExternalImageId": "20"}},
        ]}
        result = recognize_faces(photo_bytes())
        self.assertIsNone(result[0]["member_id"])
        self.assertEqual(result[0]["status"], "ambiguous")

    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_no_faces_does_not_search_or_check_in(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        client.detect_faces.return_value = {"FaceDetails": []}
        self.assertEqual(recognize_faces(photo_bytes()), [])
        client.search_faces_by_image.assert_not_called()

    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_excessive_group_size_rejected_before_search(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        face = {"BoundingBox": {"Left": .1, "Top": .1, "Width": .3, "Height": .6}}
        client.detect_faces.return_value = {"FaceDetails": [face, face, face]}
        with self.assertRaisesRegex(ValueError, "Too many faces"):
            recognize_faces(photo_bytes(), max_people=2)
        client.search_faces_by_image.assert_not_called()

    @patch("crm.services.face_recognition.ensure_collection", return_value="test")
    @patch("crm.services.face_recognition.get_rekognition_client")
    def test_unmatched_face_requires_manual_review(self, client_factory, _):
        client = Mock()
        client_factory.return_value = client
        client.detect_faces.return_value = {"FaceDetails": [
            {"BoundingBox": {"Left": .2, "Top": .1, "Width": .4, "Height": .7}},
        ]}
        client.search_faces_by_image.return_value = {"FaceMatches": []}
        result = recognize_faces(photo_bytes())
        self.assertEqual(result[0]["status"], "unmatched")
        self.assertIsNone(result[0]["member_id"])


class CheckinValidationTests(SimpleTestCase):
    def test_canceled_session_is_rejected(self):
        from types import SimpleNamespace
        from django.core.exceptions import ValidationError
        from crm.services.attendance import validate_checkin
        session = SimpleNamespace(is_canceled=True)
        with self.assertRaises(ValidationError):
            validate_checkin(session, SimpleNamespace(is_active=True))

    def test_inactive_member_is_rejected(self):
        from types import SimpleNamespace
        from django.core.exceptions import ValidationError
        from crm.services.attendance import validate_checkin
        session = SimpleNamespace(is_canceled=False)
        with self.assertRaises(ValidationError):
            validate_checkin(session, SimpleNamespace(is_active=False))

    def test_wrong_class_type_is_rejected(self):
        from types import SimpleNamespace
        from django.core.exceptions import ValidationError
        from crm.services.attendance import validate_checkin
        session = SimpleNamespace(
            is_canceled=False,
            class_template=SimpleNamespace(type="adult"),
        )
        member = SimpleNamespace(is_active=True, member_type="child")
        with self.assertRaises(ValidationError):
            validate_checkin(session, member)

    def test_past_session_is_rejected(self):
        from datetime import timedelta
        from types import SimpleNamespace
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        from crm.services.attendance import validate_checkin
        session = SimpleNamespace(
            is_canceled=False,
            class_template=SimpleNamespace(type="open"),
            date=timezone.localdate() - timedelta(days=1),
        )
        member = SimpleNamespace(is_active=True, member_type="adult")
        with self.assertRaises(ValidationError):
            validate_checkin(session, member)


class BiometricConsentPolicyTests(SimpleTestCase):
    @patch("crm.services.biometric_consent.WaiverSignature")
    def test_legacy_waiver_does_not_authorize_recognition(self, signature_model):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        signature_model.objects.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            participant_type="adult", biometric_consent=None, biometric_notice_version=""
        )
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @patch("crm.services.biometric_consent.WaiverSignature")
    def test_draft_notice_cannot_authorize_recognition(self, signature_model):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        signature_model.ADULT = "adult"
        signature_model.objects.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            participant_type="adult", biometric_consent=True, biometric_notice_version="2026-10-draft"
        )
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @patch("crm.services.biometric_consent.WaiverSignature")
    def test_approved_explicit_adult_consent_authorizes(self, signature_model):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        signature_model.ADULT = "adult"
        signature_model.objects.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            participant_type="adult", biometric_consent=True, biometric_notice_version="approved-v1"
        )
        self.assertTrue(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))
