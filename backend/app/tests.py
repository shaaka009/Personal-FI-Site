from unittest.mock import patch

from plaid import ApiException
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Account, PlaidItem, Transaction


class PlaidApiTests(APITestCase):
    @patch("app.views.create_link_token")
    def test_link_token_success(self, mock_create_link_token):
        mock_create_link_token.return_value = {"link_token": "link-sample-token"}

        response = self.client.post("/api/plaid/link-token", {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["link_token"], "link-sample-token")

    @patch("app.views.create_link_token")
    def test_link_token_plaid_error_returns_status_and_body(self, mock_create_link_token):
        exc = ApiException(status=400, reason="Bad Request")
        exc.body = b'{"error_code":"INVALID_FIELD","display_message":"Bad field"}'
        mock_create_link_token.side_effect = exc

        response = self.client.post("/api/plaid/link-token", {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error_code"], "INVALID_FIELD")
        self.assertIn("Bad field", response.data["message"])

    def test_exchange_token_requires_public_token(self):
        response = self.client.post("/api/plaid/exchange-token", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    @patch("app.views.exchange_public_token")
    def test_exchange_token_creates_item(self, mock_exchange_public_token):
        mock_exchange_public_token.return_value = {
            "item_id": "item-123",
            "access_token": "access-123",
        }
        response = self.client.post(
            "/api/plaid/exchange-token",
            {"public_token": "public-123", "institution_name": "SoFi"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PlaidItem.objects.count(), 1)
        item = PlaidItem.objects.first()
        self.assertEqual(item.item_id, "item-123")
        self.assertEqual(item.institution_name, "SoFi")

    @patch("app.views.fetch_transactions")
    @patch("app.views.fetch_accounts")
    def test_sync_is_idempotent(self, mock_fetch_accounts, mock_fetch_transactions):
        item = PlaidItem.objects.create(
            item_id="item-abc",
            access_token="access-abc",
            institution_name="SoFi",
        )
        mock_fetch_accounts.return_value = {
            "accounts": [
                {
                    "account_id": "acct-1",
                    "name": "SoFi Savings",
                    "official_name": "Savings",
                    "type": "depository",
                    "subtype": "savings",
                    "mask": "1234",
                    "balances": {
                        "current": 1200.25,
                        "available": 1200.25,
                        "iso_currency_code": "USD",
                    },
                }
            ]
        }
        mock_fetch_transactions.return_value = {
            "transactions": [
                {
                    "transaction_id": "txn-1",
                    "account_id": "acct-1",
                    "name": "Payroll",
                    "amount": -1000,
                    "date": "2026-04-13",
                    "pending": False,
                    "merchant_name": "Employer",
                    "personal_finance_category": {
                        "primary": "INCOME",
                        "detailed": "INCOME_WAGES",
                    },
                    "payment_channel": "other",
                    "authorized_date": "2026-04-13",
                }
            ]
        }

        first = self.client.post("/api/plaid/sync", {}, format="json")
        second = self.client.post("/api/plaid/sync", {}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(first.data["transactions_created"], 1)
        self.assertEqual(second.data["transactions_created"], 0)
        self.assertEqual(second.data["transactions_updated"], 1)
        self.assertEqual(second.data["items_failed"], [])
        item.refresh_from_db()
        self.assertTrue(item.last_sync_success)
        self.assertEqual(item.last_sync_error, "")

    @patch("app.views.fetch_transactions")
    @patch("app.views.fetch_accounts")
    def test_partial_sync_records_per_item_failure(
        self, mock_fetch_accounts, mock_fetch_transactions
    ):
        PlaidItem.objects.create(
            item_id="item-good",
            access_token="access-good",
            institution_name="SoFi",
        )
        PlaidItem.objects.create(
            item_id="item-bad",
            access_token="access-bad",
            institution_name="BoA",
        )

        good_accounts = {
            "accounts": [
                {
                    "account_id": "acct-good",
                    "name": "Savings",
                    "official_name": "",
                    "type": "depository",
                    "subtype": "savings",
                    "mask": "1111",
                    "balances": {
                        "current": 100,
                        "available": 100,
                        "iso_currency_code": "USD",
                    },
                }
            ]
        }

        def accounts_side_effect(access_token):
            if access_token == "access-bad":
                exc = ApiException(status=503, reason="Service Unavailable")
                exc.body = b'{"error_code":"INSTITUTION_NOT_RESPONDING","display_message":"Down"}'
                raise exc
            return good_accounts

        def transactions_side_effect(access_token, start_date, end_date):
            if access_token == "access-bad":
                raise AssertionError("transactions should not run when accounts fail")
            return {"transactions": []}

        mock_fetch_accounts.side_effect = accounts_side_effect
        mock_fetch_transactions.side_effect = transactions_side_effect

        response = self.client.post("/api/plaid/sync", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items_succeeded"], 1)
        self.assertEqual(len(response.data["items_failed"]), 1)
        self.assertEqual(response.data["items_failed"][0]["error_code"], "INSTITUTION_NOT_RESPONDING")

        good = PlaidItem.objects.get(item_id="item-good")
        bad = PlaidItem.objects.get(item_id="item-bad")
        self.assertTrue(good.last_sync_success)
        self.assertFalse(bad.last_sync_success)
        self.assertIn("Down", bad.last_sync_error)

    @patch("app.views.fetch_transactions")
    @patch("app.views.fetch_accounts")
    def test_sync_all_items_fail_returns_502(self, mock_fetch_accounts, mock_fetch_transactions):
        PlaidItem.objects.create(
            item_id="item-only",
            access_token="access-only",
            institution_name="Down Bank",
        )
        exc = ApiException(status=503, reason="Unavailable")
        exc.body = b'{"error_code":"INTERNAL_SERVER_ERROR"}'
        mock_fetch_accounts.side_effect = exc

        response = self.client.post("/api/plaid/sync", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["items_succeeded"], 0)
        self.assertEqual(len(response.data["items_failed"]), 1)

    def test_sync_status_lists_items(self):
        PlaidItem.objects.create(
            item_id="item-status",
            access_token="access-status",
            institution_name="SoFi",
        )
        response = self.client.get("/api/plaid/sync-status")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["item_id"], "item-status")
        self.assertEqual(response.data[0]["institution"], "SoFi")

    def test_transactions_endpoint_flips_asset_amount_sign_for_display(self):
        item = PlaidItem.objects.create(
            item_id="item-xyz",
            access_token="access-xyz",
            institution_name="SoFi",
        )
        account = Account.objects.create(
            plaid_account_id="acct-2",
            item=item,
            name="SoFi Savings",
            account_type="depository",
            account_subtype="savings",
            current_balance=1200.25,
        )
        Transaction.objects.create(
            plaid_transaction_id="txn-2",
            account=account,
            name="Payroll",
            amount=-1000,
            date="2026-04-10",
            pending=False,
        )

        response = self.client.get("/api/transactions")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(float(response.data[0]["raw_amount"]), -1000.0)
        self.assertEqual(float(response.data[0]["amount"]), 1000.0)
