"""URLs for Account Manager Api."""

from django.urls import include, path

# pylint: disable=C0103
name_prefix = "root"

urlpatterns = [
    path("", include("am.apps.api.v1.urls")),
    path("auth/", include("am.lib.drf.auth.urls")),
    #
    # -----------------------------------
    # routes for 3rd party apps
    # -----------------------------------
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]

__all__ = ["urlpatterns"]
