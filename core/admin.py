from django.contrib import admin
from .models import (
    StudentProfile, Account, Transaction, Payment,
    LinkedBankAccount, FinancialAidDisbursement
)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'university', 'student_id', 'refund_preference', 'created_at')
    list_filter = ('refund_preference',)
    search_fields = ('user__username', 'university', 'student_id')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'account_type', 'balance', 'is_active', 'created_at')
    list_filter = ('account_type', 'is_active')
    search_fields = ('account_number', 'user__username')


@admin.register(LinkedBankAccount)
class LinkedBankAccountAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_number_last4', 'user', 'account_type', 'is_primary', 'is_verified', 'created_at')
    list_filter = ('account_type', 'is_primary', 'is_verified')
    search_fields = ('bank_name', 'user__username', 'account_number_last4')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'account', 'transaction_type', 'amount', 'status', 'linked_bank', 'created_at')
    list_filter = ('transaction_type', 'status')
    search_fields = ('reference', 'description')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'amount', 'method', 'status', 'cheque_number', 'created_at')
    list_filter = ('method', 'status')
    search_fields = ('reference', 'user__username', 'cheque_number', 'bank_name')
    readonly_fields = ('reference', 'created_at', 'completed_at')


@admin.register(FinancialAidDisbursement)
class FinancialAidDisbursementAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'amount', 'school_name', 'destination', 'status', 'created_at')
    list_filter = ('destination', 'status')
    search_fields = ('reference', 'user__username', 'school_name')
    readonly_fields = ('reference', 'created_at', 'completed_at')
