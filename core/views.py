from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal
import stripe

from .forms import (
    SignUpForm, CardPaymentForm, BankTransferForm, ChequePaymentForm,
    LinkBankAccountForm, WithdrawalForm,
    RefundPreferenceForm, DisburseFinancialAidForm
)
from .models import (
    Account, Transaction, Payment, LinkedBankAccount,
    StudentProfile, FinancialAidDisbursement
)

stripe.api_key = settings.STRIPE_SECRET_KEY


def home(request):
    return render(request, 'core/home.html')


def features(request):
    return render(request, 'core/features.html')


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    if request.method == 'POST':
        messages.success(request, "Thank you! Your message has been received. Our team will respond within 1 business day.")
        return redirect('contact')
    return render(request, 'core/contact.html')


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Account.objects.create(user=user, account_type='checking', balance=Decimal('0.00'))
            login(request, user)
            messages.success(request, "Welcome to LuminaBank! Your Student Checking account is ready.")
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})


class CustomLoginView(LoginView):
    template_name = 'core/login.html'
    redirect_authenticated_user = True


@login_required
def dashboard(request):
    accounts = request.user.accounts.filter(is_active=True)
    recent_transactions = Transaction.objects.filter(
        account__user=request.user
    ).order_by('-created_at')[:12]

    checking = accounts.filter(account_type='checking').first()
    savings = accounts.filter(account_type='savings').first()
    linked_banks = request.user.linked_banks.all()[:5]
    profile = getattr(request.user, 'profile', None)
    recent_aid = FinancialAidDisbursement.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]

    context = {
        'accounts': accounts,
        'checking': checking,
        'savings': savings,
        'recent_transactions': recent_transactions,
        'linked_banks': linked_banks,
        'profile': profile,
        'recent_aid': recent_aid,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def payments(request):
    card_form = CardPaymentForm()
    bank_form = BankTransferForm()
    cheque_form = ChequePaymentForm()
    recent_payments = Payment.objects.filter(user=request.user).order_by('-created_at')[:8]

    context = {
        'card_form': card_form,
        'bank_form': bank_form,
        'cheque_form': cheque_form,
        'recent_payments': recent_payments,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    }
    return render(request, 'core/payments.html', context)


@login_required
@require_POST
def process_card_payment(request):
    form = CardPaymentForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': 'Invalid form data. Please check the amount.'}, status=400)

    amount = form.cleaned_data['amount']
    description = form.cleaned_data.get('description') or 'Account funding'

    account = request.user.accounts.filter(account_type='checking').first()
    if not account:
        account = Account.objects.create(user=request.user, account_type='checking')

    # Production path: create real PaymentIntent when valid Stripe keys are configured
    if settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith('sk_test_51Your'):
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency='usd',
                description=description,
                metadata={
                    'user_id': str(request.user.id),
                    'account_id': str(account.id),
                },
                automatic_payment_methods={'enabled': True},
            )
            payment = Payment.objects.create(
                user=request.user,
                account=account,
                amount=amount,
                method='card',
                status='pending',
                stripe_payment_intent=intent.id,
            )
            return JsonResponse({
                'clientSecret': intent.client_secret,
                'payment_id': payment.id,
                'reference': payment.reference,
            })
        except stripe.error.StripeError as e:
            return JsonResponse({'error': str(e.user_message or e)}, status=400)

    # Fallback when Stripe keys are not yet configured (development only)
    payment = Payment.objects.create(
        user=request.user,
        account=account,
        amount=amount,
        method='card',
        status='completed',
        completed_at=timezone.now(),
    )
    account.balance += amount
    account.save()
    Transaction.objects.create(
        account=account,
        transaction_type='deposit',
        amount=amount,
        description=f"Card payment: {description}",
        status='completed',
    )
    return JsonResponse({
        'success': True,
        'message': f'Payment of ${amount:.2f} completed successfully.',
        'reference': payment.reference,
        'new_balance': str(account.balance),
    })


