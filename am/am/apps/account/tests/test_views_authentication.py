"""Test the sign-in and sign-out views (``am.apps.account.views.authentication``)."""

from http import HTTPStatus
from unittest.mock import patch

from django.test import Client
from django.urls import reverse

from .mixins import TestAccountMixin


class TestViewsAuthentication(TestAccountMixin):
    """Test LoginView and LogoutView, through the console's ``/login/`` and ``/logout/`` routes."""

    password = "12345"

    def setUp(self):
        """An anonymous client."""
        super().setUp()
        self.client = Client()
        self.login_path = reverse("login_view")
        self.logout_path = reverse("logout_view")

    def assert_signed_in(self, signed_in: bool):
        """
        Assert whether the client's session is signed in.

        :param signed_in: True when it should be.
        """
        self.assertEqual("_auth_user_id" in self.client.session, signed_in)

    def test_get_anonymous_redirects_to_admin_login(self):
        """GET sends an anonymous user to the admin sign-in page, keeping ``next``."""
        response = self.client.get(self.login_path, {"next": "/admin/"})
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], reverse("admin:login") + "?next=%2Fadmin%2F")
        self.assertIn("no-store", response["Cache-Control"])

    def test_get_anonymous_without_query_string(self):
        """GET without a query string redirects to the bare admin sign-in page."""
        response = self.client.get(self.login_path)
        self.assertEqual(response["Location"], reverse("admin:login"))

    def test_get_authenticated_redirects_home(self):
        """GET by a signed-in user redirects to ``/``."""
        self.client.force_login(self.non_admin_user)
        response = self.client.get(self.login_path)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], "/")

    def test_post_valid_credentials_signs_in(self):
        """POST with a valid email and password signs the user in and redirects to ``/``."""
        response = self.client.post(self.login_path, {"email": self.non_admin_user.email, "password": self.password})
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], "/")
        self.assert_signed_in(True)

    def test_post_wrong_password(self):
        """POST with a wrong password is a 400, and does not sign in."""
        response = self.client.post(self.login_path, {"email": self.non_admin_user.email, "password": "wrong"})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assert_signed_in(False)

    def test_post_unknown_email(self):
        """POST with an unknown email address is a 403, and does not echo the address."""
        response = self.client.post(self.login_path, {"email": "nobody@example.com", "password": self.password})
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertNotIn(b"nobody@example.com", response.content)
        self.assert_signed_in(False)

    def test_post_invalid_form(self):
        """POST without a valid email address is a 400."""
        response = self.client.post(self.login_path, {"email": "not-an-email", "password": self.password})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_post_unexpected_error(self):
        """An unexpected error while signing in is a 500."""
        with patch("am.apps.account.views.authentication.authenticate", side_effect=RuntimeError("boom")):
            response = self.client.post(
                self.login_path, {"email": self.non_admin_user.email, "password": self.password}
            )
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assert_signed_in(False)

    def test_logout_get_and_post(self):
        """GET and POST to ``/logout/`` sign the user out and redirect to ``/``."""
        for method in (self.client.get, self.client.post):
            self.client.force_login(self.non_admin_user)
            response = method(self.logout_path)
            self.assertEqual(response.status_code, HTTPStatus.FOUND)
            self.assertEqual(response["Location"], "/")
            self.assert_signed_in(False)
