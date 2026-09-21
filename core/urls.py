from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('payments/', views.payments, name='payments'),
    path('payments/card/', views.process_card_payment, name='process_card'),
    path('payments/bank/', views.process_bank_transfer, name='process_bank'),
    path('payments/cheque/', views.process_cheque_payment, name='process_cheque'),
    path('payments/confirm/', views.confirm_card_payment, name='confirm_card'),
    path('open-savings/', views.open_savings, name='open_savings'),
    # Withdrawal
    path('withdraw/', views.withdraw, name='withdraw'),
    path('link-bank/', views.link_bank, name='link_bank'),
    path('linked-bank/<int:pk>/delete/', views.delete_linked_bank, name='delete_linked_bank'),
    # Financial Aid
    path('refund-preference/', views.refund_preference, name='refund_preference'),
    path('disburse-aid/', views.disburse_aid, name='disburse_aid'),
]
