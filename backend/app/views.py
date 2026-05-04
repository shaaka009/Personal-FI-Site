import json
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from plaid import ApiException
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Account, PlaidItem, Transaction
from .plaid_errors import plaid_error_payload, plaid_http_status, plaid_user_message
from .services.plaid_client import (
    create_link_token,
    exchange_public_token,
    fetch_accounts,
    fetch_transactions,
)

ASSET_ACCOUNT_TYPES = {"depository", "investment"}


def display_amount_for_account(txn: Transaction):
    """
    Plaid uses positive = money leaving the account.
    For asset accounts, flip sign so inflows are positive in the UI.
    """
    if txn.account.account_type in ASSET_ACCOUNT_TYPES:
        return -txn.amount
    return txn.amount


def plaid_error_response(error: Exception):
    payload = plaid_error_payload(error)
    if isinstance(error, ApiException):
        return Response(payload, status=plaid_http_status(error))
    return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def plaid_link_token(request):
    try:
        token_data = create_link_token()
        return Response({"link_token": token_data.get("link_token")})
    except Exception as exc:
        return plaid_error_response(exc)


@api_view(["POST"])
def plaid_exchange_token(request):
    public_token = request.data.get("public_token")
    institution_name = request.data.get("institution_name", "")
    if not public_token:
        return Response(
            {"error": "public_token is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        exchange = exchange_public_token(public_token)
        item_id = exchange["item_id"]
        access_token = exchange["access_token"]
        PlaidItem.objects.update_or_create(
            item_id=item_id,
            defaults={
                "access_token": access_token,
                "institution_name": institution_name,
            },
        )
        return Response({"item_id": item_id})
    except Exception as exc:
        return plaid_error_response(exc)


def _sync_single_item(item: PlaidItem) -> tuple[int, int, int]:
    """Fetch and persist accounts + transactions for one Plaid item.

    Returns (created, updated, plaid_transaction_rows_returned).
    """
    created = 0
    updated = 0
    accounts_payload = fetch_accounts(item.access_token)
    lookback = settings.PLAID_TRANSACTION_SYNC_LOOKBACK_DAYS
    start_date = date.today() - timedelta(days=lookback)
    end_date = date.today()
    transactions_payload = fetch_transactions(item.access_token, start_date, end_date)
    plaid_rows = transactions_payload.get("transactions") or []

    with transaction.atomic():
        for account_data in accounts_payload.get("accounts", []):
            balances = account_data.get("balances", {})
            Account.objects.update_or_create(
                plaid_account_id=account_data["account_id"],
                defaults={
                    "item": item,
                    "name": account_data.get("name", ""),
                    "official_name": account_data.get("official_name", "") or "",
                    "account_type": account_data.get("type", ""),
                    "account_subtype": account_data.get("subtype", "") or "",
                    "mask": account_data.get("mask", "") or "",
                    "current_balance": balances.get("current"),
                    "available_balance": balances.get("available"),
                    "currency_code": balances.get("iso_currency_code") or "USD",
                },
            )

        for txn in plaid_rows:
            account = Account.objects.filter(plaid_account_id=txn["account_id"]).first()
            if not account:
                continue
            pfc = txn.get("personal_finance_category")
            if not isinstance(pfc, dict):
                pfc = {}
            _, was_created = Transaction.objects.update_or_create(
                plaid_transaction_id=txn["transaction_id"],
                defaults={
                    "account": account,
                    "name": txn.get("name", ""),
                    "amount": txn.get("amount", 0),
                    "date": txn.get("date"),
                    "pending": txn.get("pending", False),
                    "merchant_name": txn.get("merchant_name", "") or "",
                    "category_primary": pfc.get("primary", "") or "",
                    "category_detailed": pfc.get("detailed", "") or "",
                    "payment_channel": txn.get("payment_channel", "") or "",
                    "authorized_date": txn.get("authorized_date"),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
    return created, updated, len(plaid_rows)


@api_view(["POST"])
def plaid_sync(request):
    items = list(PlaidItem.objects.all())
    if not items:
        return Response(
            {"error": "No connected institutions. Link an account first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    total_transactions_created = 0
    total_transactions_updated = 0
    total_plaid_transaction_rows = 0
    items_failed: list[dict] = []
    items_succeeded = 0
    lookback = settings.PLAID_TRANSACTION_SYNC_LOOKBACK_DAYS
    window_start = date.today() - timedelta(days=lookback)
    window_end = date.today()

    for item in items:
        try:
            c, u, n = _sync_single_item(item)
            total_transactions_created += c
            total_transactions_updated += u
            total_plaid_transaction_rows += n
            now = timezone.now()
            item.last_sync_at = now
            item.last_sync_success = True
            item.last_sync_error = ""
            item.updated_at = now
            item.save(update_fields=["last_sync_at", "last_sync_success", "last_sync_error", "updated_at"])
            items_succeeded += 1
        except Exception as exc:
            msg = plaid_user_message(exc)
            now = timezone.now()
            item.last_sync_at = now
            item.last_sync_success = False
            item.last_sync_error = msg
            item.updated_at = now
            item.save(update_fields=["last_sync_at", "last_sync_success", "last_sync_error", "updated_at"])
            err_entry: dict = {
                "item_id": item.item_id,
                "institution": item.institution_name or "",
                "error": msg,
            }
            if isinstance(exc, ApiException) and exc.body:
                try:
                    body = json.loads(
                        exc.body.decode("utf-8", errors="replace")
                        if isinstance(exc.body, bytes)
                        else exc.body
                    )
                    if isinstance(body, dict) and body.get("error_code"):
                        err_entry["error_code"] = body["error_code"]
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
            items_failed.append(err_entry)

    payload = {
        "message": "Sync completed"
        if not items_failed
        else ("Sync completed with errors" if items_succeeded else "Sync failed for all institutions"),
        "accounts_count": Account.objects.count(),
        "transactions_count": Transaction.objects.count(),
        "transactions_created": total_transactions_created,
        "transactions_updated": total_transactions_updated,
        "items_succeeded": items_succeeded,
        "items_failed": items_failed,
        "transactions_fetch_window": {
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "lookback_days": lookback,
        },
        "plaid_transaction_rows_fetched": total_plaid_transaction_rows,
        "history_note": (
            "Plaid stores only as much history as was requested the first time that bank was linked "
            f"(`transactions.days_requested`, currently {lookback} days from this app). "
            "If you already linked before raising that value, disconnect the institution and run "
            "Connect Institution again so Plaid can pull a deeper window."
        ),
    }

    if items_succeeded == 0:
        return Response(payload, status=status.HTTP_502_BAD_GATEWAY)
    return Response(payload)


@api_view(["GET"])
def plaid_sync_status(request):
    items = PlaidItem.objects.all().order_by("institution_name", "item_id")
    return Response(
        [
            {
                "item_id": item.item_id,
                "institution": item.institution_name or "",
                "last_sync_at": item.last_sync_at.isoformat() if item.last_sync_at else None,
                "last_sync_success": item.last_sync_success,
                "last_sync_error": item.last_sync_error or "",
            }
            for item in items
        ]
    )


@api_view(["GET"])
def accounts_list(request):
    accounts = Account.objects.select_related("item").all()
    payload = [
        {
            "id": account.id,
            "institution": account.item.institution_name,
            "name": account.name,
            "official_name": account.official_name,
            "type": account.account_type,
            "subtype": account.account_subtype,
            "mask": account.mask,
            "current_balance": account.current_balance,
            "available_balance": account.available_balance,
            "currency_code": account.currency_code,
            "updated_at": account.updated_at,
        }
        for account in accounts
    ]
    return Response(payload)


def _parse_transactions_limit(raw: str | None) -> tuple[int | None, Response | None]:
    if raw is None or raw == "":
        return 500, None
    try:
        n = int(raw)
    except ValueError:
        return None, Response({"error": "Invalid limit"}, status=status.HTTP_400_BAD_REQUEST)
    if n < 1:
        return None, Response({"error": "limit must be at least 1"}, status=status.HTTP_400_BAD_REQUEST)
    return min(n, 2000), None


@api_view(["GET"])
def transactions_list(request):
    qs = Transaction.objects.select_related("account", "account__item").all()

    date_from = request.query_params.get("date_from")
    if date_from:
        try:
            qs = qs.filter(date__gte=date.fromisoformat(date_from))
        except ValueError:
            return Response({"error": "Invalid date_from"}, status=status.HTTP_400_BAD_REQUEST)

    date_to = request.query_params.get("date_to")
    if date_to:
        try:
            qs = qs.filter(date__lte=date.fromisoformat(date_to))
        except ValueError:
            return Response({"error": "Invalid date_to"}, status=status.HTTP_400_BAD_REQUEST)

    account_id = request.query_params.get("account_id")
    if account_id is not None and account_id != "":
        if not str(account_id).isdigit():
            return Response({"error": "Invalid account_id"}, status=status.HTTP_400_BAD_REQUEST)
        qs = qs.filter(account_id=int(account_id))

    institution = (request.query_params.get("institution") or "").strip()
    if institution:
        qs = qs.filter(account__item__institution_name__icontains=institution)

    category = (request.query_params.get("category") or "").strip()
    if category:
        qs = qs.filter(
            Q(category_primary__icontains=category)
            | Q(category_detailed__icontains=category)
        )

    q = (request.query_params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(merchant_name__icontains=q))

    pending_raw = request.query_params.get("pending")
    if pending_raw is not None and pending_raw != "":
        key = pending_raw.lower()
        if key in ("true", "1", "yes"):
            qs = qs.filter(pending=True)
        elif key in ("false", "0", "no"):
            qs = qs.filter(pending=False)
        else:
            return Response({"error": "Invalid pending"}, status=status.HTTP_400_BAD_REQUEST)

    limit_n, err = _parse_transactions_limit(request.query_params.get("limit"))
    if err:
        return err

    ordered = qs.order_by("-date", "-updated_at")
    total = ordered.count()
    slice_qs = ordered[:limit_n]
    payload = [
        {
            "id": txn.id,
            "transaction_id": txn.plaid_transaction_id,
            "account_id": txn.account_id,
            "institution": txn.account.item.institution_name,
            "account_name": txn.account.name,
            "name": txn.name,
            "amount": display_amount_for_account(txn),
            "raw_amount": txn.amount,
            "date": txn.date,
            "pending": txn.pending,
            "merchant_name": txn.merchant_name,
            "category_primary": txn.category_primary,
            "category_detailed": txn.category_detailed,
        }
        for txn in slice_qs
    ]
    return Response({"results": payload, "count": total})