@login_required
@require_POST
def process_bank_transfer(request):
    form = BankTransferForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the errors in the form.")
        return redirect('payments')

    amount = form.cleaned_data['amount']
    bank_name = form.cleaned_data['bank_name']
    routing = form.cleaned_data['routing_number']
    account_number = form.cleaned_data['account_number']

    account = request.user.accounts.filter(account_type='checking').first()
    if not account:
        account = Account.objects.create(user=request.user, account_type='checking')

    payment = Payment.objects.create(
        user=request.user,
        account=account,
        amount=amount,
        method='bank_transfer',
        status='processing',
        bank_name=bank_name,
        routing_number=routing,
        account_number_last4=account_number[-4:],
    )

    # Credit account (in production this would happen after ACH settlement)
    account.balance += amount
    account.save()
    payment.status = 'completed'
    payment.completed_at = timezone.now()
    payment.save()

    Transaction.objects.create(
        account=account,
        transaction_type='deposit',
        amount=amount,
        description=f"Bank transfer from {bank_name} ••••{account_number[-4:]}",
        status='completed',
    )

    messages.success(
        request,
        f"Bank transfer of ${amount:.2f} initiated successfully. "
        f"Reference: {payment.reference}. Funds are typically available within 1–3 business days."
    )
    return redirect('dashboard')


@login_required
@require_POST
def process_cheque_payment(request):
    form = ChequePaymentForm(request.POST)
    if not form.is_valid():
        error_list = []
        for field, errors in form.errors.items():
            for error in errors:
                error_list.append(f"{field.replace('_', ' ').title()}: {error}")
        messages.error(request, "Validation failed: " + " | ".join(error_list))
        return redirect('payments')

    amount = form.cleaned_data['amount']
    cheque_number = form.cleaned_data['cheque_number']
    bank_name = form.cleaned_data['bank_name']
    issue_date = form.cleaned_data['issue_date']
    payer_name = form.cleaned_data.get('payer_name') or ''

    account = request.user.accounts.filter(account_type='checking').first()
    if not account:
        account = Account.objects.create(user=request.user, account_type='checking')

    payment = Payment.objects.create(
        user=request.user,
        account=account,
        amount=amount,
        method='cheque',
        status='processing',
        bank_name=bank_name,
        cheque_number=cheque_number,
        cheque_issue_date=issue_date,
    )

    # In production, funds would be held until the cheque clears
    account.balance += amount
    account.save()
    payment.status = 'completed'
    payment.completed_at = timezone.now()
    payment.save()

    Transaction.objects.create(
        account=account,
        transaction_type='deposit',
        amount=amount,
        description=f"Cheque #{cheque_number} – {bank_name}" + (f" ({payer_name})" if payer_name else ""),
        status='completed',
    )

    messages.success(
        request,
        f"Cheque #{cheque_number} for ${amount:.2f} has been submitted. "
        f"Reference: {payment.reference}. Funds are usually available after the cheque clears (1–3 business days)."
    )
    return redirect('dashboard')


