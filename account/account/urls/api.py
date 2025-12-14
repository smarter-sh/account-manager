"""
URLs for Account Manager Api.
"""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("", include("account.apps.api.urls")),
    #
    # superfluous stuff that breaks the site unless it's included ...
    # -----------
    path("admin/", admin.site.urls),
    path("", include("account.urls.console")),
]

__all__ = ["urlpatterns"]
