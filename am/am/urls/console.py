"""URLs for Account Manager web console."""

from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path

from am.apps.account.views.authentication import (
    LoginView,
    LogoutView,
)
from am.apps.account.views.webserver import (
    FaviconView,
    HealthzView,
    ReadinessView,
    RobotsTxtView,
)
from am.apps.api.const import namespace as api_namespace
from am.apps.api.v1.views.openapi import schema_view

admin.autodiscover()

# pylint: disable=C0103
name_prefix = "root"


urlpatterns = [
    path("", lambda request: redirect("admin:index"), name=f"{name_prefix}_home"),
    # -----------------------------------
    # root paths
    # -----------------------------------
    path("api/", include("am.apps.api.urls", namespace=api_namespace)),
    path("admin/", admin.site.urls, name="django_admin"),
    path("admin/docs/", include("django.contrib.admindocs.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("login/", LoginView.as_view(), name="login_view"),
    path("logout/", LogoutView.as_view(), name="logout_view"),
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
    # -----------------------------------
    # stripe urls
    # see: https://dj-stripe.dev/dj-stripe/
    # -----------------------------------
    # path("stripe/", include("djstripe.urls", namespace="djstripe")),
    # -----------------------------------
    # -------------------------------------------------------------------------
    # Documentation generators
    # -------------------------------------------------------------------------
    re_path(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

__all__ = ["urlpatterns"]
