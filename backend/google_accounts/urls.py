from django.urls import path

from .views import AccountDetailView, AccountListView, CallbackView, ConnectView

urlpatterns = [
    path("connect", ConnectView.as_view(), name="google-connect"),
    path("callback", CallbackView.as_view(), name="google-callback"),
    path("accounts", AccountListView.as_view(), name="google-accounts"),
    path("accounts/<int:account_id>", AccountDetailView.as_view(), name="google-account-detail"),
]
