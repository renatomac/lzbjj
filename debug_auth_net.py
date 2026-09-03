#!/usr/bin/env python
"""Debug script to test Authorize.Net batch API response"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone.settings')
django.setup()

import httpx
import base64
from django.conf import settings

login_id = settings.AUTHORIZE_LOGIN_ID
transaction_key = settings.AUTHORIZE_TRANSACTION_KEY

auth = base64.b64encode(f"{login_id}:{transaction_key}".encode("utf-8")).decode("utf-8")
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

batch_payload = {
    "getSettledBatchListRequest": {
        "merchantAuthentication": {
            "name": login_id,
            "transactionKey": transaction_key,
        },
        "firstSettlementDate": "2026-08-01T00:00:00Z",
        "lastSettlementDate": "2026-08-14T23:59:59Z",
    }
}

print("=" * 80)
print("BATCH REQUEST PAYLOAD:")
print(json.dumps(batch_payload, indent=2))
print("=" * 80)

response = httpx.post(
    "https://api.authorize.net/xml/v1/request.api",
    json=batch_payload,
    headers=headers,
    timeout=30,
)

print(f"\nHTTP Status: {response.status_code}")
print("\nRESPONSE BODY:")
body = response.json()
print(json.dumps(body, indent=2))
print("=" * 80)

# Try to extract batches
print("\nPARSING ATTEMPTS:")
print(f"body.get('batchList'): {body.get('batchList')}")
print(f"body.get('getSettledBatchListResponse'): {body.get('getSettledBatchListResponse')}")

# Check if response is nested
if 'getSettledBatchListResponse' in body:
    response_body = body['getSettledBatchListResponse']
    print(f"\nNested response keys: {response_body.keys()}")
    print(f"Nested batchList: {response_body.get('batchList')}")
