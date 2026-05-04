from django.conf import settings
from plaid import ApiClient, Configuration
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions


ENVIRONMENTS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


def _api_client() -> plaid_api.PlaidApi:
    host = ENVIRONMENTS.get(settings.PLAID_ENV, ENVIRONMENTS["development"])
    configuration = Configuration(
        host=host,
        api_key={
            "clientId": settings.PLAID_CLIENT_ID,
            "secret": settings.PLAID_SECRET,
        },
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token() -> dict:
    client = _api_client()
    request_kwargs = dict(
        user=LinkTokenCreateRequestUser(client_user_id="single-user-local"),
        client_name="Personal FI Tracker",
        language="en",
        country_codes=[CountryCode(code) for code in settings.PLAID_COUNTRY_CODES],
        products=[Products(product) for product in settings.PLAID_PRODUCTS],
    )
    if settings.PLAID_REDIRECT_URI:
        request_kwargs["redirect_uri"] = settings.PLAID_REDIRECT_URI
    # Plaid caps how much history exists for an Item at first link time (default 90 days).
    # Must match PLAID_TRANSACTION_SYNC_LOOKBACK_DAYS; changing env alone does not deepen old Items.
    if any(p.strip().lower() == "transactions" for p in settings.PLAID_PRODUCTS):
        request_kwargs["transactions"] = LinkTokenTransactions(
            days_requested=settings.PLAID_TRANSACTION_SYNC_LOOKBACK_DAYS
        )

    request = LinkTokenCreateRequest(**request_kwargs)
    return client.link_token_create(request).to_dict()


def exchange_public_token(public_token: str) -> dict:
    client = _api_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    return client.item_public_token_exchange(request).to_dict()


def fetch_accounts(access_token: str) -> dict:
    client = _api_client()
    return client.accounts_get({"access_token": access_token}).to_dict()


def fetch_transactions(access_token: str, start_date, end_date) -> dict:
    """Pull all transactions in the date range (paginates; Plaid caps count per request at 500)."""
    client = _api_client()
    page_size = 500
    offset = 0
    merged: list[dict] = []
    while True:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(count=page_size, offset=offset),
        )
        payload = client.transactions_get(request).to_dict()
        batch = payload.get("transactions") or []
        merged.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return {"transactions": merged}
