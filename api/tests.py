from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from api.authorize_net import AuthorizeNetClient


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