@login_required
def withdraw(request):
    checking = request.user.accounts.filter(account_type='checking', is_active=True).first()
    linked_banks = request.user.linked_banks.filter(is_verified=True)

    if request.method == 'POST':
        form = WithdrawalForm(request.user, request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            linked_bank = form.cleaned_data['linked_bank']
            memo = form.cleaned_data.get('memo') or ''

            checking.balance -= amount
            checking.save()

            description = f"Withdrawal to {linked_bank.bank_name} ••••{linked_bank.account_number_last4}"
            if memo:
                description += f" – {memo}"

            txn = Transaction.objects.create(
                account=checking,
                transaction_type='withdrawal',
                amount=amount,
                description=description,
                status='processing',
                linked_bank=linked_bank,
            )
            # Mark completed after initiation (real ACH would stay processing longer)
            txn.status = 'completed'
            txn.save()

            messages.success(
                request,
                f"Withdrawal of ${amount:.2f} to {linked_bank.bank_name} ••••{linked_bank.account_number_last4} "
                f"has been initiated. Reference: {txn.reference}. "
                f"Funds typically arrive in 1–3 business days."
            )
            return redirect('dashboard')
    else:
        form = WithdrawalForm(request.user)

    return render(request, 'core/withdraw.html', {
        'form': form,
        'checking': checking,
        'linked_banks': linked_banks,
    })


@login_required
def link_bank(request):
    if request.method == 'POST':
        form = LinkBankAccountForm(request.POST)
        if form.is_valid():
            linked = form.save(commit=False)
            linked.user = request.user
            linked.save()
            messages.success(
                request,
                f"Successfully linked {linked.bank_name} ••••{linked.account_number_last4}."
            )
            return redirect('withdraw')
    else:
        form = LinkBankAccountForm()
    return render(request, 'core/link_bank.html', {'form': form})


@login_required
def delete_linked_bank(request, pk):
    linked = get_object_or_404(LinkedBankAccount, pk=pk, user=request.user)
    name = f"{linked.bank_name} ••••{linked.account_number_last4}"
    linked.delete()
    messages.success(request, f"Removed linked account {name}.")
    return redirect('withdraw')


@login_required
def open_savings(request):
    if request.user.accounts.filter(account_type='savings').exists():
        messages.info(request, "You already have a Savings account.")
        return redirect('dashboard')
    Account.objects.create(user=request.user, account_type='savings', balance=Decimal('0.00'))
    messages.success(request, "High-Yield Savings account opened successfully.")
    return redirect('dashboard')


@login_required
def confirm_card_payment(request):
    payment_id = request.GET.get('payment_id')
    if not payment_id:
        messages.error(request, "Invalid payment confirmation.")
        return redirect('payments')
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    if payment.status != 'completed':
        payment.status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()
        if payment.account:
            payment.account.balance += payment.amount
            payment.account.save()
            Transaction.objects.create(
                account=payment.account,
                transaction_type='deposit',
                amount=payment.amount,
                description=f"Card payment {payment.reference}",
                status='completed',
            )
    messages.success(request, f"Payment of ${payment.amount:.2f} completed. Reference: {payment.reference}")
    return redirect('dashboard')


@login_required
def refund_preference(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    linked_banks = request.user.linked_banks.filter(is_verified=True)

    if request.method == 'POST':
        form = RefundPreferenceForm(request.user, request.POST)
        if form.is_valid():
            profile.refund_preference = form.cleaned_data['refund_preference']
            if profile.refund_preference == 'external':
                profile.preferred_external_bank = form.cleaned_data['preferred_external_bank']
            else:
                profile.preferred_external_bank = None
            profile.save()
            messages.success(request, "Your Financial Aid refund preference has been updated.")
            return redirect('dashboard')
    else:
        form = RefundPreferenceForm(request.user, initial={
            'refund_preference': profile.refund_preference,
            'preferred_external_bank': profile.preferred_external_bank,
        })

    return render(request, 'core/refund_preference.html', {
        'form': form,
        'profile': profile,
        'linked_banks': linked_banks,
    })


@login_required
def disburse_aid(request):
    """Process a financial aid disbursement according to the student's refund preference."""
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = DisburseFinancialAidForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            school_name = form.cleaned_data['school_name']
            term = form.cleaned_data.get('term') or ''
            description = form.cleaned_data.get('description') or f"Financial Aid from {school_name}"

            destination = profile.refund_preference
            external_bank = None

            if destination == 'external':
                external_bank = profile.preferred_external_bank
                if not external_bank:
                    destination = 'lumina'
                    messages.warning(
                        request,
                        "No external bank selected for direct deposit. Funds deposited to your LuminaBank account."
                    )

            disbursement = FinancialAidDisbursement.objects.create(
                user=request.user,
                amount=amount,
                school_name=school_name,
                term=term,
                description=description,
                destination=destination,
                external_bank=external_bank,
                status='processing',
            )

            if destination == 'lumina':
                account = request.user.accounts.filter(account_type='checking').first()
                if not account:
                    account = Account.objects.create(user=request.user, account_type='checking')

                account.balance += amount
                account.save()

                Transaction.objects.create(
                    account=account,
                    transaction_type='aid',
                    amount=amount,
                    description=f"Financial Aid – {school_name}" + (f" ({term})" if term else ""),
                    status='completed',
                )
                disbursement.status = 'completed'
                disbursement.completed_at = timezone.now()
                disbursement.save()

                messages.success(
                    request,
                    f"Financial Aid of ${amount:.2f} from {school_name} has been deposited "
                    f"into your Checking account. Reference: {disbursement.reference}"
                )
            else:
                disbursement.status = 'completed'
                disbursement.completed_at = timezone.now()
                disbursement.save()

                account = request.user.accounts.filter(account_type='checking').first()
                if account:
                    Transaction.objects.create(
                        account=account,
                        transaction_type='aid',
                        amount=amount,
                        description=f"Financial Aid directed to {external_bank.bank_name} ••••{external_bank.account_number_last4} – {school_name}",
                        status='completed',
                        linked_bank=external_bank,
                    )

                messages.success(
                    request,
                    f"Financial Aid of ${amount:.2f} from {school_name} has been sent via direct deposit "
                    f"to {external_bank.bank_name} ••••{external_bank.account_number_last4}. "
                    f"Reference: {disbursement.reference}"
                )

            return redirect('dashboard')
    else:
        form = DisburseFinancialAidForm()

    return render(request, 'core/disburse_aid.html', {
        'form': form,
        'profile': profile,
    })
