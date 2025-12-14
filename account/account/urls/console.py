"""
URLs for Account Manager web console.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

from account.apps.account.const import namespace as account_namespace
from account.apps.account.views.authentication import (
    AccountRegisterView,
    LoginView,
    LogoutView,
)
from account.apps.account.views.webserver import (FaviconView, HealthzView, ReadinessView, RobotsTxtView)
from account.apps.api.const import namespace as api_namespace


admin.autodiscover()

name_prefix = "root"


urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard:dashboard"), name=f"{name_prefix}_home"),
    # -----------------------------------
    # Api
    # -----------------------------------
    path("api/", include("account.apps.api.urls", namespace=api_namespace)),
    # -----------------------------------
    # root paths
    # -----------------------------------
    path("account/", include("account.apps.account.urls", namespace=account_namespace)),
    path("admin/", admin.site.urls, name="django_admin"),
    path("admin/docs/", include("django.contrib.admindocs.urls")),
    path("login/", LoginView.as_view(), name="login_view"),
    path("logout/", LogoutView.as_view(), name="logout_view"),
    path("register/", AccountRegisterView.as_view(), name=f"{name_prefix}_register_view"),
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
    path("social-auth/", include("social_django.urls", namespace="social_auth")),
    # -----------------------------------
    # stripe urls
    # see: https://dj-stripe.dev/dj-stripe/
    # -----------------------------------
    # path("stripe/", include("djstripe.urls", namespace="djstripe")),
    # -----------------------------------
    # -----------------------------------
    # IMPORTANT: place these wagtail routes at the end of the urlpatterns
    # -----------------------------------
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# if settings.DEBUG:
#     import debug_toolbar
# urlpatterns += [
#     path("__debug__/", include(debug_toolbar.urls)),
# ]

__all__ = ["urlpatterns"]
