from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import StudentProfile, LinkedBankAccount, Account
import re


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    university = forms.CharField(max_length=200, required=False, help_text="Your college or university")
    student_id = forms.CharField(max_length=50, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'university', 'student_id')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            StudentProfile.objects.create(
                user=user,
                university=self.cleaned_data.get('university', ''),
                student_id=self.cleaned_data.get('student_id', '')
            )
        return user


class CardPaymentForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1.00, max_value=10000.00, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter amount (USD)', 'step': '0.01'
        })
    )
    description = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional description (e.g. Account funding)'
        })
    )


class BankTransferForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1.00, max_value=50000.00, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter amount (USD)', 'step': '0.01'
        })
    )
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bank name (e.g. Chase, Bank of America)'
        })
    )
    routing_number = forms.CharField(
        max_length=9, min_length=9,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '9-digit routing number', 'pattern': '[0-9]{9}'
        })
    )
    account_number = forms.CharField(
        max_length=17,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Account number'
        })
    )
    account_type = forms.ChoiceField(
        choices=[('checking', 'Checking'), ('savings', 'Savings')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    description = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Optional memo'
        })
    )

    def clean_routing_number(self):
        routing = self.cleaned_data['routing_number']
        if not routing.isdigit() or len(routing) != 9:
            raise forms.ValidationError("Routing number must be exactly 9 digits.")
        return routing


class ChequePaymentForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1.00, max_value=25000.00, decimal_places=2,
        error_messages={
            'min_value': 'Cheque amount must be at least $1.00.',
            'max_value': 'Cheque amount cannot exceed $25,000.00.',
            'required': 'Please enter the cheque amount.',
        },
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter amount written on the cheque', 'step': '0.01'
        })
    )
    cheque_number = forms.CharField(
        max_length=20, min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cheque / Check number (e.g. 1042)',
            'autocomplete': 'off'
        })
    )
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bank name printed on the cheque'
        })
    )
    issue_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    payer_name = forms.CharField(
        max_length=120, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Name of the person/company who wrote the cheque (optional)'
        })
    )
    description = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Optional memo / purpose'
        })
    )

    def clean_cheque_number(self):
        number = self.cleaned_data['cheque_number'].strip()
        if not re.match(r'^[\d\-\s]+$', number):
            raise forms.ValidationError("Cheque number should contain only digits, spaces or hyphens.")
        digits_only = re.sub(r'[\s\-]', '', number)
        if len(digits_only) < 3:
            raise forms.ValidationError("Cheque number must contain at least 3 digits.")
        return number

    def clean_bank_name(self):
        name = self.cleaned_data['bank_name'].strip()
        if len(name) < 2:
            raise forms.ValidationError("Please enter a valid bank name.")
        return name

    def clean_issue_date(self):
        issue_date = self.cleaned_data['issue_date']
        today = timezone.now().date()
        if issue_date > today:
            raise forms.ValidationError("Cheque issue date cannot be in the future.")
        six_months_ago = today - timedelta(days=183)
        if issue_date < six_months_ago:
            raise forms.ValidationError(
                "This cheque appears older than 6 months and may be stale-dated."
            )
        return issue_date


class LinkBankAccountForm(forms.ModelForm):
    """Form to link an external bank account for withdrawals."""
    class Meta:
        model = LinkedBankAccount
        fields = ['bank_name', 'routing_number', 'account_number', 'account_type', 'nickname', 'is_primary']
        widgets = {
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Chase, Bank of America, Wells Fargo'
            }),
            'routing_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '9-digit routing number',
                'pattern': '[0-9]{9}',
                'maxlength': '9'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full account number'
            }),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'nickname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional nickname (e.g. My Main Checking)'
            }),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_routing_number(self):
        routing = self.cleaned_data['routing_number']
        if not routing.isdigit() or len(routing) != 9:
            raise forms.ValidationError("Routing number must be exactly 9 digits.")
        return routing

    def clean_account_number(self):
        number = self.cleaned_data['account_number'].strip()
        if not number.isdigit():
            raise forms.ValidationError("Account number should contain only digits.")
        if len(number) < 4 or len(number) > 17:
            raise forms.ValidationError("Account number length looks invalid.")
        return number


class WithdrawalForm(forms.Form):
    """Form to withdraw funds from Lumina account to a linked bank account."""
    amount = forms.DecimalField(
        min_value=Decimal('1.00'),
        max_value=Decimal('10000.00'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter amount to withdraw',
            'step': '0.01'
        })
    )
    linked_bank = forms.ModelChoiceField(
        queryset=LinkedBankAccount.objects.none(),
        empty_label="Select a linked bank account",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    memo = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional memo'
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['linked_bank'].queryset = LinkedBankAccount.objects.filter(
            user=user, is_verified=True
        ).order_by('-is_primary', '-created_at')

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        # Check available balance in checking account
        checking = Account.objects.filter(
            user=self.user, account_type='checking', is_active=True
        ).first()
        if not checking:
            raise forms.ValidationError("No active checking account found.")
        if amount > checking.balance:
            raise forms.ValidationError(
                f"Insufficient funds. Available balance: ${checking.balance:.2f}"
            )
        if amount < Decimal('1.00'):
            raise forms.ValidationError("Minimum withdrawal amount is $1.00.")
        return amount


class RefundPreferenceForm(forms.Form):
    """Student chooses where Financial Aid should be sent."""
    refund_preference = forms.ChoiceField(
        choices=[
            ('lumina', 'Deposit to my LuminaBank Checking Account'),
            ('external', 'Direct Deposit to my External Bank Account'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Where should we send your Financial Aid refunds?"
    )
    preferred_external_bank = forms.ModelChoiceField(
        queryset=LinkedBankAccount.objects.none(),
        required=False,
        empty_label="Select linked bank account",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="External Bank Account"
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['preferred_external_bank'].queryset = LinkedBankAccount.objects.filter(
            user=user, is_verified=True
        ).order_by('-is_primary', '-created_at')

    def clean(self):
        cleaned = super().clean()
        preference = cleaned.get('refund_preference')
        bank = cleaned.get('preferred_external_bank')
        if preference == 'external' and not bank:
            raise forms.ValidationError(
                "Please select a linked bank account for direct deposit, or change preference to LuminaBank."
            )
        return cleaned


class DisburseFinancialAidForm(forms.Form):
    """Demo / admin form to simulate a school sending financial aid."""
    amount = forms.DecimalField(
        min_value=1.00,
        max_value=50000.00,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Aid amount (USD)',
            'step': '0.01'
        })
    )
    school_name = forms.CharField(
        max_length=200,
        initial='Partner University',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'School / University name'
        })
    )
    term = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Fall 2026, Spring 2027'
        })
    )
    description = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional note (e.g. Pell Grant, Scholarship)'
        })
    )
