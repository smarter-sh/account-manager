"""Test the JWT login, refresh and logout views of am.lib.drf.views.react."""

from http import HTTPStatus
from unittest.mock import patch

from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from am.apps.account.tests.mixins import TestAccountMixin
from am.lib.drf.views.react import CookieTokenRefreshView, LoginView, LogoutView

PASSWORD = "12345"
"""The password that the account test factories give their users."""


class TestReactAuthViews(TestAccountMixin):
    """Test LoginView, CookieTokenRefreshView and LogoutView."""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def post(self, view_class, data=None, cookie=None, user=None):
        request = self.factory.post("/api/auth/", data or {}, format="json")
        if cookie is not None:
            request.COOKIES["refresh_token"] = cookie
        if user is not None:
            force_authenticate(request, user=user)
        return view_class.as_view()(request)

    def test_login_returns_tokens(self):
        response = self.post(LoginView, {"username": self.admin_user.username, "password": PASSWORD})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(set(response.data), {"access", "refresh"})

    def test_login_with_bad_password(self):
        response = self.post(LoginView, {"username": self.admin_user.username, "password": "wrong"})
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_login_passes_other_responses_through(self):
        with patch("am.lib.drf.views.react.TokenObtainPairView.post", return_value=Response(status=429)):
            response = self.post(LoginView, {"username": "x", "password": "y"})
        self.assertEqual(response.status_code, 429)

    def test_refresh_from_cookie(self):
        response = self.post(CookieTokenRefreshView, cookie=str(RefreshToken.for_user(self.admin_user)))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(set(response.data), {"access"})

    def test_refresh_without_cookie(self):
        self.assertEqual(self.post(CookieTokenRefreshView).status_code, HTTPStatus.UNAUTHORIZED)

    def test_refresh_with_invalid_cookie(self):
        response = self.post(CookieTokenRefreshView, cookie="not-a-jwt")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_logout_deletes_cookie(self):
        response = self.post(LogoutView, user=self.admin_user)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.cookies["refresh_token"].value, "")

    def test_get_is_not_allowed(self):
        for view_class in (LoginView, CookieTokenRefreshView, LogoutView):
            with self.subTest(view=view_class.__name__):
                request = self.factory.get("/api/auth/")
                force_authenticate(request, user=self.admin_user)
                response = view_class.as_view()(request)
                self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
