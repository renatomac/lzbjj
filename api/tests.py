from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from api.authorize_net import AuthorizeNetClient
from api.transaction_reconciliation import match_transaction
from crm.models import Member, Plan


class TransactionReconciliationTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            name="Monthly",
            description="", 
            enroll_price=Decimal("0.00"),
            membership_price=Decimal("120.00"),
            duration_months=1,
        )

    def test_match_transaction_prefers_profile_id_when_available(self):
        member = Member.objects.create(
            first_name="Alex",
            last_name="Kogan",
            email="alex@example.com",
            date_of_birth="2000-01-01",
            address="123 Main St",
            city="Chicago",
            state="IL",
            zip_code="60601",
            plan=self.plan,
            authorize_customer_profile_id="profile-abc",
        )
        tx = {
            "customerProfileId": "profile-abc",
            "firstName": "Someone",
            "lastName": "Else",
            "amount": "120.00",
        }

        matched_member, match_status, matched_by = match_transaction(tx, "Someone", "Else", Decimal("120.00"))

        self.assertEqual(matched_member, member)
        self.assertEqual(match_status, "matched")
        self.assertEqual(matched_by, "invoice")

    def test_match_transaction_uses_name_match_when_profile_is_missing(self):
        member = Member.objects.create(
            first_name="Taylor",
            last_name="Smith",
            email="taylor@example.com",
            date_of_birth="1995-05-10",
            address="456 Oak Ave",
            city="Chicago",
            state="IL",
            zip_code="60602",
            plan=self.plan,
        )
        tx = {"customerProfileId": "", "firstName": "Taylor", "lastName": "Smith", "amount": "120.00"}

        matched_member, match_status, matched_by = match_transaction(tx, "Taylor", "Smith", Decimal("120.00"))

        self.assertEqual(matched_member, member)
        self.assertEqual(match_status, "matched")
        self.assertEqual(matched_by, "name_match")

    def test_match_transaction_marks_ambiguous_heuristic_as_needs_review(self):
        Member.objects.create(
            first_name="Jamie",
            last_name="Park",
            email="jamie@example.com",
            date_of_birth="2001-02-02",
            address="1 A St",
            city="Chicago",
            state="IL",
            zip_code="60603",
            plan=self.plan,
        )
        Member.objects.create(
            first_name="Jordan",
            last_name="Park",
            email="jordan@example.com",
            date_of_birth="2002-03-03",
            address="2 B St",
            city="Chicago",
            state="IL",
            zip_code="60604",
            plan=self.plan,
        )
        tx = {"customerProfileId": "", "firstName": "No", "lastName": "Park", "amount": "120.00"}

        matched_member, match_status, matched_by = match_transaction(tx, "No", "Park", Decimal("120.00"))

        self.assertIsNone(matched_member)
        self.assertEqual(match_status, "needs_review")
        self.assertEqual(matched_by, "")


class AuthorizeNetClientTests(TestCase):
    @patch("api.authorize_net.httpx.post")
    def test_get_transactions_for_date_range_uses_reporting_api(self, mock_post):
        class MockResponse:
            def __init__(self, payload, status_code=200):
                self._payload = payload
                self.status_code = status_code

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        mock_post.side_effect = [
            MockResponse({
                "batchList": [{"batchId": "1001"}],
                "messages": {"resultCode": "Ok"},
            }),
            MockResponse({
                "transactions": {
                    "transaction": [{
                        "transId": "123",
                        "transactionStatus": "settledSuccessfully",
                        "authAmount": "120.00",
                        "submitTimeUTC": "2026-08-10T04:27:29Z",
                        "billTo": {"email": "alex@example.com"},
                    }]
                },
                "messages": {"resultCode": "Ok"},
            }),
        ]

        client = AuthorizeNetClient(login_id="login", transaction_key="key")
        transactions = client.get_transactions_for_date_range(date(2026, 8, 1), date(2026, 8, 10))

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]["transId"], "123")
        self.assertEqual(mock_post.call_count, 2)
        first_request = mock_post.call_args_list[0].kwargs["json"]
        self.assertIn("getSettledBatchListRequest", first_request)
