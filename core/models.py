from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class StudentProfile(models.Model):
    REFUND_PREFERENCES = [
        ('lumina', 'Deposit to LuminaBank Checking'),
        ('external', 'Direct Deposit to External Bank Account'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    university = models.CharField(max_length=200, blank=True)
    student_id = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # Financial Aid refund preference
    refund_preference = models.CharField(
        max_length=20, choices=REFUND_PREFERENCES, default='lumina'
    )
    preferred_external_bank = models.ForeignKey(
        'LinkedBankAccount', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preferred_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.university}"


class Account(models.Model):
    ACCOUNT_TYPES = [
        ('checking', 'Student Checking'),
        ('savings', 'High-Yield Savings'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    account_number = models.CharField(max_length=20, unique=True, editable=False)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='checking')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    routing_number = models.CharField(max_length=9, default='021000021')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = str(uuid.uuid4().int)[:12]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_type.title()} - {self.account_number}"


class LinkedBankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('checking', 'Checking'),
        ('savings', 'Savings'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='linked_banks')
    bank_name = models.CharField(max_length=100)
    routing_number = models.CharField(max_length=9)
    account_number = models.CharField(max_length=17)
    account_number_last4 = models.CharField(max_length=4, editable=False)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='checking')
    nickname = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Linked Bank Account"
        verbose_name_plural = "Linked Bank Accounts"

    def save(self, *args, **kwargs):
        if self.account_number:
            self.account_number_last4 = self.account_number[-4:]
        if self.is_primary:
            LinkedBankAccount.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bank_name} ••••{self.account_number_last4} ({self.user.username})"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('payment', 'Payment'),
        ('reward', 'Cash Reward'),
        ('aid', 'Financial Aid'),
        ('interest', 'Interest'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    reference = models.CharField(max_length=50, unique=True, editable=False)
    linked_bank = models.ForeignKey(
        LinkedBankAccount, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='withdrawals'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.amount}"


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('card', 'Card Payment'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque / Check'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_payment_intent = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    routing_number = models.CharField(max_length=9, blank=True)
    account_number_last4 = models.CharField(max_length=4, blank=True)
    cheque_number = models.CharField(max_length=30, blank=True)
    cheque_issue_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=50, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - ${self.amount} via {self.method}"


class FinancialAidDisbursement(models.Model):
    """Records a financial aid refund/disbursement from a school."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    DESTINATION_CHOICES = [
        ('lumina', 'LuminaBank Checking'),
        ('external', 'External Bank Account'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='aid_disbursements')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    school_name = models.CharField(max_length=200, default='Partner University')
    term = models.CharField(max_length=50, blank=True, help_text="e.g. Fall 2026")
    description = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=20, choices=DESTINATION_CHOICES)
    external_bank = models.ForeignKey(
        LinkedBankAccount, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='aid_received'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=50, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"AID-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - ${self.amount} to {self.user.username}"
