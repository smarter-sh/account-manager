from django.urls import path

from account.lib.drf.views.react import CookieTokenRefreshView, LoginView, LogoutView

from .const import namespace


urlpatterns = [
    path("login/", LoginView.as_view(), name=f"{namespace}_login"),
    path("logout/", LogoutView.as_view(), name=f"{namespace}_logout"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name=f"{namespace}_token_refresh"),
]
