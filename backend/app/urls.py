from django.urls import path

from . import views

urlpatterns = [
    path("plaid/link-token", views.plaid_link_token),
    path("plaid/exchange-token", views.plaid_exchange_token),
    path("plaid/sync", views.plaid_sync),
    path("plaid/sync-status", views.plaid_sync_status),
    path("accounts", views.accounts_list),
    path("transactions", views.transactions_list),
]
