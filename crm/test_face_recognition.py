from django.test import override_settings
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
    def _decision(self, *, choice="grant", version="approved-v1", verified=True, minor=False):
        from types import SimpleNamespace
        notice = SimpleNamespace(version=version, content="Full approved notice",
                                 is_approved=True, is_active=True,
                                 approved_at=object(), effective_date=object())
        waiver = SimpleNamespace(is_void=False, agreed=True, member_id=5,
                                 participant_type="minor" if minor else "adult")
        decision = SimpleNamespace(
            decision=choice, signed_at=object(), notice=notice,
            notice_version=version, notice_text=notice.content,
            signer_name="Parent Smith" if minor else "Student Smith",
            signature="Signed", guardian_relationship="parent" if minor else "",
            waiver_signature=waiver,
        )
        if verified:
            decision.verification = SimpleNamespace(verified_by_id=1)
        return decision

    @override_settings(BIOMETRIC_RECOGNITION_ENABLED=False)
    @patch("crm.services.biometric_consent.BiometricConsentRecord")
    def test_disabled_feature_never_authorizes(self, model):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = self._decision()
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @override_settings(BIOMETRIC_RECOGNITION_ENABLED=True)
    @patch("crm.services.biometric_consent.BiometricConsentWithdrawal")
    @patch("crm.services.biometric_consent.BiometricConsentRecord")
    def test_verified_approved_adult_authorizes(self, model, withdrawals):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = self._decision()
        withdrawals.objects.filter.return_value.exists.return_value = False
        self.assertTrue(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @override_settings(BIOMETRIC_RECOGNITION_ENABLED=True)
    @patch("crm.services.biometric_consent.BiometricConsentWithdrawal")
    @patch("crm.services.biometric_consent.BiometricConsentRecord")
    def test_withdrawal_blocks_earlier_grant(self, model, withdrawals):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = self._decision()
        withdrawals.objects.filter.return_value.exists.return_value = True
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @override_settings(BIOMETRIC_RECOGNITION_ENABLED=True)
    @patch("crm.services.biometric_consent.BiometricConsentWithdrawal")
    @patch("crm.services.biometric_consent.BiometricConsentRecord")
    def test_unverified_decision_is_not_authorized(self, model, withdrawals):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = self._decision(verified=False)
        withdrawals.objects.filter.return_value.exists.return_value = False
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @override_settings(BIOMETRIC_RECOGNITION_ENABLED=True)
    @patch("crm.services.biometric_consent.BiometricConsentWithdrawal")
    @patch("crm.services.biometric_consent.BiometricConsentRecord")
    def test_draft_notice_cannot_authorize(self, model, withdrawals):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = self._decision(version="2026-10-draft")
        withdrawals.objects.filter.return_value.exists.return_value = False
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))

    @override_settings(BIOMETRIC_RECOGNITION_ENABLED=True)
    @patch("crm.services.biometric_consent.BiometricConsentWithdrawal")
    @patch("crm.services.biometric_consent.BiometricConsentRecord")
    def test_declined_consent_never_authorizes(self, model, withdrawals):
        from types import SimpleNamespace
        from crm.services.biometric_consent import has_biometric_consent
        model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = self._decision(choice="decline")
        self.assertFalse(has_biometric_consent(SimpleNamespace(pk=5, member_type="adult")))


class BiometricDeletionTests(SimpleTestCase):
    @patch("crm.aws_utils.get_rekognition_client")
    @patch("crm.aws_utils.ensure_collection", return_value="test-collection")
    def test_delete_all_guided_poses(self, collection, get_client):
        from types import SimpleNamespace
        from crm.aws_utils import delete_member_biometrics
        member = SimpleNamespace(pk=42, rekognition_face_id="old", save=Mock())
        client = get_client.return_value
        client.list_faces.return_value = {"Faces": [
            {"FaceId": "one", "ExternalImageId": "42"},
            {"FaceId": "two", "ExternalImageId": "42"},
            {"FaceId": "other", "ExternalImageId": "7"},
        ]}
        client.delete_faces.return_value = {"DeletedFaces": ["one", "two"]}
        self.assertEqual(delete_member_biometrics(member), 2)
        client.delete_faces.assert_called_once_with(CollectionId="test-collection", FaceIds=["one", "two"])
        self.assertIsNone(member.rekognition_face_id)

    @patch("crm.aws_utils.get_rekognition_client")
    @patch("crm.aws_utils.ensure_collection", return_value="test-collection")
    def test_unconfirmed_deletion_keeps_local_marker(self, collection, get_client):
        from types import SimpleNamespace
        from crm.aws_utils import delete_member_biometrics
        member = SimpleNamespace(pk=42, rekognition_face_id="old", save=Mock())
        client = get_client.return_value
        client.list_faces.return_value = {"Faces": [{"FaceId": "one", "ExternalImageId": "42"}]}
        client.delete_faces.return_value = {"DeletedFaces": []}
        with self.assertRaises(RuntimeError):
            delete_member_biometrics(member)
        self.assertEqual(member.rekognition_face_id, "old")
        member.save.assert_not_called()


