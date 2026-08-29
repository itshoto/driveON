from django.urls import path

from .views import (
    RebalanceCheckView,
    RebalanceStatusView,
    RebalanceTriggerView,
    StorageSummaryView,
)

urlpatterns = [
    path("summary", StorageSummaryView.as_view(), name="storage-summary"),
    path("rebalance/check", RebalanceCheckView.as_view(), name="rebalance-check"),
    path("rebalance/trigger", RebalanceTriggerView.as_view(), name="rebalance-trigger"),
    path("rebalance/status/<int:run_id>", RebalanceStatusView.as_view(), name="rebalance-status"),
]
