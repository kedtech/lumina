# LuminaBank – Student Digital Banking Platform

A production-oriented Django application for student checking, savings, funding, withdrawals, and financial aid disbursements.

## Features

- Student Checking & High-Yield Savings accounts
- Fund account via Card (Stripe), Bank Transfer (ACH), and Cheque
- Withdraw funds to linked external bank accounts
- Financial Aid refund preference (LuminaBank or external bank)
- Financial Aid disbursement processing
- Full transaction history and dashboard
- Secure authentication (login / logout / signup)

## Quick Start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit http://127.0.0.1:8000/

## Stripe Configuration (Card Payments)

Set your keys as environment variables (recommended):

```bash
export STRIPE_PUBLIC_KEY=pk_live_...   # or pk_test_...
export STRIPE_SECRET_KEY=sk_live_...   # or sk_test_...
```

Or update the values in `luminabank/settings.py`.

When valid Stripe keys are provided, the application creates real PaymentIntents.  
Without configured keys, card payments still complete successfully for local development.

## Production Checklist

- [ ] Set `DEBUG = False`
- [ ] Configure a strong `SECRET_KEY`
- [ ] Set proper `ALLOWED_HOSTS`
- [ ] Use PostgreSQL (or another production database)
- [ ] Configure HTTPS and secure cookies
- [ ] Add real Stripe live keys
- [ ] Integrate Plaid (or equivalent) for bank account verification
- [ ] Add webhook endpoint for Stripe payment confirmation
- [ ] Configure email backend for notifications
- [ ] Set up proper logging and monitoring

## Project Structure

```
luminabank/
├── core/                 # Main application
│   ├── models.py         # Account, Transaction, Payment, LinkedBank, FinancialAid
│   ├── views.py
│   ├── forms.py
│   ├── templates/core/
│   └── urls.py
├── luminabank/           # Project settings
├── manage.py
└── requirements.txt
```

## License

Proprietary – All rights reserved.