class BiometricDeletionQueueTests(SimpleTestCase):
    @patch("crm.services.biometric_deletion.delete_member_biometrics", return_value=5)
    def test_success_marks_job_complete(self, delete):
        from types import SimpleNamespace
        from crm.services.biometric_deletion import execute_biometric_deletion
        job = SimpleNamespace(pk=7, member=SimpleNamespace(pk=2), attempts=0, status="pending",
                              last_error="", save=Mock())
        result = execute_biometric_deletion(job)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.deleted_face_count, 5)
        job.save.assert_called_once()

    @patch("crm.services.biometric_deletion.delete_member_biometrics", side_effect=RuntimeError("AWS unavailable"))
    def test_failure_remains_retryable(self, delete):
        from types import SimpleNamespace
        from crm.services.biometric_deletion import execute_biometric_deletion
        job = SimpleNamespace(pk=7, member=SimpleNamespace(pk=2), attempts=0, status="pending",
                              last_error="", save=Mock())
        result = execute_biometric_deletion(job)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.attempts, 1)
        self.assertIn("AWS unavailable", result.last_error)


class BiometricReconciliationTests(SimpleTestCase):
    def test_protects_profile_photo_reference(self):
        from types import SimpleNamespace
        from crm.management.commands.reconcile_biometric_assets import classify
        member = SimpleNamespace(face_image_s3_key="face-enrollments/member-9-photo.jpg", photo="")
        status, _ = classify(member, member.face_image_s3_key, 1, 0, "not_consented")
        self.assertEqual(status, "PROTECT_PROFILE_PHOTO")

    def test_protects_legacy_photo_url(self):
        from types import SimpleNamespace
        from crm.management.commands.reconcile_biometric_assets import classify
        key = "face-enrollments/member-9-photo.jpg"
        member = SimpleNamespace(face_image_s3_key=None, photo="https://bucket.s3.amazonaws.com/" + key)
        status, _ = classify(member, key, 1, 0, "not_consented")
        self.assertEqual(status, "PROTECT_PROFILE_PHOTO")

    def test_missing_member_is_not_safe_to_delete(self):
        from crm.management.commands.reconcile_biometric_assets import classify
        status, _ = classify(None, "face-enrollments/member-9-photo.jpg", 1, 0, "member_missing")
        self.assertEqual(status, "INVESTIGATE_MISSING_MEMBER")

    def test_duplicate_images_require_review(self):
        from types import SimpleNamespace
        from crm.management.commands.reconcile_biometric_assets import classify
        member = SimpleNamespace(face_image_s3_key=None, photo="")
        status, _ = classify(member, "face-enrollments/member-9-other.jpg", 3, 0, "approved_consent")
        self.assertEqual(status, "REVIEW_MULTIPLE_IMAGES")


class BiometricDashboardTests(SimpleTestCase):
    def test_inventory_classifies_missing_member_without_deleting(self):
        from crm.management.commands.reconcile_biometric_assets import classify
        status, _ = classify(None, "face-enrollments/member-999-test.jpg", 1, 0, "member_missing")
        self.assertEqual(status, "INVESTIGATE_MISSING_MEMBER")

    def test_dashboard_requires_staff_access(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from crm.views import biometric_privacy_dashboard
        request = RequestFactory().get("/privacy/biometrics/")
        request.user = AnonymousUser()
        response = biometric_privacy_dashboard(request)
        self.assertEqual(response.status_code, 302)


class BiometricInvitationTests(SimpleTestCase):
    def test_signed_invitation_round_trip(self):
        from types import SimpleNamespace
        from crm.services.biometric_invitation import make_invitation, resolve_invitation
        token = make_invitation(SimpleNamespace(pk=67))
        self.assertEqual(resolve_invitation(token), 67)

    def test_tampered_invitation_rejected(self):
        from types import SimpleNamespace
        from django.core.signing import BadSignature
        from crm.services.biometric_invitation import make_invitation, resolve_invitation
        token = make_invitation(SimpleNamespace(pk=67))
        with self.assertRaises(BadSignature):
            resolve_invitation(token + "x")

    def test_unapproved_notice_blocks_invitations(self):
        from django.test import override_settings
        from crm.services.biometric_invitation import notice_configuration
        with patch("crm.services.biometric_invitation.active_notice", return_value=None):
            self.assertFalse(notice_configuration()[2])
