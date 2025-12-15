"""
URLs for Account Manager Api.
"""

from django.apps import apps
from django.contrib import admin
from django.urls import include, path

from am.apps.account.views.webserver import (
    FaviconView,
    HealthzView,
    ReadinessView,
    RobotsTxtView,
)


# pylint: disable=C0103
name_prefix = "root"

urlpatterns = [
    path("", include("am.apps.api.urls")),
    path("auth/", include("am.lib.drf.auth.urls")),
    #
    # -----------------------------------
    # static routes
    # -----------------------------------
    path("favicon.png", FaviconView.as_view(), name=f"{name_prefix}_favicon"),
    path("robots.txt", RobotsTxtView.as_view(), name=f"{name_prefix}_robots_txt"),
    path("healthz/", HealthzView.as_view(), name=f"{name_prefix}_healthz"),
    path("readiness/", ReadinessView.as_view(), name=f"{name_prefix}_readiness"),
    # -----------------------------------
    # routes for 3rd party apps
    # -----------------------------------
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("", include(apps.get_app_config("oscar").urls[0])),  # type: ignore[attr-defined]
    # superfluous stuff that breaks the site unless it's included ...
    # -----------
    path("admin/", admin.site.urls),
]

__all__ = ["urlpatterns"]
