"""Integration tests for LZBJJ biometric consent workflows.

Uses Django's disposable test database, fictional people and a fictional
approved notice. Does not contact AWS or grant legal approval.
"""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from crm.models import (
    BiometricConsentRecord,
    BiometricConsentVerification,
    BiometricConsentWithdrawal,
    BiometricDeletionJob,
    BiometricNoticeVersion,
    Member,
    WaiverSignature,
    WaiverVersion,
)
from crm.services.biometric_consent import has_biometric_consent
from crm.services.biometric_invitation import make_invitation


@override_settings(
    BIOMETRIC_RECOGNITION_ENABLED=True,
    BIOMETRIC_BULK_SCANNING_ENABLED=False,
)
class BiometricWorkflowIntegrationTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="integration-privacy-staff", password="test-only", is_staff=True
        )
        self.notice = BiometricNoticeVersion.objects.create(
            version="integration-test-approved",
            title="FICTIONAL TEST NOTICE",
            content="Test fixture only. Not approved for real biometric collection.",
            effective_date=timezone.localdate(),
            is_approved=True,
            is_active=True,
            approved_at=timezone.now(),
            approved_by=self.staff,
        )
        for waiver_type in (WaiverVersion.ADULT, WaiverVersion.MINOR):
            WaiverVersion.objects.create(
                waiver_type=waiver_type,
                version="integration-test",
                content="Fictional waiver used only in automated tests.",
                effective_date=timezone.localdate(),
                is_active=True,
            )

    def make_member(self, kind="adult"):
        return Member.objects.create(
            member_type=kind,
            first_name="Test",
            last_name="Student",
            date_of_birth=date(2015, 1, 1) if kind == "child" else date(1990, 1, 1),
            address="123 Test Road",
            city="Test City",
            zip_code="60000",
        )

    @staticmethod
    def waiver_data(minor=False, decision="yes"):
        data = {
            "participant_first_name": "Test",
            "participant_last_name": "Student",
            "signature": "Test Parent" if minor else "Test Student",
            "agreed": "on",
            "biometric_consent": decision,
        }
        if minor:
            data.update({
                "participant_dob": "2015-01-01",
                "guardian_first_name": "Test",
                "guardian_last_name": "Parent",
                "guardian_relationship": "parent",
            })
        return data

    @patch("crm.views.start_trial_from_waiver")
    def test_adult_waiver_grant_is_separate_from_recognition(self, _trial):
        response = self.client.post(reverse("adult_waiver"), self.waiver_data())
        self.assertEqual(response.status_code, 302)
        record = BiometricConsentRecord.objects.get()
        self.assertEqual(record.decision, "grant")
        self.assertEqual(record.notice_text, self.notice.content)
        self.assertEqual(record.waiver_signature.participant_type, WaiverSignature.ADULT)
        self.assertIsNone(record.member_id)  # public waiver has not been linked to a member
        self.assertFalse(has_biometric_consent(self.make_member()))

    @patch("crm.views.start_trial_from_waiver")
    def test_minor_waiver_decline_records_guardian(self, _trial):
        response = self.client.post(
            reverse("minor_waiver"), self.waiver_data(minor=True, decision="no")
        )
        self.assertEqual(response.status_code, 302)
        record = BiometricConsentRecord.objects.get()
        self.assertEqual(record.decision, "decline")
        self.assertEqual(record.signer_name, "Test Parent")
        self.assertEqual(record.guardian_relationship, "parent")
        self.assertEqual(record.waiver_signature.participant_type, WaiverSignature.MINOR)

    def test_minor_waiver_without_guardian_is_rejected(self):
        data = self.waiver_data(minor=True)
        del data["guardian_first_name"]
        response = self.client.post(reverse("minor_waiver"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WaiverSignature.objects.exists())
        self.assertFalse(BiometricConsentRecord.objects.exists())

    def test_waiver_missing_biometric_choice_is_not_saved(self):
        data = self.waiver_data()
        del data["biometric_consent"]
        response = self.client.post(reverse("adult_waiver"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WaiverSignature.objects.exists())
        self.assertFalse(BiometricConsentRecord.objects.exists())

    def test_invitation_verification_and_withdrawal_queue(self):
        member = self.make_member()
        response = self.client.post(
            reverse("biometric_consent_sign", args=[make_invitation(member)]),
            {
                "decision": "grant",
                "signer_name": "Test Student",
                "signature": "Test Student",
                "acknowledged": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        record = BiometricConsentRecord.objects.get(member=member)
        self.assertFalse(has_biometric_consent(member))

        BiometricConsentVerification.objects.create(
            consent=record,
            verified_by=self.staff,
            method="in-person fictional test",
        )
        self.assertTrue(has_biometric_consent(member))

        self.client.force_login(self.staff)
        with patch("crm.services.biometric_deletion.delete_member_biometrics") as aws_delete:
            response = self.client.post(
                reverse("revoke_member_biometric_consent", args=[member.pk])
            )
            aws_delete.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(has_biometric_consent(member))
        self.assertEqual(
            BiometricConsentWithdrawal.objects.filter(member=member).count(), 1
        )
        self.assertTrue(
            BiometricDeletionJob.objects.filter(member=member, status="pending").exists()
        )
        record.refresh_from_db()
        self.assertEqual(record.decision, "grant")  # signed evidence is preserved

    def test_minor_invitation_without_verification_cannot_authorize(self):
        member = self.make_member("child")
        response = self.client.post(
            reverse("biometric_consent_sign", args=[make_invitation(member)]),
            {
                "decision": "grant",
                "signer_name": "Test Parent",
                "signature": "Test Parent",
                "guardian_relationship": "parent",
                "acknowledged": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(has_biometric_consent(member))
