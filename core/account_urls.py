from django.urls import path
from .account_api import ChangePasswordView
from .account_settings import AcceptTermsView, DeleteAccountView, ExportDataView, ProfileView
from .password_reset import ForgotPasswordView, ResetPasswordConfirmView

urlpatterns = [
  path('change-password/', ChangePasswordView.as_view()),
  path('forgot-password/', ForgotPasswordView.as_view()),
  path('reset-password/', ResetPasswordConfirmView.as_view()),
  path('profile/', ProfileView.as_view()),
  path('export/', ExportDataView.as_view()),
  path('accept-terms/', AcceptTermsView.as_view()),
  path('delete/', DeleteAccountView.as_view()),
]
