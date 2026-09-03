from __future__ import annotations

import base64
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class AuthorizeNetClient:
    """Thin wrapper around Authorize.Net's payment and reporting API."""

    def __init__(self, login_id: Optional[str] = None, transaction_key: Optional[str] = None, environment: Optional[str] = None):
        self.login_id = login_id or getattr(settings, "AUTHORIZE_LOGIN_ID", "")
        self.transaction_key = transaction_key or getattr(settings, "AUTHORIZE_TRANSACTION_KEY", "")
        self.environment = (environment or getattr(settings, "AUTHORIZE_ENVIRONMENT", "sandbox")).lower()

        if getattr(settings, "AUTHORIZE_API_URL", ""):
            self.base_url = settings.AUTHORIZE_API_URL.rstrip("/")
        elif self.environment == "sandbox":
            self.base_url = "https://sandbox-api.authorize.net"
        else:
            self.base_url = "https://api.authorize.net"

    def _post_json(self, payload: Dict[str, Any], max_attempts: int = 4) -> Dict[str, Any]:
        if not self.is_configured:
            return {}

        for attempt in range(max_attempts):
            try:
                response = httpx.post(
                    f"{self.base_url}/xml/v1/request.api",
                    json=payload,
                    headers=self._auth_headers(),
                    timeout=30,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == max_attempts - 1:
                        response.raise_for_status()
                    delay = min(30, 2 ** attempt)
                    logger.warning("Authorize.Net returned HTTP %s; retrying in %ss", response.status_code, delay)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                break
            except (httpx.HTTPError, OSError):
                if attempt == max_attempts - 1:
                    raise
                delay = min(30, 2 ** attempt)
                logger.warning("Authorize.Net request failed; retrying in %ss", delay, exc_info=True)
                time.sleep(delay)

        try:
            body = response.json()
        except ValueError:
            body = {}

        messages = body.get("messages") if isinstance(body, dict) else {}
        if isinstance(messages, dict):
            result_code = str(messages.get("resultCode") or "").lower()
            message_items = messages.get("message") or []
            if result_code == "error":
                if isinstance(message_items, list):
                    texts = [str(item.get("text") or item) for item in message_items if isinstance(item, dict)]
                    if texts:
                        raise ValueError("Authorize.Net API error: " + "; ".join(texts))
                elif isinstance(message_items, dict):
                    text = message_items.get("text")
                    if text:
                        raise ValueError(f"Authorize.Net API error: {text}")
                raise ValueError("Authorize.Net API error: the request was rejected by Authorize.Net.")

        return body

    @property
    def is_configured(self) -> bool:
        return bool(self.login_id and self.transaction_key)

    def _auth_headers(self) -> Dict[str, str]:
        if not self.is_configured:
            raise ValueError("Authorize.Net credentials are not configured.")

        auth = base64.b64encode(f"{self.login_id}:{self.transaction_key}".encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_transaction_details(self, transaction_id: str) -> Dict[str, Any]:
        """Fetch transaction details by transaction ID using Authorize.Net reporting API."""
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": "Authorize.Net credentials are not configured.",
            }

        try:
            payload = {
                "getTransactionDetailsRequest": {
                    "merchantAuthentication": {
                        "name": self.login_id,
                        "transactionKey": self.transaction_key,
                    },
                    "transId": str(transaction_id),
                }
            }
            body = self._post_json(payload)

            tx = body.get("transaction") or body
            return {
                "transaction_id": tx.get("transId") or tx.get("trans_id") or transaction_id,
                "status": tx.get("transactionStatus") or tx.get("transaction_status"),
                "response_code": tx.get("responseCode") or tx.get("response_code"),
                "amount": tx.get("authAmount") or tx.get("settleAmount") or tx.get("amount"),
                "auth_code": tx.get("authCode") or tx.get("authorizationCode"),
                "settlement_state": tx.get("settlementState") or tx.get("settlement_state"),
                "raw": body,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": str(exc),
                "transaction_id": str(transaction_id),
            }

    def get_transactions_for_date_range(self, start_date, end_date) -> List[Dict[str, Any]]:
        """Return every transaction in settled batches, paging each batch.

        Accepts either `date` (whole-day range) or `datetime` (precise range,
        used for the rolling-hour recurring sync) for start_date/end_date.
        """
        if not self.is_configured:
            return []

        def _to_iso(value, end_of_day):
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%dT%H:%M:%SZ")
            return f"{value.isoformat()}T{'23:59:59' if end_of_day else '00:00:00'}Z"

        batch_payload = {
            "getSettledBatchListRequest": {
                "merchantAuthentication": {
                    "name": self.login_id,
                    "transactionKey": self.transaction_key,
                },
                "firstSettlementDate": _to_iso(start_date, end_of_day=False),
                "lastSettlementDate": _to_iso(end_date, end_of_day=True),
            }
        }
        batch_body = self._post_json(batch_payload)
        batches = batch_body.get("batchList") or []
        if isinstance(batches, dict):
            batches = batches.get("batch") or []
        if not isinstance(batches, list):
            return []

        all_transactions: List[Dict[str, Any]] = []
        for batch in batches:
            batch_id = batch.get("batchId")
            if not batch_id:
                continue

            # Settlement date/time is a batch-level attribute, not per-transaction.
            batch_settlement_utc = batch.get("settlementTimeUTC")
            batch_settlement_local = batch.get("settlementTimeLocal")

            offset = 1
            while True:
                tx_list_payload = {
                    "getTransactionListRequest": {
                        "merchantAuthentication": {
                            "name": self.login_id,
                            "transactionKey": self.transaction_key,
                        },
                        "batchId": str(batch_id),
                        "sorting": {"orderBy": "submitTimeUTC", "orderDescending": True},
                        "paging": {"limit": "1000", "offset": str(offset)},
                    }
                }
                tx_body = self._post_json(tx_list_payload)
                tx_response = tx_body.get("transactions") or tx_body.get("getTransactionListResponse", {}).get("transactions") or {}
                if isinstance(tx_response, dict):
                    transaction_items = tx_response.get("transaction") or []
                elif isinstance(tx_response, list):
                    transaction_items = tx_response
                else:
                    transaction_items = []

                if isinstance(transaction_items, dict):
                    transaction_items = [transaction_items]

                for item in transaction_items:
                    item["_batchId"] = batch_id
                    item["_settlementTimeUTC"] = batch_settlement_utc
                    item["_settlementTimeLocal"] = batch_settlement_local

                all_transactions.extend(transaction_items)
                if len(transaction_items) < 1000:
                    break
                offset += 1000

        return all_transactions


def get_member_payment_status(member, transaction_id: Optional[str] = None, amount: Optional[str] = None):
    """Return a normalized membership payment and expiration status for a member."""
    from crm.models import Payment

    today = date.today()
    membership_start = member.membership_start_date
    membership_end = member.membership_end_date

    if membership_end:
        days_until_expiration = (membership_end - today).days
    else:
        days_until_expiration = None

    is_expired = bool(membership_end and membership_end < today)
    is_active = bool(membership_end and membership_end >= today and member.is_active)

    latest_payment = (
        Payment.objects.filter(user=member.user).order_by("-payment_date", "-timestamp").first()
        if member.user_id
        else None
    )

    result = {
        "member_id": member.id,
        "member_name": str(member),
        "is_active": bool(member.is_active),
        "membership_start_date": membership_start.isoformat() if membership_start else None,
        "membership_end_date": membership_end.isoformat() if membership_end else None,
        "is_expired": is_expired,
        "membership_status": "expired" if is_expired else "active" if is_active else "pending",
        "days_until_expiration": days_until_expiration,
        "latest_payment": {
            "id": latest_payment.id,
            "amount": float(latest_payment.amount),
            "payment_date": latest_payment.payment_date.isoformat() if latest_payment.payment_date else None,
            "status": latest_payment.status,
            "payment_method": latest_payment.payment_method,
        } if latest_payment else None,
        "payment_verified": False,
    }

    if transaction_id:
        client = AuthorizeNetClient()
        external = client.get_transaction_details(transaction_id)
        result["authorize_net"] = external
        result["payment_verified"] = bool(external.get("status") and external.get("status") not in {"error", "not_configured"})

    if amount and latest_payment is not None:
        result["amount_matches"] = float(latest_payment.amount) >= float(amount)
    else:
        result["amount_matches"] = None

    return result
