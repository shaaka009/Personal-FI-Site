from django.db import models


class PlaidItem(models.Model):
    item_id = models.CharField(max_length=255, unique=True)
    access_token = models.CharField(max_length=255)
    institution_name = models.CharField(max_length=255, blank=True)
    last_transactions_sync_cursor = models.CharField(max_length=255, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_success = models.BooleanField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.institution_name or 'Institution'} ({self.item_id})"


class Account(models.Model):
    plaid_account_id = models.CharField(max_length=255, unique=True)
    item = models.ForeignKey(PlaidItem, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=255)
    official_name = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(max_length=100)
    account_subtype = models.CharField(max_length=100, blank=True)
    mask = models.CharField(max_length=16, blank=True)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    available_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=8, default="USD")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class Transaction(models.Model):
    plaid_transaction_id = models.CharField(max_length=255, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    pending = models.BooleanField(default=False)
    merchant_name = models.CharField(max_length=255, blank=True)
    category_primary = models.CharField(max_length=255, blank=True)
    category_detailed = models.CharField(max_length=255, blank=True)
    payment_channel = models.CharField(max_length=100, blank=True)
    authorized_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-updated_at"]
