from django.urls import path

from .views import AccountDetailView, AccountListView, CallbackView, ConnectView

urlpatterns = [
    path("connect/<str:provider>", ConnectView.as_view(), name="account-connect"),
    path("callback/<str:provider>", CallbackView.as_view(), name="account-callback"),
    path("", AccountListView.as_view(), name="account-list"),
    path("<int:account_id>", AccountDetailView.as_view(), name="account-detail"),
]
