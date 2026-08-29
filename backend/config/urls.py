from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Must come before admin.site.urls so admin/dashboard/ resolves here;
    # everything else under admin/ still falls through to admin.site.urls.
    path("admin/", include("adminpanel.urls")),
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/storage/", include("storage.urls")),
    path("api/files/", include("files.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/sharing/", include("sharing.urls")),
    path("api/ai/", include("ai.urls")),
]
