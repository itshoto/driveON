from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/google/", include("google_accounts.urls")),
    path("api/storage/", include("storage.urls")),
    path("api/files/", include("files.urls")),
]
