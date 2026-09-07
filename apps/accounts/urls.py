"""Browser authentication routes."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegistrationView.as_view(), name="register"),
    path("verification/sent/", views.VerificationSentView.as_view(), name="verification_sent"),
    path("verify/<uidb64>/<token>/", views.VerifyEmailView.as_view(), name="verify_email"),
    path("verification/resend/", views.ResendVerificationView.as_view(), name="resend_verification"),
    path("login/", views.AccountLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/", views.AccountPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.AccountPasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.AccountPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("password-reset/complete/", views.AccountPasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("mfa/setup/", views.MFASetupView.as_view(), name="mfa_setup"),
    path("mfa/challenge/", views.MFAChallengeView.as_view(), name="mfa_challenge"),
    path("mfa/disable/", views.MFADisableView.as_view(), name="mfa_disable"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
]
